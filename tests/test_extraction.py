"""Extraction tests: leakage (the most important test in the repo), determinism,
type quota, and exclusion rules."""

from __future__ import annotations

from collections import Counter

from boxbox.data.schemas import LapRecord, PitStop, RaceData, Weather
from boxbox.extract.decision_points import (
    _Candidate,
    apply_type_quota,
    build_state,
    extract_decision_points,
    truncate_race,
)

PIT_LOSS = 20.0


def make_candidates(dp_type: str, n: int) -> list[_Candidate]:
    return [
        _Candidate(
            driver=f"D{i:02d}",
            lap=10 + i,
            dp_type=dp_type,
            trigger="test",
            relevant_gap_s=float(i),
        )
        for i in range(n)
    ]


def test_leakage_states_identical_without_future_laps(race, extraction_cfg):
    """Deleting every lap after the decision lap must not change a single field."""
    dps = extract_decision_points(race, PIT_LOSS, extraction_cfg)
    assert dps, "synthetic race must yield decision points"
    for dp in dps:
        truncated = truncate_race(race, dp.lap)
        state_truncated = build_state(truncated, dp.driver, dp.lap, PIT_LOSS, extraction_cfg)
        assert state_truncated is not None
        assert (
            state_truncated.model_dump() == dp.state.model_dump()
        ), f"{dp.dp_id}: state changed when future laps were removed"


def test_leakage_no_future_lap_times_in_state(race, extraction_cfg):
    """The focal car's lap-t time must never appear among the last lap times."""
    dps = extract_decision_points(race, PIT_LOSS, extraction_cfg)
    for dp in dps:
        lap_t = next(
            (r.lap_time_s for r in race.laps if r.driver == dp.driver and r.lap_number == dp.lap),
            None,
        )
        if lap_t is not None:
            assert lap_t not in dp.state.focal.last_lap_times_s


def test_determinism(race, extraction_cfg):
    a = extract_decision_points(race, PIT_LOSS, extraction_cfg)
    b = extract_decision_points(race, PIT_LOSS, extraction_cfg)
    assert [dp.model_dump() for dp in a] == [dp.model_dump() for dp in b]


def test_quota_balanced_when_all_types_plentiful():
    pool = make_candidates("A", 10) + make_candidates("B", 10) + make_candidates("C", 10)
    picked = apply_type_quota(pool, cap=18, target=6)
    assert Counter(c.dp_type for c in picked) == {"A": 6, "B": 6, "C": 6}


def test_quota_redistributes_unused_slots_to_b_first():
    pool = make_candidates("B", 18) + make_candidates("C", 8)  # no Type A available
    picked = apply_type_quota(pool, cap=18, target=6)
    assert Counter(c.dp_type for c in picked) == {"B": 12, "C": 6}


def test_quota_redistributes_to_c_before_a():
    pool = make_candidates("A", 10) + make_candidates("B", 2) + make_candidates("C", 10)
    picked = apply_type_quota(pool, cap=18, target=6)
    # B is short by 4; C absorbs all 4 before A gets any
    assert Counter(c.dp_type for c in picked) == {"A": 6, "B": 2, "C": 10}


def test_quota_keeps_closest_battles_within_type():
    pool = make_candidates("A", 10) + make_candidates("B", 10) + make_candidates("C", 10)
    picked = apply_type_quota(pool, cap=18, target=6)
    for dp_type in "ABC":
        kept_gaps = sorted(c.relevant_gap_s for c in picked if c.dp_type == dp_type)
        assert kept_gaps == [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]


def test_quota_keeps_everything_under_cap():
    pool = make_candidates("A", 2) + make_candidates("B", 3) + make_candidates("C", 1)
    picked = apply_type_quota(pool, cap=18, target=6)
    assert len(picked) == 6


def test_count_bounds_respect_quota(race, extraction_cfg):
    dps = extract_decision_points(race, PIT_LOSS, extraction_cfg)
    cap = int(extraction_cfg["max_dp_per_race"])
    target = int(extraction_cfg["quota_per_type"])
    assert 1 <= len(dps) <= cap
    # dedupe: at most one DP per (driver, lap)
    keys = [(dp.driver, dp.lap) for dp in dps]
    assert len(keys) == len(set(keys))

    # per-type availability with the cap lifted, then the expected quota allocation
    uncapped = {**extraction_cfg, "max_dp_per_race": 10_000, "quota_per_type": 10_000}
    avail = Counter(dp.dp_type for dp in extract_decision_points(race, PIT_LOSS, uncapped))
    take = {t: min(target, avail.get(t, 0)) for t in "ABC"}
    leftover = min(cap, sum(avail.values())) - sum(take.values())
    for t in ("B", "C", "A"):
        extra = min(leftover, avail.get(t, 0) - take[t])
        take[t] += extra
        leftover -= extra
    got = Counter(dp.dp_type for dp in dps)
    assert {t: got.get(t, 0) for t in "ABC"} == take


def test_exclusion_windows(race, extraction_cfg):
    dps = extract_decision_points(race, PIT_LOSS, extraction_cfg)
    first = int(extraction_cfg["exclude"]["first_laps"])
    last = int(extraction_cfg["exclude"]["last_laps"])
    for dp in dps:
        assert dp.lap > first
        assert dp.lap <= race.total_laps - last


def test_sc_produces_type_b(race, extraction_cfg):
    """The synthetic SC on lap 9 must produce Type B points at lap 9."""
    dps = extract_decision_points(race, PIT_LOSS, extraction_cfg)
    type_b = [dp for dp in dps if dp.dp_type == "B"]
    assert type_b and all(dp.lap == 9 for dp in type_b)
    assert all(dp.state.track_status == "SC" for dp in type_b)


def three_car_race(gap2: float, gap3: float) -> RaceData:
    """P1 ('PIT') stops on lap 10; 'ADJ' runs gap2 behind P1, 'FAR' gap3 behind P1.

    Constant 90s pace keeps the running order PIT > ADJ > FAR until the stop,
    so at the end of lap 9 ADJ is +-1 position from PIT and FAR is 2 away.
    """
    total = 20
    laps: list[LapRecord] = []
    for drv, offset in (("PIT", 0.0), ("ADJ", gap2), ("FAR", gap3)):
        clock = offset
        age = 0
        compound = "MEDIUM"
        for n in range(1, total + 1):
            age += 1
            lap_time = 90.0
            pit_in = drv == "PIT" and n == 10
            pit_out = drv == "PIT" and n == 11
            if pit_in:
                lap_time += 5.0
            if pit_out:
                lap_time += 12.0
            start = clock
            clock += lap_time
            laps.append(
                LapRecord(
                    driver=drv,
                    team="T",
                    lap_number=n,
                    lap_time_s=lap_time,
                    start_time_s=start,
                    end_time_s=clock,
                    compound=compound,
                    tyre_age=age,
                    stint=1 if n <= 10 or drv != "PIT" else 2,
                    position=None,
                    pit_in=pit_in,
                    pit_out=pit_out,
                    track_status="GREEN",
                )
            )
            if pit_in:
                compound = "HARD"
                age = 0
    by_lap: dict[int, list[LapRecord]] = {}
    for r in laps:
        by_lap.setdefault(r.lap_number, []).append(r)
    for recs in by_lap.values():
        recs.sort(key=lambda r: r.end_time_s)
        for pos, r in enumerate(recs, start=1):
            r.position = pos
    return RaceData(
        race_id="2099-threecar",
        season=2099,
        track="Threeville",
        total_laps=total,
        weather=Weather(rain=False),
        laps=laps,
        pit_stops=[PitStop(driver="PIT", lap=10, old_compound="MEDIUM", new_compound="HARD")],
        classified=["PIT", "ADJ", "FAR"],
        teams={d: "T" for d in ("PIT", "ADJ", "FAR")},
    )


def test_type_c_requires_adjacent_position(extraction_cfg):
    """Both cars are within 3.5s of the stopping car, but only the +-1-position
    car may get a Type C point."""
    race = three_car_race(gap2=2.0, gap3=3.0)
    dps = extract_decision_points(race, PIT_LOSS, extraction_cfg)
    type_c = [dp for dp in dps if dp.dp_type == "C"]
    assert [(dp.driver, dp.lap) for dp in type_c] == [("ADJ", 11)]


def test_type_c_requires_gap_threshold(extraction_cfg):
    """An adjacent car outside the 3.5s threshold must not trigger Type C."""
    race = three_car_race(gap2=4.0, gap3=8.0)
    dps = extract_decision_points(race, PIT_LOSS, extraction_cfg)
    assert not [dp for dp in dps if dp.dp_type == "C"]


def test_team_action_matches_real_stop(race, extraction_cfg):
    """A DP on a driver's actual in-lap must carry team_action PIT + new compound."""
    dps = extract_decision_points(race, PIT_LOSS, extraction_cfg)
    stop_laps = {(s.driver, s.lap): s for s in race.pit_stops}
    on_stop = [dp for dp in dps if (dp.driver, dp.lap) in stop_laps]
    for dp in on_stop:
        assert dp.team_action == "PIT"
        assert dp.team_compound == stop_laps[(dp.driver, dp.lap)].new_compound
    off_stop = [dp for dp in dps if (dp.driver, dp.lap) not in stop_laps]
    for dp in off_stop:
        assert dp.team_action == "STAY"
