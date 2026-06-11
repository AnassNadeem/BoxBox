"""Per-call scoring: simulator delta vs hindsight-optimal, plus team-relative metrics."""

from __future__ import annotations

import logging

from boxbox.data.schemas import CallResult, DecisionPoint, RaceData, Score
from boxbox.sim.optimal import DPEvaluation, evaluate_decision_point
from boxbox.sim.race_sim import make_simulator

log = logging.getLogger(__name__)


def evaluate_all(
    dps: list[DecisionPoint], races: dict[str, RaceData], sim_cfg: dict | None = None
) -> dict[str, DPEvaluation]:
    """One simulator evaluation per decision point, keyed by dp_id."""
    sims = {}
    evals: dict[str, DPEvaluation] = {}
    for dp in dps:
        if dp.race_id not in sims:
            sims[dp.race_id], *_ = make_simulator(races[dp.race_id], sim_cfg)
        evals[dp.dp_id] = evaluate_decision_point(dp, sims[dp.race_id])
    return evals


def score_call(dp: DecisionPoint, ev: DPEvaluation, result: CallResult) -> Score:
    base = dict(
        dp_id=dp.dp_id,
        race_id=dp.race_id,
        season=dp.season,
        dp_type=dp.dp_type,
        model_name=result.model_name,
        repeat_index=result.repeat_index,
        sim_optimal_s=round(ev.sim_optimal_s, 3),
        sim_team_s=round(ev.sim_team_s, 3),
        team_action=dp.team_action,
        optimal_action=ev.optimal_action,
        optimal_compound=ev.optimal_compound,
        optimal_stop_lap=ev.optimal_stop_lap,
    )
    if result.invalid or result.decision is None:
        return Score(invalid=True, **base)

    decision = result.decision
    value = ev.value_of(decision.action, decision.compound)
    if value is None:
        return Score(invalid=True, action=decision.action, compound=decision.compound, **base)

    agree_action = decision.action == dp.team_action
    agree_exact = agree_action and (
        decision.action == "STAY" or decision.compound == dp.team_compound
    )
    return Score(
        invalid=False,
        action=decision.action,
        compound=decision.compound,
        sim_model_s=round(value, 3),
        delta_vs_optimal_s=round(value - ev.sim_optimal_s, 3),
        delta_vs_team_s=round(value - ev.sim_team_s, 3),
        beat_team=value < ev.sim_team_s - 1e-9,
        agree_team_action=agree_action,
        agree_team_exact=agree_exact,
        **base,
    )


def score_all(
    dps: list[DecisionPoint],
    results: list[CallResult],
    races: dict[str, RaceData],
    sim_cfg: dict | None = None,
) -> list[Score]:
    dp_by_id = {dp.dp_id: dp for dp in dps}
    evals = evaluate_all(dps, races, sim_cfg)
    scores: list[Score] = []
    for result in results:
        dp = dp_by_id.get(result.dp_id)
        if dp is None:
            log.warning("Result for unknown dp_id %s skipped", result.dp_id)
            continue
        scores.append(score_call(dp, evals[dp.dp_id], result))
    return scores
