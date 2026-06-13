"""Rule-based decision-point extraction (OVERNIGHT_TASK.md section 6).

A DecisionPoint at lap t freezes what a strategist knows entering lap t:
- every numeric field is derived from completed laps <= t-1;
- the only lap-t information used is the track status (real-time knowledge);
- the question posed is "pit at the end of lap t?".

The leakage guarantee is structural: build_state() first truncates the race to
laps <= t and then never reads lap-t fields except track_status, so deleting
all laps > t from the input cannot change any emitted state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from boxbox.data.schemas import (
    DRY_COMPOUNDS,
    WET_COMPOUNDS,
    Compound,
    DecisionPoint,
    FocalCar,
    LapRecord,
    RaceData,
    RaceState,
    RivalInfo,
    TopNRow,
    TrackStatusLabel,
)

_STATUS_PRIORITY = {"RED": 4, "SC": 3, "VSC": 2, "YELLOW": 1, "GREEN": 0}
_TYPE_PRIORITY = {"B": 0, "C": 1, "A": 2}  # lower = kept first (dedupe + redistribution)


class RaceIndex:
    """Lookup structures over a RaceData's lap records."""

    def __init__(self, race: RaceData):
        self.race = race
        self.by_driver: dict[str, dict[int, LapRecord]] = {}
        self.by_lap: dict[int, list[LapRecord]] = {}
        for rec in race.laps:
            self.by_driver.setdefault(rec.driver, {})[rec.lap_number] = rec
            self.by_lap.setdefault(rec.lap_number, []).append(rec)

    def rec(self, driver: str, lap: int) -> Optional[LapRecord]:
        return self.by_driver.get(driver, {}).get(lap)

    def field_status(self, lap: int) -> TrackStatusLabel:
        """Worst track status reported by any car on this lap."""
        best: TrackStatusLabel = "GREEN"
        for rec in self.by_lap.get(lap, []):
            if _STATUS_PRIORITY[rec.track_status] > _STATUS_PRIORITY[best]:
                best = rec.track_status
        return best

    def order_at(self, lap: int) -> list[LapRecord]:
        """Records of this lap sorted by position (cars without position last)."""
        recs = [r for r in self.by_lap.get(lap, []) if r.position is not None]
        recs.sort(key=lambda r: r.position)  # type: ignore[arg-type,return-value]
        return recs


@dataclass
class _Candidate:
    driver: str
    lap: int
    dp_type: str
    trigger: str
    rival_gap_s: Optional[float] = None  # only for Type C
    state: Optional[RaceState] = field(default=None, compare=False)
    relevant_gap_s: float = 9999.0


# ------------------------------------------------------------------ state construction


def truncate_race(race: RaceData, lap: int) -> RaceData:
    """Copy of race with all lap records after `lap` removed (leakage-test helper)."""
    return race.model_copy(
        update={"laps": [r for r in race.laps if r.lap_number <= lap]}, deep=True
    )


def wet_running_near(race: RaceData, t: int, window: int) -> bool:
    """Conditions-only: did the field actually run INTERMEDIATE/WET tyres, or have
    rain-affected laps, within `window` laps of the decision lap t — i.e. on a lap in
    [t-window, t]? The upper bound is t (not t+window), keeping this <= t so it is
    leakage-safe for the offered compound set.

    This replaces the v1 wet test (`weather.rain or any wet lap seen so far`), which
    over-offered INTER in two ways the audit found: the race-level Rainfall.any() flag
    (Miami: 3 stray pings on a 42C dry race) and a latch that stayed on for the rest of
    the race after one early damp lap (Canada: damp laps 1-3 leaking into a dry race).
    """
    lo = t - window
    return any(
        lo <= r.lap_number <= t and (r.compound in WET_COMPOUNDS or r.rain_affected)
        for r in race.laps
    )


def build_state(
    race: RaceData,
    driver: str,
    t: int,
    pit_loss_s: float,
    cfg: dict[str, Any],
) -> Optional[RaceState]:
    """RaceState for `driver` entering lap t. None if the data is insufficient."""
    # Structural leakage guarantee: drop everything after lap t up front.
    visible = [r for r in race.laps if r.lap_number <= t]
    idx = RaceIndex(race.model_copy(update={"laps": visible}))

    last = idx.rec(driver, t - 1)
    if last is None or last.position is None or last.compound == "UNKNOWN":
        return None

    n_times = int(cfg.get("state", {}).get("last_n_lap_times", 3))
    last_times = []
    for n in range(t - n_times, t):
        r = idx.rec(driver, n)
        if r is not None and r.lap_time_s is not None:
            last_times.append(round(r.lap_time_s, 3))

    used: list[Compound] = []
    for n in range(1, t):
        r = idx.rec(driver, n)
        if r is not None and r.compound != "UNKNOWN" and r.compound not in used:
            used.append(r.compound)

    # Offer wet compounds only if the field actually ran them near this lap (not the
    # race-level rain flag, not a whole-race latch). Leakage-safe: window is <= t.
    window = int(cfg.get("wet", {}).get("window_laps", 5))
    wet_nearby = wet_running_near(race, t, window)
    available: list[Compound] = list(DRY_COMPOUNDS) + (list(WET_COMPOUNDS) if wet_nearby else [])

    order = idx.order_at(t - 1)
    leader = order[0] if order else None

    def rival(position: int) -> Optional[RivalInfo]:
        for rec in order:
            if rec.position == position:
                gap = None
                if rec.end_time_s is not None and last.end_time_s is not None:
                    gap = round(abs(last.end_time_s - rec.end_time_s), 3)
                return RivalInfo(
                    driver=rec.driver,
                    gap_s=gap,
                    compound=rec.compound,
                    tyre_age=rec.tyre_age,
                )
        return None

    top_n = int(cfg.get("state", {}).get("top_n_summary", 10))
    top10 = []
    for rec in order[:top_n]:
        gap_leader = None
        if leader is not None and rec.end_time_s is not None and leader.end_time_s is not None:
            gap_leader = round(rec.end_time_s - leader.end_time_s, 3)
        top10.append(
            TopNRow(
                position=rec.position,  # type: ignore[arg-type]
                driver=rec.driver,
                compound=rec.compound,
                tyre_age=rec.tyre_age,
                gap_to_leader_s=gap_leader,
            )
        )

    return RaceState(
        race_id=race.race_id,
        track=race.track,
        total_laps=race.total_laps,
        current_lap=t,
        weather=race.weather,
        track_status=idx.field_status(t),  # the one permitted piece of lap-t knowledge
        pit_loss_s=round(pit_loss_s, 2),
        focal=FocalCar(
            driver=driver,
            position=last.position,
            compound=last.compound,
            tyre_age=last.tyre_age or 0,  # completed laps on the current set
            compounds_used=used,
            compounds_available=available,
            last_lap_times_s=last_times,
            car_ahead=rival(last.position - 1) if last.position > 1 else None,
            car_behind=rival(last.position + 1),
        ),
        top10=top10,
    )


def is_changeable(race: RaceData, focal_compound: str, t: int, window: int) -> bool:
    """Conditions-only test (NEVER uses score/delta): is the decision at lap t in a
    wet/changeable phase the dry-only v1 simulator cannot model?

    Uses the SAME actual-wet-running test as the offered compound set (no dependence on
    the race-level rain flag): True if the field ran INTER/WET or had rain-affected laps
    within `window` laps of t, OR the focal car is itself on INTER/WET entering lap t
    (mid-changeover). The v1 simulator runs a single stint to the flag and cannot switch
    wet<->slick, so such points are out of scope for the headline (see LIMITATIONS.md).
    """
    return wet_running_near(race, t, window) or focal_compound in WET_COMPOUNDS


def _is_lapped(idx: RaceIndex, driver: str, t: int) -> bool:
    """Leak-free lapped check: gap to leader at end of t-1 exceeds the leader's lap time."""
    order = idx.order_at(t - 1)
    if not order:
        return False
    leader = order[0]
    rec = idx.rec(driver, t - 1)
    if rec is None:
        return True  # has not even completed lap t-1: at least a lap down
    if rec.end_time_s is None or leader.end_time_s is None or leader.lap_time_s is None:
        return False
    return (rec.end_time_s - leader.end_time_s) > leader.lap_time_s


# ------------------------------------------------------------------------- extraction


def apply_type_quota(survivors: list[_Candidate], cap: int, target: int) -> list[_Candidate]:
    """Select up to `cap` candidates targeting `target` per type (A/B/C).

    A type with fewer than `target` available donates its unused slots to the
    remaining types in priority order B > C > A. Within a type the closest
    battles are kept first, with stable (lap, driver) tie-breakers.
    """
    by_type: dict[str, list[_Candidate]] = {"A": [], "B": [], "C": []}
    for cand in survivors:
        by_type[cand.dp_type].append(cand)
    for group in by_type.values():
        group.sort(key=lambda c: (c.relevant_gap_s, c.lap, c.driver))

    take = {t: min(target, len(group)) for t, group in by_type.items()}
    for t in sorted(by_type, key=lambda t: _TYPE_PRIORITY[t], reverse=True):  # shed A, C, B
        excess = sum(take.values()) - cap
        if excess <= 0:
            break
        take[t] -= min(excess, take[t])  # only reachable if cap < 3 * target
    leftover = cap - sum(take.values())
    for t in sorted(by_type, key=lambda t: _TYPE_PRIORITY[t]):  # B, then C, then A
        if leftover <= 0:
            break
        extra = min(leftover, len(by_type[t]) - take[t])
        take[t] += extra
        leftover -= extra

    picked: list[_Candidate] = []
    for t in ("A", "B", "C"):
        picked.extend(by_type[t][: take[t]])
    return picked


def extract_decision_points(
    race: RaceData, pit_loss_s: float, cfg: dict[str, Any]
) -> list[DecisionPoint]:
    """Apply Type A/B/C rules, dedupe, excludes, and the per-race cap."""
    idx = RaceIndex(race)
    exclude = cfg.get("exclude", {})
    first_laps = int(exclude.get("first_laps", 3))
    last_laps = int(exclude.get("last_laps", 2))
    ret_window = int(exclude.get("retirement_window_laps", 3))
    rival_gap_max = float(cfg.get("type_c", {}).get("rival_gap_s", 3.5))

    candidates: dict[tuple[str, int], _Candidate] = {}

    def add(cand: _Candidate) -> None:
        key = (cand.driver, cand.lap)
        existing = candidates.get(key)
        if existing is None or (_TYPE_PRIORITY[cand.dp_type] < _TYPE_PRIORITY[existing.dp_type]):
            candidates[key] = cand

    # --- Type A: pit-stop neighborhoods (classified cars only)
    for stop in race.pit_stops:
        if stop.driver not in race.classified:
            continue
        for off in cfg.get("type_a", {}).get("offsets", [2, 1, 0]):
            add(
                _Candidate(
                    driver=stop.driver,
                    lap=stop.lap - int(off),
                    dp_type="A",
                    trigger=f"own pit stop on lap {stop.lap}",
                )
            )

    # --- Type B: first lap of each SC/VSC period, every car in the top N
    top_n = int(cfg.get("type_b", {}).get("top_n_positions", 10))
    prev = "GREEN"
    for t in range(1, race.total_laps + 1):
        status = idx.field_status(t)
        if status in ("SC", "VSC") and prev != status:
            for rec in idx.order_at(t - 1)[:top_n]:
                add(
                    _Candidate(
                        driver=rec.driver,
                        lap=t,
                        dp_type="B",
                        trigger=f"{status} deployed on lap {t}",
                    )
                )
        prev = status

    # --- Type C: a direct rival pits on lap s. "Direct" = within +-1 race position
    # AND within the gap threshold, both at the end of lap s-1.
    for stop in race.pit_stops:
        s = stop.lap
        pit_rec = idx.rec(stop.driver, s - 1)
        if pit_rec is None or pit_rec.end_time_s is None or pit_rec.position is None:
            continue
        for rec in idx.by_lap.get(s - 1, []):
            if rec.driver == stop.driver or rec.end_time_s is None or rec.position is None:
                continue
            if abs(rec.position - pit_rec.position) > 1:
                continue
            gap = abs(rec.end_time_s - pit_rec.end_time_s)
            if gap <= rival_gap_max:
                add(
                    _Candidate(
                        driver=rec.driver,
                        lap=s + 1,
                        dp_type="C",
                        trigger=f"rival {stop.driver} pitted on lap {s} ({gap:.1f}s away)",
                        rival_gap_s=round(gap, 3),
                    )
                )

    # --- excludes + state building
    survivors: list[_Candidate] = []
    for cand in candidates.values():
        t = cand.lap
        if t <= first_laps or t > race.total_laps - last_laps:
            continue
        last_completed = max(idx.by_driver.get(cand.driver, {0: None}).keys())
        if cand.driver not in race.classified and t > last_completed - ret_window:
            continue  # no leakage of an upcoming retirement
        if exclude.get("lapped_cars", True) and _is_lapped(idx, cand.driver, t):
            continue
        state = build_state(race, cand.driver, t, pit_loss_s, cfg)
        if state is None:
            continue
        cand.state = state
        gaps = [
            g
            for g in (
                state.focal.car_ahead.gap_s if state.focal.car_ahead else None,
                state.focal.car_behind.gap_s if state.focal.car_behind else None,
            )
            if g is not None
        ]
        if cand.dp_type == "C" and cand.rival_gap_s is not None:
            cand.relevant_gap_s = cand.rival_gap_s
        elif gaps:
            cand.relevant_gap_s = min(gaps)
        survivors.append(cand)

    # --- cap with per-type quota; within a type, closest battles first
    survivors = apply_type_quota(
        survivors,
        cap=int(cfg.get("max_dp_per_race", 18)),
        target=int(cfg.get("quota_per_type", 6)),
    )
    survivors.sort(key=lambda c: (c.lap, c.driver))

    # --- assemble DecisionPoints with hindsight team action
    points: list[DecisionPoint] = []
    for cand in survivors:
        team_action, team_compound = _team_action(race, idx, cand.driver, cand.lap)
        points.append(
            DecisionPoint(
                dp_id=f"{race.race_id}-L{cand.lap:03d}-{cand.driver}-{cand.dp_type}",
                race_id=race.race_id,
                season=race.season,
                lap=cand.lap,
                driver=cand.driver,
                dp_type=cand.dp_type,  # type: ignore[arg-type]
                question=(
                    f"It is lap {cand.lap} of {race.total_laps}. Decide for "
                    f"{cand.driver}: pit at the end of this lap, or stay out? "
                    f"If pitting, choose the new compound."
                ),
                state=cand.state,  # type: ignore[arg-type]
                team_action=team_action,
                team_compound=team_compound,
                trigger=cand.trigger,
                changeable_conditions=is_changeable(
                    race,
                    cand.state.focal.compound,  # type: ignore[union-attr]
                    cand.lap,
                    int(cfg.get("wet", {}).get("window_laps", 5)),
                ),
            )
        )
    return points


def _team_action(
    race: RaceData, idx: RaceIndex, driver: str, t: int
) -> tuple[str, Optional[Compound]]:
    """What the real team did at lap t (hindsight; stored outside the prompt state)."""
    rec = idx.rec(driver, t)
    if rec is None or not rec.pit_in:
        return "STAY", None
    for stop in race.pit_stops:
        if stop.driver == driver and stop.lap == t:
            comp = stop.new_compound
            return "PIT", (comp if comp != "UNKNOWN" else None)
    return "PIT", None
