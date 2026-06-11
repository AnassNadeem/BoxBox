"""Simulator sanity: degradation monotonicity, pit-loss arithmetic, optimal dominance."""

from __future__ import annotations

import pytest

from boxbox.data.schemas import LapRecord, RaceData, Weather
from boxbox.extract.decision_points import extract_decision_points
from boxbox.sim.degradation import DegradationModel, estimate_pit_loss
from boxbox.sim.optimal import evaluate_decision_point
from boxbox.sim.race_sim import RaceSimulator

PIT_LOSS = 20.0


@pytest.fixture(scope="module")
def deg(race) -> DegradationModel:
    return DegradationModel(race)


def test_more_tyre_age_is_slower(deg):
    fresh = deg.predict("AAA", "MEDIUM", tyre_age=2, lap_number=10)
    worn = deg.predict("AAA", "MEDIUM", tyre_age=10, lap_number=10)
    assert worn > fresh


def test_measured_pit_loss_close_to_constructed(race):
    """conftest builds stops as +5s in-lap and +12s out-lap => ~17s true loss."""
    loss, factor, note = estimate_pit_loss(race)
    assert 12.0 <= loss <= 22.0, note
    assert 0.2 <= factor <= 1.0


def flat_race() -> RaceData:
    """Constant 90s laps, one driver, no stops: isolates pit-loss arithmetic."""
    laps = []
    clock = 0.0
    for n in range(1, 21):
        start = clock
        clock += 90.0
        laps.append(
            LapRecord(
                driver="XXX",
                team="T",
                lap_number=n,
                lap_time_s=90.0,
                start_time_s=start,
                end_time_s=clock,
                compound="MEDIUM",
                tyre_age=n,
                stint=1,
                position=1,
                track_status="GREEN",
            )
        )
    return RaceData(
        race_id="2099-flat",
        season=2099,
        track="Flatville",
        total_laps=20,
        weather=Weather(rain=False),
        laps=laps,
        classified=["XXX"],
        teams={"XXX": "T"},
    )


def test_adding_a_stop_adds_about_pit_loss():
    race = flat_race()
    deg = DegradationModel(race)
    sim = RaceSimulator(race, deg, pit_loss_s=PIT_LOSS, sc_pit_factor=0.55)
    no_stop = sim.rollout("XXX", 5, "MEDIUM", 4, [])
    one_stop = sim.rollout("XXX", 5, "MEDIUM", 4, [(10, "MEDIUM")])
    diff = one_stop - no_stop
    # flat pace means the fresh set gives ~0 benefit; diff must be ~pit loss
    assert diff == pytest.approx(PIT_LOSS, abs=2.0)


def test_optimal_never_worse_than_team_or_any_action(race, extraction_cfg):
    deg = DegradationModel(race)
    sim = RaceSimulator(race, deg, pit_loss_s=PIT_LOSS, sc_pit_factor=0.55)
    dps = extract_decision_points(race, PIT_LOSS, extraction_cfg)
    assert dps
    for dp in dps:
        ev = evaluate_decision_point(dp, sim)
        tol = 1e-6
        assert ev.sim_optimal_s <= ev.sim_team_s + tol
        if ev.sim_stay_s is not None:
            assert ev.sim_optimal_s <= ev.sim_stay_s + tol
        for value in ev.sim_pit_s.values():
            assert ev.sim_optimal_s <= value + tol


def test_exante_optimal_never_better_than_hindsight(race, extraction_cfg):
    """The ex-ante plan, valued in the realized race, can never beat the
    hindsight optimum (which minimizes exactly that realized value)."""
    deg = DegradationModel(race)
    sim = RaceSimulator(race, deg, pit_loss_s=PIT_LOSS, sc_pit_factor=0.55)
    dps = extract_decision_points(race, PIT_LOSS, extraction_cfg)
    assert dps
    for dp in dps:
        ev = evaluate_decision_point(dp, sim)
        assert ev.sim_exante_optimal_s >= ev.sim_optimal_s - 1e-6


def test_exante_rollout_assumes_green_future(race):
    """With the SC on laps 9-10 unknown, the ex-ante rollout from lap 8 must be
    faster than the hindsight rollout that charges the slow SC laps."""
    deg = DegradationModel(race)
    sim = RaceSimulator(race, deg, pit_loss_s=PIT_LOSS, sc_pit_factor=0.55)
    hindsight = sim.rollout("AAA", 8, "MEDIUM", 7, [])
    exante = sim.rollout("AAA", 8, "MEDIUM", 7, [], assume_green_after=8)
    assert exante < hindsight


def test_exante_rollout_keeps_current_lap_status(race):
    """A stop on the decision lap itself (SC lap 9) keeps the SC pit discount in
    ex-ante mode: the current track status is known, only the future is not."""
    deg = DegradationModel(race)
    sim = RaceSimulator(race, deg, pit_loss_s=PIT_LOSS, sc_pit_factor=0.55)
    no_stop = sim.rollout("AAA", 9, "MEDIUM", 8, [], assume_green_after=9)
    stop_now = sim.rollout("AAA", 9, "MEDIUM", 8, [(9, "HARD")], assume_green_after=9)
    added = stop_now - no_stop
    # full pit loss would be ~20s; the SC discount caps the addition well below it
    assert added < PIT_LOSS * 0.55 + 2.0


def test_sc_laps_use_field_median(race):
    """Rollout over the synthetic SC laps (9-10) must charge the slow SC pace."""
    deg = DegradationModel(race)
    sim = RaceSimulator(race, deg, pit_loss_s=PIT_LOSS, sc_pit_factor=0.55)
    with_sc = sim.rollout("AAA", 8, "MEDIUM", 7, [])
    green_estimate = sum(
        deg.predict("AAA", "MEDIUM", 7 + i, 8 + i) for i in range(race.total_laps - 8 + 1)
    )
    assert with_sc > green_estimate  # SC laps at ~1.4x pace dominate
