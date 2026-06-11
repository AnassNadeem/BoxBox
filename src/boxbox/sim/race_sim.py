"""Counterfactual rollout of the focal car's remaining race (section 7).

Only the focal car is simulated; everything else (including the SC/VSC timeline,
which the hindsight oracle is allowed to know) is held fixed at what actually
happened. SC/VSC laps run at the field-median actual time for that lap. No
traffic interaction in v1 - the headline limitation in docs/LIMITATIONS.md.
"""

from __future__ import annotations

import statistics
from typing import Optional

from boxbox.data.schemas import RaceData, TrackStatusLabel
from boxbox.sim.degradation import DegradationModel


class RaceSimulator:
    def __init__(
        self,
        race: RaceData,
        deg: DegradationModel,
        pit_loss_s: float,
        sc_pit_factor: float = 0.55,
        rejoin_penalty_s: float = 0.0,
    ):
        self.race = race
        self.deg = deg
        self.pit_loss_s = pit_loss_s
        self.sc_pit_factor = sc_pit_factor
        self.rejoin_penalty_s = rejoin_penalty_s

        self._lap_status: dict[int, TrackStatusLabel] = {}
        self._lap_median: dict[int, float] = {}
        self._neutralized: set[int] = set()  # SC/VSC/RED or mostly rain-affected laps
        by_lap: dict[int, list[float]] = {}
        rain_count: dict[int, int] = {}
        lap_count: dict[int, int] = {}
        prio = {"RED": 4, "SC": 3, "VSC": 2, "YELLOW": 1, "GREEN": 0}
        for r in race.laps:
            cur = self._lap_status.get(r.lap_number, "GREEN")
            if prio[r.track_status] > prio[cur]:
                self._lap_status[r.lap_number] = r.track_status
            elif r.lap_number not in self._lap_status:
                self._lap_status[r.lap_number] = r.track_status
            if r.lap_time_s is not None:
                by_lap.setdefault(r.lap_number, []).append(r.lap_time_s)
            lap_count[r.lap_number] = lap_count.get(r.lap_number, 0) + 1
            if r.rain_affected:
                rain_count[r.lap_number] = rain_count.get(r.lap_number, 0) + 1
        for n, times in by_lap.items():
            self._lap_median[n] = statistics.median(times)
        for n, total_n in lap_count.items():
            status = self._lap_status.get(n, "GREEN")
            rainy = rain_count.get(n, 0) / total_n > 0.3
            if status in ("SC", "VSC", "RED") or rainy:
                self._neutralized.add(n)

    def lap_status(self, lap: int) -> TrackStatusLabel:
        return self._lap_status.get(lap, "GREEN")

    def rollout(
        self,
        driver: str,
        from_lap: int,
        start_compound: str,
        start_tyre_age: int,
        stops: list[tuple[int, str]],
    ) -> float:
        """Total time (s) for laps from_lap..total_laps under the given stop plan.

        `start_tyre_age` = completed laps on the current set entering from_lap.
        A stop (n, compound) means: pit at the END of lap n, rejoin on `compound`.
        """
        stop_map = dict(stops)
        total = 0.0
        compound = start_compound
        age = start_tyre_age
        for n in range(from_lap, self.race.total_laps + 1):
            age += 1
            status = self.lap_status(n)
            if n in self._neutralized and n in self._lap_median:
                lap_time = self._lap_median[n]  # SC/VSC/red/damp: everyone runs field pace
            else:
                lap_time = self.deg.predict(driver, compound, age, n)
            if n in stop_map:
                factor = self.sc_pit_factor if status in ("SC", "VSC") else 1.0
                lap_time += self.pit_loss_s * factor + self.rejoin_penalty_s
                compound = stop_map[n]
                age = 0  # out-lap next lap counts as age 1
            total += lap_time
        return total


def make_simulator(
    race: RaceData,
    sim_cfg: Optional[dict] = None,
) -> tuple[RaceSimulator, DegradationModel, float, float, str]:
    """Convenience factory: fits + pit loss + simulator from one RaceData."""
    from boxbox.sim.degradation import estimate_pit_loss

    cfg = sim_cfg or {}
    deg = DegradationModel(
        race,
        min_clean_laps=int(cfg.get("min_clean_laps_for_fit", 4)),
        outlier_mad=float(cfg.get("outlier_mad", 3.0)),
    )
    pit_loss, sc_factor, note = estimate_pit_loss(race)
    if not cfg.get("sc_pit_loss_factor_default") is None and "default" in note:
        sc_factor = float(cfg["sc_pit_loss_factor_default"])
    sim = RaceSimulator(
        race,
        deg,
        pit_loss_s=pit_loss,
        sc_pit_factor=sc_factor,
        rejoin_penalty_s=float(cfg.get("rejoin_penalty_s", 0.0)),
    )
    return sim, deg, pit_loss, sc_factor, note
