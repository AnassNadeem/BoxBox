"""OpenF1 REST client (https://api.openf1.org/v1) + fallback ingestion to RaceData.

Used two ways:
1. Fallback ingestion when FastF1 cannot load a race (ingest_openf1).
2. Live polling source for the Sunday live runner (OpenF1Client used directly).

Historic data needs no auth. All times are normalized to seconds relative to the
earliest lap start we see, so downstream gap math matches the FastF1 path.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Optional

import httpx

from boxbox.data.schemas import (
    LapRecord,
    RaceData,
    Weather,
)

log = logging.getLogger(__name__)

BASE_URL = "https://api.openf1.org/v1"
_COMPOUNDS = {"SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"}


def _parse_date_s(value: Any) -> Optional[float]:
    """OpenF1 ISO-8601 date -> epoch seconds (float), None-safe."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


class OpenF1Client:
    """Thin retrying GET client for OpenF1."""

    def __init__(self, base_url: str = BASE_URL, timeout: float = 30.0, retries: int = 3):
        self.base_url = base_url
        self.retries = retries
        self._client = httpx.Client(timeout=timeout)

    def get(self, endpoint: str, **params: Any) -> list[dict[str, Any]]:
        url = f"{self.base_url}/{endpoint}"
        last_exc: Exception | None = None
        for attempt in range(self.retries):
            try:
                resp = self._client.get(url, params=params)
                if resp.status_code == 429 or resp.status_code >= 500:
                    raise httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}", request=resp.request, response=resp
                    )
                resp.raise_for_status()
                data = resp.json()
                return data if isinstance(data, list) else []
            except Exception as exc:  # network or HTTP error: back off and retry
                last_exc = exc
                wait = 2.0**attempt
                log.warning("OpenF1 %s failed (%s); retry in %.0fs", endpoint, exc, wait)
                time.sleep(wait)
        raise RuntimeError(f"OpenF1 {endpoint} failed after {self.retries} tries: {last_exc}")

    def close(self) -> None:
        self._client.close()


def find_race_session(client: OpenF1Client, year: int, event: str) -> dict[str, Any]:
    """Resolve (year, event-name fragment) to the OpenF1 race session row."""
    sessions = client.get("sessions", year=year, session_name="Race")
    frag = event.lower()
    for s in sessions:
        haystack = " ".join(
            str(s.get(k, "")) for k in ("country_name", "location", "circuit_short_name")
        ).lower()
        if frag in haystack:
            return s
    raise RuntimeError(f"No OpenF1 race session found for {year} '{event}'")


def ingest_openf1(race_id: str, year: int, event: str) -> RaceData:
    """Fallback ingestion: build the same RaceData shape FastF1 would give us."""
    client = OpenF1Client()
    try:
        session = find_race_session(client, year, event)
        key = session["session_key"]

        drivers = {d["driver_number"]: d for d in client.get("drivers", session_key=key)}
        laps_raw = client.get("laps", session_key=key)
        stints_raw = client.get("stints", session_key=key)
        pits_raw = client.get("pit", session_key=key)
        rc_raw = client.get("race_control", session_key=key)
        weather_raw = client.get("weather", session_key=key)
    finally:
        client.close()

    def acronym(num: Any) -> str:
        d = drivers.get(num, {})
        return str(d.get("name_acronym") or f"#{num}")

    def team(num: Any) -> str:
        return str(drivers.get(num, {}).get("team_name") or "")

    # stint lookup: (driver_number, lap) -> (compound, tyre_age_incl_current, stint_no)
    stint_info: dict[tuple[Any, int], tuple[str, int, int]] = {}
    for s in stints_raw:
        comp = str(s.get("compound") or "").upper()
        comp = comp if comp in _COMPOUNDS else "UNKNOWN"
        start = int(s.get("lap_start") or 0)
        end = int(s.get("lap_end") or 0)
        age0 = int(s.get("tyre_age_at_start") or 0)
        num = s.get("driver_number")
        stint_no = int(s.get("stint_number") or 0)
        for lap in range(start, end + 1):
            stint_info[(num, lap)] = (comp, age0 + (lap - start) + 1, stint_no)

    pit_in_laps = {(p.get("driver_number"), int(p.get("lap_number") or 0)) for p in pits_raw}

    # SC/VSC intervals from race control messages
    sc_intervals = _status_intervals(rc_raw, ("SAFETY CAR DEPLOYED",), "SC")
    vsc_intervals = _status_intervals(rc_raw, ("VIRTUAL SAFETY CAR DEPLOYED",), "VSC")

    t0 = min(
        (t for t in (_parse_date_s(lap.get("date_start")) for lap in laps_raw) if t is not None),
        default=0.0,
    )

    records: list[LapRecord] = []
    for lap in laps_raw:
        num = lap.get("driver_number")
        n = int(lap.get("lap_number") or 0)
        if n <= 0:
            continue
        dur = lap.get("lap_duration")
        start_abs = _parse_date_s(lap.get("date_start"))
        start_s = (start_abs - t0) if start_abs is not None else None
        end_s = start_s + float(dur) if (start_s is not None and dur is not None) else None
        comp, age, stint_no = stint_info.get((num, n), ("UNKNOWN", 0, 0))
        status = _label_for_interval(start_abs, dur, sc_intervals, vsc_intervals)
        records.append(
            LapRecord(
                driver=acronym(num),
                team=team(num),
                lap_number=n,
                lap_time_s=float(dur) if dur is not None else None,
                start_time_s=start_s,
                end_time_s=end_s,
                compound=comp,  # type: ignore[arg-type]
                tyre_age=age or None,
                stint=stint_no or None,
                position=None,  # filled below by completion-time ranking
                pit_in=(num, n) in pit_in_laps,
                pit_out=bool(lap.get("is_pit_out_lap")),
                track_status=status,
                is_accurate=dur is not None and not bool(lap.get("is_pit_out_lap")),
            )
        )

    from boxbox.data.ingest import _fill_missing_positions, derive_pit_stops

    _fill_missing_positions(records)

    total_laps = max((r.lap_number for r in records), default=0)
    last_lap: dict[str, int] = {}
    for r in records:
        last_lap[r.driver] = max(last_lap.get(r.driver, 0), r.lap_number)
    classified = [d for d, n in last_lap.items() if n >= 0.9 * total_laps]
    retirements = {d: n for d, n in last_lap.items() if d not in classified}

    weather = Weather()
    if weather_raw:
        try:
            air = [
                w["air_temperature"] for w in weather_raw if w.get("air_temperature") is not None
            ]
            trk = [
                w["track_temperature"]
                for w in weather_raw
                if w.get("track_temperature") is not None
            ]
            rain = any(float(w.get("rainfall") or 0) > 0 for w in weather_raw)
            weather = Weather(
                air_temp_c=round(sum(air) / len(air), 1) if air else None,
                track_temp_c=round(sum(trk) / len(trk), 1) if trk else None,
                rain=rain,
            )
        except (KeyError, TypeError, ZeroDivisionError):
            pass

    return RaceData(
        race_id=race_id,
        season=year,
        track=str(session.get("location") or event),
        total_laps=total_laps,
        weather=weather,
        laps=records,
        pit_stops=derive_pit_stops(records),
        classified=classified,
        retirements=retirements,
        teams={r.driver: r.team for r in records if r.team},
        source="openf1",
    )


def _status_intervals(
    rc_messages: list[dict[str, Any]], start_markers: tuple[str, ...], kind: str
) -> list[tuple[float, float]]:
    """Build [start, end) epoch intervals for SC or VSC periods from race control."""
    events: list[tuple[float, str]] = []
    for m in rc_messages:
        ts = _parse_date_s(m.get("date"))
        msg = str(m.get("message") or "").upper()
        if ts is None:
            continue
        events.append((ts, msg))
    events.sort()

    intervals: list[tuple[float, float]] = []
    open_start: Optional[float] = None
    for ts, msg in events:
        if any(marker in msg for marker in start_markers):
            if open_start is None:
                open_start = ts
        elif open_start is not None and (
            "GREEN" in msg
            or "CLEAR" in msg
            or (kind == "SC" and "SAFETY CAR IN THIS LAP" in msg)
            or (kind == "VSC" and "VIRTUAL SAFETY CAR ENDING" in msg)
        ):
            intervals.append((open_start, ts))
            open_start = None
    if open_start is not None:
        intervals.append((open_start, float("inf")))
    return intervals


def _label_for_interval(
    start_abs: Optional[float],
    duration: Any,
    sc: list[tuple[float, float]],
    vsc: list[tuple[float, float]],
) -> str:
    if start_abs is None:
        return "GREEN"
    end_abs = start_abs + float(duration) if duration is not None else start_abs + 120.0

    def overlaps(intervals: list[tuple[float, float]]) -> bool:
        return any(s < end_abs and e > start_abs for s, e in intervals)

    if overlaps(sc):
        return "SC"
    if overlaps(vsc):
        return "VSC"
    return "GREEN"
