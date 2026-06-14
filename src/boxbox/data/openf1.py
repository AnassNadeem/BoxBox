"""OpenF1 REST client (https://api.openf1.org/v1) + fallback ingestion to RaceData.

Used two ways:
1. Fallback ingestion when FastF1 cannot load a race (ingest_openf1).
2. Live polling source for the Sunday live runner (OpenF1Client used directly).

Historic free-tier data needs no auth. A paid OpenF1 subscription authenticates via
OAuth2 password grant (username+password -> 1h bearer token, see
https://openf1.org/auth.html); OpenF1Auth manages and auto-refreshes that token so a
~90 min live session never straddles a dead token. All times are normalized to seconds
relative to the earliest lap start we see, so downstream gap math matches the FastF1 path.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from typing import Any, Callable, Optional

import httpx

from boxbox.data.schemas import (
    LapRecord,
    RaceData,
    Weather,
)

log = logging.getLogger(__name__)

BASE_URL = "https://api.openf1.org/v1"
TOKEN_URL = "https://api.openf1.org/token"
# Token lives 3600s; refresh once we are within this margin of expiry. 600s => refresh
# at ~50 min, comfortably before the 60 min expiry and inside a ~90 min race.
DEFAULT_REFRESH_MARGIN_S = 600.0
_COMPOUNDS = {"SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"}


class OpenF1AuthError(RuntimeError):
    """Raised when token acquisition fails (bad creds, endpoint error, malformed body)."""


class OpenF1Auth:
    """OAuth2 password-grant token manager for OpenF1's paid tier.

    token() always returns a currently-valid bearer token, transparently refetching
    when the cached token is missing or within ``refresh_margin_s`` of expiry. The
    ``clock`` and ``client`` seams exist so the refresh-before-expiry behaviour can be
    tested deterministically without sleeping an hour or hitting the network.
    """

    def __init__(
        self,
        username: str,
        password: str,
        token_url: str = TOKEN_URL,
        refresh_margin_s: float = DEFAULT_REFRESH_MARGIN_S,
        timeout: float = 30.0,
        clock: Callable[[], float] = time.time,
        client: Any | None = None,
    ):
        if not username or not password:
            raise OpenF1AuthError("OpenF1 username/password missing")
        self._username = username
        self._password = password
        self._token_url = token_url
        self._refresh_margin_s = refresh_margin_s
        self._clock = clock
        self._client = client if client is not None else httpx.Client(timeout=timeout)
        self._owns_client = client is None
        self._access_token: Optional[str] = None
        self._expires_at: float = 0.0
        self.refresh_count = 0

    def _needs_refresh(self) -> bool:
        return self._access_token is None or self._clock() >= (
            self._expires_at - self._refresh_margin_s
        )

    def token(self) -> str:
        if self._needs_refresh():
            self._fetch()
        assert self._access_token is not None
        return self._access_token

    def invalidate(self) -> None:
        """Drop the cached token so the next token() refetches (used on a 401)."""
        self._access_token = None

    def _fetch(self) -> None:
        resp = self._client.post(
            self._token_url,
            data={"username": self._username, "password": self._password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        status = resp.status_code
        if status != 200:
            body = (resp.text or "")[:300]
            raise OpenF1AuthError(f"token fetch failed: HTTP {status}: {body}")
        payload = resp.json()
        tok = payload.get("access_token")
        if not tok:
            raise OpenF1AuthError(f"token response missing access_token: {payload}")
        expires_in = float(payload.get("expires_in") or 3600)
        self._access_token = str(tok)
        self._expires_at = self._clock() + expires_in
        self.refresh_count += 1
        log.info(
            "OpenF1 token acquired (refresh #%d); expires in %.0fs", self.refresh_count, expires_in
        )

    @property
    def expires_at(self) -> float:
        return self._expires_at

    def expires_in(self) -> float:
        return self._expires_at - self._clock()

    def close(self) -> None:
        if self._owns_client:
            self._client.close()


def auth_from_env() -> Optional[OpenF1Auth]:
    """Build an OpenF1Auth from OPENF1_USERNAME/OPENF1_PASSWORD, or None if unset.

    None means anonymous free-tier access (historic ingestion still works)."""
    user = os.environ.get("OPENF1_USERNAME")
    pw = os.environ.get("OPENF1_PASSWORD")
    if user and pw:
        return OpenF1Auth(user, pw)
    return None


def _parse_date_s(value: Any) -> Optional[float]:
    """OpenF1 ISO-8601 date -> epoch seconds (float), None-safe."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


class OpenF1Client:
    """Thin retrying GET client for OpenF1.

    Pass ``auth`` (an OpenF1Auth) to use the paid tier: every GET then carries a fresh
    ``Authorization: Bearer <token>`` header, and a 401 invalidates the cached token so
    the retry refetches. With ``auth=None`` the client is anonymous (free historic tier).
    """

    def __init__(
        self,
        base_url: str = BASE_URL,
        timeout: float = 30.0,
        retries: int = 3,
        auth: Optional[OpenF1Auth] = None,
    ):
        self.base_url = base_url
        self.retries = retries
        self.auth = auth
        self._client = httpx.Client(timeout=timeout)

    def get(self, endpoint: str, **params: Any) -> list[dict[str, Any]]:
        url = f"{self.base_url}/{endpoint}"
        last_exc: Exception | None = None
        for attempt in range(self.retries):
            try:
                headers: dict[str, str] = {}
                if self.auth is not None:
                    headers["Authorization"] = f"Bearer {self.auth.token()}"
                resp = self._client.get(url, params=params, headers=headers)
                if resp.status_code == 401 and self.auth is not None:
                    # token may have just expired; drop it and retry with a fresh one
                    self.auth.invalidate()
                if resp.status_code == 429 or resp.status_code == 401 or resp.status_code >= 500:
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
        if self.auth is not None:
            self.auth.close()


def _is_race(session: dict[str, Any]) -> bool:
    return (
        str(session.get("session_name", "")).lower() == "race"
        or str(session.get("session_type", "")).lower() == "race"
    )


def _matches_event(session: dict[str, Any], frag: str) -> bool:
    haystack = " ".join(
        str(session.get(k, ""))
        for k in ("country_name", "location", "circuit_short_name", "meeting_name")
    ).lower()
    return frag in haystack


def find_race_session(
    client: OpenF1Client, year: int, event: str, live: bool = False
) -> dict[str, Any]:
    """Resolve (year, event-name fragment) to the OpenF1 race session row.

    With ``live=True`` we first consult ``session_key=latest`` — the session OpenF1 is
    currently serving — and return it when it is the Race for this event (this is what is
    actually running on race day, and avoids ambiguity with prior sessions). We always
    fall back to the scheduled-session lookup, which also lists upcoming races, so this
    works both during the race and earlier on race morning before timing data flows.
    """
    frag = event.lower()

    if live:
        try:
            for s in client.get("sessions", session_key="latest"):
                if _is_race(s) and _matches_event(s, frag):
                    log.info(
                        "find_race_session: using live latest session %s", s.get("session_key")
                    )
                    return s
        except Exception as exc:  # latest may be unavailable pre-session; fall through
            log.warning("find_race_session: latest lookup failed (%s); using schedule", exc)

    # Scheduled lookup. Some rows carry session_type but not session_name pre-event, so
    # match on either rather than filtering server-side on session_name only.
    sessions = client.get("sessions", year=year)
    matches = [s for s in sessions if _is_race(s) and _matches_event(s, frag)]
    if matches:
        if len(matches) > 1:
            # Ambiguous fragment (e.g. "spain" matches both Barcelona-Catalunya and the
            # Madrid round in 2026). Pick the race nearest in time to now, which on a race
            # weekend is the one we actually want, rather than blindly the last-listed.
            now = time.time()

            def _dist(s: dict[str, Any]) -> float:
                d = _parse_date_s(s.get("date_start"))
                return abs(d - now) if d is not None else float("inf")

            matches.sort(key=_dist)
            log.warning(
                "find_race_session: %d races matched %r; picked nearest-dated session %s (%s)",
                len(matches),
                frag,
                matches[0].get("session_key"),
                matches[0].get("date_start"),
            )
        return matches[0]
    raise RuntimeError(f"No OpenF1 race session found for {year} '{event}' (live={live})")


def ingest_openf1(
    race_id: str,
    year: int,
    event: str,
    client: Optional[OpenF1Client] = None,
    auth: Optional[OpenF1Auth] = None,
    live: bool = False,
    total_laps_override: Optional[int] = None,
) -> RaceData:
    """Fallback / live ingestion: build the same RaceData shape FastF1 would give us.

    Pass an existing ``client`` (the live loop does, to reuse one authed bearer token
    across polls). When no client is given we build one, using ``auth`` if supplied else
    auto-detecting paid creds from the environment. ``total_laps_override`` sets the
    scheduled race distance: during a LIVE race max-lap-seen is only the current lap, so
    without it the loop would treat the race as already finished."""
    own_client = client is None
    if client is None:
        client = OpenF1Client(auth=auth if auth is not None else auth_from_env())
    try:
        session = find_race_session(client, year, event, live=live)
        key = session["session_key"]

        drivers = {d["driver_number"]: d for d in client.get("drivers", session_key=key)}
        laps_raw = client.get("laps", session_key=key)
        stints_raw = client.get("stints", session_key=key)
        pits_raw = client.get("pit", session_key=key)
        rc_raw = client.get("race_control", session_key=key)
        weather_raw = client.get("weather", session_key=key)
    finally:
        if own_client:
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

    laps_seen = max((r.lap_number for r in records), default=0)
    # During a live race laps_seen is just the current lap; prefer the scheduled distance.
    total_laps = max(laps_seen, total_laps_override or 0)
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
