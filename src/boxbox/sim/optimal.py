"""Strategy grid search around a decision point -> hindsight optimum + action values.

Candidate space: pit at the end of any lap from t to total_laps-1 onto any
available compound, or no further stop - subject to the two-compound rule in
dry races. STAY at lap t is valued as the best legal plan that does not stop on
lap t (the strategist keeps future flexibility); the team's real call is valued
the same way so that agreement at the decision instant scores as a tie.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from boxbox.data.schemas import (
    DRY_COMPOUNDS,
    WET_COMPOUNDS,
    DecisionPoint,
    StrategyOption,
)
from boxbox.sim.race_sim import RaceSimulator


@dataclass
class DPEvaluation:
    dp_id: str
    sim_optimal_s: float
    optimal_action: str  # "PIT" | "STAY"
    optimal_compound: Optional[str]
    optimal_stop_lap: Optional[int]
    sim_stay_s: Optional[float]  # best legal plan not stopping at lap t
    sim_pit_s: dict[str, float]  # compound -> value of stopping at lap t
    sim_team_s: float
    options: list[StrategyOption]

    def value_of(self, action: str, compound: Optional[str]) -> Optional[float]:
        """Sim value of a model's answer; None if it cannot be evaluated."""
        if action == "STAY":
            return self.sim_stay_s
        if action == "PIT":
            if compound and compound in self.sim_pit_s:
                return self.sim_pit_s[compound]
            if self.sim_pit_s:  # PIT with no/unknown compound: charitable best PIT
                return min(self.sim_pit_s.values())
        return None


def evaluate_decision_point(dp: DecisionPoint, sim: RaceSimulator) -> DPEvaluation:
    race = sim.race
    t = dp.lap
    focal = dp.state.focal
    available = list(focal.compounds_available)
    wet_race = any(c in WET_COMPOUNDS for c in available)
    used_dry = {c for c in focal.compounds_used if c in DRY_COMPOUNDS}

    def legal(plan_compounds: list[str]) -> bool:
        if wet_race:
            return True  # two-compound rule is waived once wet tyres are in play
        return len(used_dry | {c for c in plan_compounds if c in DRY_COMPOUNDS}) >= 2

    def roll(stops: list[tuple[int, str]]) -> float:
        return sim.rollout(focal.driver, t, focal.compound, focal.tyre_age, stops)

    options: list[StrategyOption] = []

    no_stop_legal = legal([])
    options.append(
        StrategyOption(
            stop_lap=None, compound=None, total_time_s=roll([]), legal=no_stop_legal
        )
    )

    last_stop_lap = race.total_laps - 1
    for stop_lap in range(t, last_stop_lap + 1):
        for comp in available:
            options.append(
                StrategyOption(
                    stop_lap=stop_lap,
                    compound=comp,  # type: ignore[arg-type]
                    total_time_s=roll([(stop_lap, comp)]),
                    legal=legal([comp]),
                )
            )

    legal_options = [o for o in options if o.legal]
    if not legal_options:  # degenerate; never expected, but never crash
        legal_options = options
    best = min(legal_options, key=lambda o: o.total_time_s)

    # Value of every immediate action ------------------------------------------------
    stay_candidates = [o for o in legal_options if o.stop_lap is None or o.stop_lap > t]
    sim_stay = min((o.total_time_s for o in stay_candidates), default=None)

    sim_pit: dict[str, float] = {}
    for comp in available:
        candidates = [
            o.total_time_s for o in options if o.stop_lap == t and o.compound == comp and o.legal
        ]
        if candidates:
            sim_pit[comp] = min(candidates)
        else:
            # Illegal as a final stint (e.g. pitting onto the only dry compound used):
            # force the cheapest legalizing second stop.
            second: list[float] = []
            for fix_lap in range(t + 1, last_stop_lap + 1):
                for fix_comp in available:
                    if legal([comp, fix_comp]):
                        second.append(roll([(t, comp), (fix_lap, fix_comp)]))
            if second:
                sim_pit[comp] = min(second)

    # Team's real call, valued at the decision instant --------------------------------
    if dp.team_action == "PIT":
        if dp.team_compound and dp.team_compound in sim_pit:
            sim_team = sim_pit[dp.team_compound]
        elif sim_pit:
            sim_team = min(sim_pit.values())
        else:
            sim_team = best.total_time_s
    else:
        sim_team = sim_stay if sim_stay is not None else best.total_time_s

    return DPEvaluation(
        dp_id=dp.dp_id,
        sim_optimal_s=best.total_time_s,
        optimal_action="PIT" if best.stop_lap == t else "STAY",
        optimal_compound=best.compound if best.stop_lap == t else None,
        optimal_stop_lap=best.stop_lap,
        sim_stay_s=sim_stay,
        sim_pit_s=sim_pit,
        sim_team_s=sim_team,
        options=options,
    )
