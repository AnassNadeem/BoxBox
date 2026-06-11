"""Shared fixtures: a deterministic synthetic race so tests never need network/data."""

from __future__ import annotations

import math

import pytest

from boxbox.data.ingest import derive_pit_stops
from boxbox.data.schemas import LapRecord, RaceData, Weather

DRIVERS = [
    ("AAA", "Team Red", 90.0, 12),
    ("BBB", "Team Red", 90.2, 13),
    ("CCC", "Team Blue", 90.4, 14),
    ("DDD", "Team Blue", 90.6, 15),
    ("EEE", "Team Green", 90.8, 16),
    ("FFF", "Team Green", 91.0, 17),
]
TOTAL_LAPS = 30
SC_LAPS = {9, 10}  # safety car window
DEG_PER_LAP = 0.08
FUEL_PER_LAP = -0.02
PIT_IN_EXTRA = 5.0
PIT_OUT_EXTRA = 12.0


def synthetic_race(race_id: str = "2099-testville") -> RaceData:
    laps: list[LapRecord] = []
    for d_idx, (driver, team, base, stop_lap) in enumerate(DRIVERS):
        clock = d_idx * 1.5  # grid stagger
        age = 0
        compound = "MEDIUM"
        for n in range(1, TOTAL_LAPS + 1):
            age += 1
            wobble = 0.15 * math.sin(n * 1.7 + d_idx)  # deterministic noise
            lap_time = base + DEG_PER_LAP * age + FUEL_PER_LAP * n + wobble
            status = "SC" if n in SC_LAPS else "GREEN"
            if status == "SC":
                lap_time = base * 1.4
            pit_in = n == stop_lap
            pit_out = n == stop_lap + 1
            if pit_in:
                lap_time += PIT_IN_EXTRA
            if pit_out:
                lap_time += PIT_OUT_EXTRA
            start = clock
            clock += lap_time
            laps.append(
                LapRecord(
                    driver=driver,
                    team=team,
                    lap_number=n,
                    lap_time_s=round(lap_time, 3),
                    start_time_s=round(start, 3),
                    end_time_s=round(clock, 3),
                    compound=compound,
                    tyre_age=age,
                    stint=1 if n <= stop_lap else 2,
                    position=None,  # filled by ranking below
                    pit_in=pit_in,
                    pit_out=pit_out,
                    track_status=status,
                    is_accurate=status == "GREEN" and not (pit_in or pit_out),
                )
            )
            if pit_in:
                compound = "HARD"
                age = 0

    # rank positions per lap by completion time
    by_lap: dict[int, list[LapRecord]] = {}
    for r in laps:
        by_lap.setdefault(r.lap_number, []).append(r)
    for recs in by_lap.values():
        recs.sort(key=lambda r: r.end_time_s)
        for pos, r in enumerate(recs, start=1):
            r.position = pos

    return RaceData(
        race_id=race_id,
        season=2099,
        track="Testville",
        total_laps=TOTAL_LAPS,
        weather=Weather(air_temp_c=25.0, track_temp_c=40.0, rain=False),
        laps=laps,
        pit_stops=derive_pit_stops(laps),
        classified=[d[0] for d in DRIVERS],
        retirements={},
        teams={d[0]: d[1] for d in DRIVERS},
        source="fastf1",
    )


@pytest.fixture(scope="session")
def race() -> RaceData:
    return synthetic_race()


@pytest.fixture(scope="session")
def extraction_cfg() -> dict:
    from boxbox.config import load_config

    return load_config("extraction")


@pytest.fixture(scope="session")
def run_cfg() -> dict:
    from boxbox.config import load_config

    return load_config("run")
