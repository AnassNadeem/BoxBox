"""FastF1 ingestion: load a race session and normalize it into RaceData.

The normalized JSON is persisted to data/processed/<race_id>.json so every
downstream stage (extraction, simulation, replay) runs offline and
deterministically from the same snapshot.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from boxbox.data.schemas import (
    Compound,
    LapRecord,
    PitStop,
    RaceData,
    TrackStatusLabel,
    Weather,
)

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
CACHE_DIR = DATA_DIR / "fastf1_cache"
PROCESSED_DIR = DATA_DIR / "processed"

_COMPOUNDS = {"SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"}


def _compound(raw: Any) -> Compound:
    s = str(raw).upper() if raw is not None and not pd.isna(raw) else ""
    return s if s in _COMPOUNDS else "UNKNOWN"  # type: ignore[return-value]


def _status_label(raw: Any) -> TrackStatusLabel:
    """Collapse FastF1's concatenated status codes ('2645') to one label.

    Priority: red > SC > VSC > yellow > green. Codes: 1 green, 2 yellow,
    4 SC, 5 red, 6 VSC deployed, 7 VSC ending.
    """
    s = "" if raw is None or (isinstance(raw, float) and pd.isna(raw)) else str(raw)
    if "5" in s:
        return "RED"
    if "4" in s:
        return "SC"
    if "6" in s or "7" in s:
        return "VSC"
    if "2" in s:
        return "YELLOW"
    return "GREEN"


def _td_s(value: Any) -> Optional[float]:
    """Timedelta-ish -> float seconds, NaT/None -> None."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        return None
    return float(pd.Timedelta(value).total_seconds())


def _int_or_none(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def ingest_fastf1(race_id: str, year: int, event: str) -> RaceData:
    """Load <year> <event> race via FastF1 and normalize to RaceData."""
    import fastf1  # local import: keep module importable without network/cache side effects

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE_DIR))
    for name in ("fastf1", "fastf1.core", "fastf1.req", "fastf1.api"):
        logging.getLogger(name).setLevel(logging.WARNING)

    session = fastf1.get_session(year, event, "R")
    session.load(laps=True, telemetry=False, weather=True, messages=True)

    laps_df = session.laps
    if laps_df is None or len(laps_df) == 0:
        raise RuntimeError(f"FastF1 returned no laps for {race_id}")

    records: list[LapRecord] = []
    teams: dict[str, str] = {}
    for row in laps_df.itertuples():
        driver = str(getattr(row, "Driver", "") or "")
        lap_number = _int_or_none(getattr(row, "LapNumber", None))
        if not driver or lap_number is None:
            continue
        team = str(getattr(row, "Team", "") or "")
        if team:
            teams.setdefault(driver, team)
        records.append(
            LapRecord(
                driver=driver,
                team=team,
                lap_number=lap_number,
                lap_time_s=_td_s(getattr(row, "LapTime", None)),
                start_time_s=_td_s(getattr(row, "LapStartTime", None)),
                end_time_s=_td_s(getattr(row, "Time", None)),
                compound=_compound(getattr(row, "Compound", None)),
                tyre_age=_int_or_none(getattr(row, "TyreLife", None)),
                stint=_int_or_none(getattr(row, "Stint", None)),
                position=_int_or_none(getattr(row, "Position", None)),
                pit_in=_td_s(getattr(row, "PitInTime", None)) is not None,
                pit_out=_td_s(getattr(row, "PitOutTime", None)) is not None,
                track_status=_status_label(getattr(row, "TrackStatus", None)),
                is_accurate=bool(getattr(row, "IsAccurate", False)),
            )
        )

    _fill_missing_positions(records)
    _mark_rain_laps(session, records)

    total_laps = int(getattr(session, "total_laps", 0) or 0)
    if total_laps <= 0:
        total_laps = max(r.lap_number for r in records)

    classified, retirements = _classification(session, records, total_laps)

    weather = _weather(session)

    race = RaceData(
        race_id=race_id,
        season=year,
        track=str(session.event.get("Location", event)),
        total_laps=total_laps,
        weather=weather,
        laps=records,
        pit_stops=derive_pit_stops(records),
        classified=classified,
        retirements=retirements,
        teams=teams,
        source="fastf1",
    )
    return race


def _fill_missing_positions(records: list[LapRecord]) -> None:
    """Fill missing per-lap positions by ranking cars on each lap by completion time."""
    by_lap: dict[int, list[LapRecord]] = {}
    for r in records:
        by_lap.setdefault(r.lap_number, []).append(r)
    for lap_records in by_lap.values():
        if all(r.position is not None for r in lap_records):
            continue
        timed = [r for r in lap_records if r.end_time_s is not None]
        timed.sort(key=lambda r: r.end_time_s)  # type: ignore[arg-type,return-value]
        for rank, r in enumerate(timed, start=1):
            if r.position is None:
                r.position = rank


def _mark_rain_laps(session: Any, records: list[LapRecord]) -> None:
    """Flag laps whose time window overlaps recorded rainfall (slicks-on-damp ruins fits)."""
    try:
        wd = session.weather_data
        if wd is None or len(wd) == 0 or not wd["Rainfall"].any():
            return
        rain_times = [
            float(pd.Timedelta(t).total_seconds())
            for t, raining in zip(wd["Time"], wd["Rainfall"])
            if bool(raining)
        ]
    except Exception as exc:
        log.warning("Rain marking skipped (%s)", exc)
        return
    if not rain_times:
        return
    # weather samples are ~1/min; pad the window accordingly
    for rec in records:
        if rec.start_time_s is None or rec.end_time_s is None:
            continue
        if any(rec.start_time_s - 60.0 <= t <= rec.end_time_s for t in rain_times):
            rec.rain_affected = True


def _classification(
    session: Any, records: list[LapRecord], total_laps: int
) -> tuple[list[str], dict[str, int]]:
    """Classified drivers + retirements (driver -> last completed lap)."""
    last_lap: dict[str, int] = {}
    for r in records:
        last_lap[r.driver] = max(last_lap.get(r.driver, 0), r.lap_number)

    classified: list[str] = []
    try:
        results = session.results
        for _, row in results.iterrows():
            abbrev = str(row.get("Abbreviation", "") or "")
            cp = str(row.get("ClassifiedPosition", "") or "")
            if abbrev and cp.isdigit():
                classified.append(abbrev)
    except Exception as exc:  # results occasionally unavailable
        log.warning("No usable session.results (%s); falling back to lap-count heuristic", exc)
    if not classified:
        classified = [d for d, n in last_lap.items() if n >= 0.9 * total_laps]

    retirements = {d: n for d, n in last_lap.items() if d not in classified}
    return classified, retirements


def _weather(session: Any) -> Weather:
    try:
        wd = session.weather_data
        if wd is None or len(wd) == 0:
            return Weather()
        return Weather(
            air_temp_c=round(float(wd["AirTemp"].mean()), 1),
            track_temp_c=round(float(wd["TrackTemp"].mean()), 1),
            rain=bool(wd["Rainfall"].any()),
        )
    except Exception as exc:
        log.warning("No weather data (%s)", exc)
        return Weather()


def derive_pit_stops(records: list[LapRecord]) -> list[PitStop]:
    """Pit stops from lap records: an in-lap, with the next lap's compound as the new one."""
    by_driver: dict[str, dict[int, LapRecord]] = {}
    for r in records:
        by_driver.setdefault(r.driver, {})[r.lap_number] = r

    stops: list[PitStop] = []
    for driver, lap_map in by_driver.items():
        for n, rec in sorted(lap_map.items()):
            if not rec.pit_in:
                continue
            nxt = lap_map.get(n + 1)
            stops.append(
                PitStop(
                    driver=driver,
                    lap=n,
                    old_compound=rec.compound,
                    new_compound=nxt.compound if nxt is not None else "UNKNOWN",
                    under_sc=rec.track_status in ("SC", "VSC"),
                )
            )
    stops.sort(key=lambda s: (s.lap, s.driver))
    return stops


# --------------------------------------------------------------------------- persistence


def processed_path(race_id: str) -> Path:
    return PROCESSED_DIR / f"{race_id}.json"


def save_race(race: RaceData) -> Path:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    path = processed_path(race.race_id)
    path.write_text(race.model_dump_json(), encoding="utf-8")
    return path


def load_race(race_id: str) -> RaceData:
    path = processed_path(race_id)
    if not path.exists():
        raise FileNotFoundError(
            f"No processed data for {race_id}; run scripts/build_dataset.py first"
        )
    return RaceData.model_validate_json(path.read_text(encoding="utf-8"))


def ingest_race(race_id: str, year: int, event: str, force: bool = False) -> RaceData:
    """Ingest one race: FastF1 first, OpenF1 fallback. Cached via data/processed/."""
    if not force and processed_path(race_id).exists():
        log.info("%s already processed; skipping (force=True to redo)", race_id)
        return load_race(race_id)
    try:
        race = ingest_fastf1(race_id, year, event)
    except Exception as exc:
        log.warning("FastF1 failed for %s (%s); trying OpenF1 fallback", race_id, exc)
        from boxbox.data.openf1 import ingest_openf1

        race = ingest_openf1(race_id, year, event)
    save_race(race)
    return race
