"""Extraction tests: leakage (the most important test in the repo), determinism,
count bounds, and exclusion rules."""

from __future__ import annotations

from boxbox.extract.decision_points import (
    build_state,
    extract_decision_points,
    truncate_race,
)

PIT_LOSS = 20.0


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


def test_count_bounds(race, extraction_cfg):
    dps = extract_decision_points(race, PIT_LOSS, extraction_cfg)
    cap = int(extraction_cfg["max_dp_per_race"])
    assert 1 <= len(dps) <= cap
    # dedupe: at most one DP per (driver, lap)
    keys = [(dp.driver, dp.lap) for dp in dps]
    assert len(keys) == len(set(keys))


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
