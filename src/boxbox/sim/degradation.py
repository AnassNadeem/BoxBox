"""Per (driver, compound) lap-time models and pit-loss estimation (section 7).

Model: lap_time = a + b * tyre_age + c * lap_number, fitted on clean laps
(green flag, no in/out laps, residual outliers > 3 MAD removed). Fallback
chain when a driver has too few clean laps on a compound:
driver fit -> team-mate fit -> field (pooled) fit -> unseen-compound fallback.
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass
from typing import Optional

import numpy as np

from boxbox.data.schemas import LapRecord, RaceData

log = logging.getLogger(__name__)

FitSource = str  # "driver" | "teammate" | "field" | "unseen-compound"


@dataclass(frozen=True)
class LapTimeFit:
    a: float  # base pace (s)
    b: float  # degradation (s per lap of tyre age)
    c: float  # fuel/track evolution effect (s per race lap)
    n_laps: int
    source: FitSource

    def predict(self, tyre_age: float, lap_number: float) -> float:
        return self.a + self.b * tyre_age + self.c * lap_number


def _clean_laps(race: RaceData) -> list[LapRecord]:
    """Clean = timed, green flag, not an in/out lap. (IsAccurate is NOT required:
    several 2026 sessions mark whole drivers inaccurate; MAD filtering covers it.)"""
    return [
        r
        for r in race.laps
        if r.lap_time_s is not None
        and r.track_status == "GREEN"
        and not r.pit_in
        and not r.pit_out
        and r.compound != "UNKNOWN"
        and r.tyre_age is not None
    ]


def _fit(laps: list[LapRecord], source: FitSource) -> Optional[LapTimeFit]:
    """Least-squares fit with one round of >3*MAD residual outlier removal."""
    if len(laps) < 4:
        return None

    def solve(subset: list[LapRecord]) -> tuple[np.ndarray, np.ndarray]:
        x = np.array([[1.0, r.tyre_age, r.lap_number] for r in subset])
        y = np.array([r.lap_time_s for r in subset])
        coef, *_ = np.linalg.lstsq(x, y, rcond=None)
        return coef, y - x @ coef

    coef, resid = solve(laps)
    mad = statistics.median(abs(float(e)) for e in resid)
    if mad > 0:
        kept = [r for r, e in zip(laps, resid) if abs(float(e)) <= 3.0 * mad]
        if len(kept) >= 4 and len(kept) < len(laps):
            coef, _ = solve(kept)
            laps = kept
    return LapTimeFit(
        a=float(coef[0]), b=float(coef[1]), c=float(coef[2]), n_laps=len(laps), source=source
    )


class DegradationModel:
    """All lap-time fits for one race, with the fallback chain resolved per lookup.

    Predictions are clamped to physical bounds: tyre age is capped at the maximum
    age observed on that compound in clean running (linear fits extrapolate
    absurdly past the data, e.g. negative degradation at Monaco), and no lap can
    be faster than the race's fastest clean lap.
    """

    def __init__(self, race: RaceData, min_clean_laps: int = 4, outlier_mad: float = 3.0):
        self.race = race
        self.min_clean_laps = min_clean_laps
        clean = _clean_laps(race)

        by_dc: dict[tuple[str, str], list[LapRecord]] = {}
        by_comp: dict[str, list[LapRecord]] = {}
        for r in clean:
            by_dc.setdefault((r.driver, r.compound), []).append(r)
            by_comp.setdefault(r.compound, []).append(r)

        self.max_age_seen: dict[str, int] = {
            comp: max(r.tyre_age for r in laps) for comp, laps in by_comp.items()  # type: ignore[type-var]
        }
        self.fastest_clean_s: float = min(
            (r.lap_time_s for r in clean if r.lap_time_s is not None), default=60.0
        )

        self.driver_fits: dict[tuple[str, str], LapTimeFit] = {}
        for (driver, comp), laps in by_dc.items():
            if len(laps) >= min_clean_laps:
                fit = _fit(laps, "driver")
                if fit is not None:
                    self.driver_fits[(driver, comp)] = fit

        self.field_fits: dict[str, LapTimeFit] = {}
        for comp, laps in by_comp.items():
            fit = _fit(laps, "field")
            if fit is not None:
                self.field_fits[comp] = fit

        self.fallback_counts: dict[FitSource, int] = {
            "driver": 0,
            "teammate": 0,
            "field": 0,
            "unseen-compound": 0,
        }

    def _teammates(self, driver: str) -> list[str]:
        team = self.race.teams.get(driver, "")
        if not team:
            return []
        return [d for d, t in self.race.teams.items() if t == team and d != driver]

    def fit_for(self, driver: str, compound: str) -> LapTimeFit:
        fit = self.driver_fits.get((driver, compound))
        if fit is not None:
            self.fallback_counts["driver"] += 1
            return fit
        for mate in self._teammates(driver):
            fit = self.driver_fits.get((mate, compound))
            if fit is not None:
                self.fallback_counts["teammate"] += 1
                return LapTimeFit(fit.a, fit.b, fit.c, fit.n_laps, "teammate")
        fit = self.field_fits.get(compound)
        if fit is not None:
            self.fallback_counts["field"] += 1
            return fit
        # Compound nobody ran cleanly: slowest known field fit + 1.0s/lap penalty.
        self.fallback_counts["unseen-compound"] += 1
        if self.field_fits:
            worst = max(self.field_fits.values(), key=lambda f: f.a)
            return LapTimeFit(worst.a + 1.0, worst.b, worst.c, worst.n_laps, "unseen-compound")
        # Degenerate race data: flat 100s laps keeps the pipeline alive, loudly.
        log.error("No field fits at all for %s - returning flat fallback", self.race.race_id)
        return LapTimeFit(100.0, 0.1, 0.0, 0, "unseen-compound")

    def predict(self, driver: str, compound: str, tyre_age: float, lap_number: float) -> float:
        age_cap = self.max_age_seen.get(compound)
        if age_cap is not None:
            tyre_age = min(tyre_age, float(age_cap))
        raw = self.fit_for(driver, compound).predict(tyre_age, lap_number)
        return max(raw, self.fastest_clean_s)

    def fit_report(self) -> dict:
        return {
            "race_id": self.race.race_id,
            "n_driver_fits": len(self.driver_fits),
            "n_field_fits": len(self.field_fits),
            "lookups_by_source": dict(self.fallback_counts),
        }


# ---------------------------------------------------------------------------- pit loss

def estimate_pit_loss(race: RaceData) -> tuple[float, float, str]:
    """(green pit loss s, SC pit-loss factor, note about which path was used).

    Per real stop: loss = in_lap + out_lap - 2 * driver's clean-lap median.
    Green loss = median over green-flag stops; SC factor measured from the race's
    own SC-era stops when >= 2 are available, else the configured default 0.55
    (applied by the caller; we return the measured-or-default value).
    """
    by_driver: dict[str, dict[int, LapRecord]] = {}
    for r in race.laps:
        by_driver.setdefault(r.driver, {})[r.lap_number] = r

    clean_median: dict[str, float] = {}
    for driver, lap_map in by_driver.items():
        times = [
            r.lap_time_s
            for r in lap_map.values()
            if r.lap_time_s is not None
            and r.track_status == "GREEN"
            and not r.pit_in
            and not r.pit_out
        ]
        if len(times) >= 5:
            clean_median[driver] = statistics.median(times)

    green_losses: list[float] = []
    sc_losses: list[float] = []
    for stop in race.pit_stops:
        in_lap = by_driver.get(stop.driver, {}).get(stop.lap)
        out_lap = by_driver.get(stop.driver, {}).get(stop.lap + 1)
        base = clean_median.get(stop.driver)
        if (
            in_lap is None
            or out_lap is None
            or in_lap.lap_time_s is None
            or out_lap.lap_time_s is None
            or base is None
        ):
            continue
        loss = in_lap.lap_time_s + out_lap.lap_time_s - 2.0 * base
        if not 5.0 <= loss <= 120.0:
            continue  # red-flag stops and timing glitches
        if in_lap.track_status in ("SC", "VSC") or out_lap.track_status in ("SC", "VSC"):
            sc_losses.append(loss)
        else:
            green_losses.append(loss)

    if green_losses:
        green = statistics.median(green_losses)
        note = f"green loss from {len(green_losses)} stops"
    elif sc_losses:
        green = statistics.median(sc_losses) / 0.55
        note = f"no green-flag stops; back-computed from {len(sc_losses)} SC stops"
    else:
        green = 22.0
        note = "no measurable stops; default 22.0s"

    if len(sc_losses) >= 2 and green > 0:
        factor = max(0.2, min(1.0, statistics.median(sc_losses) / green))
        note += f"; SC factor measured from {len(sc_losses)} SC-era stops"
    else:
        factor = 0.55
        note += "; SC factor default 0.55"
    return float(green), float(factor), note


# -------------------------------------------------------------------------- calibration

def calibration_records(race: RaceData, model: DegradationModel) -> list[dict]:
    """Per real stint: simulated vs actual stint time over its clean laps.

    Uses each driver's own fallback-resolved fit, so the numbers reflect what the
    simulator would actually do. Returns one record per (driver, stint).
    """
    by_stint: dict[tuple[str, int], list[LapRecord]] = {}
    for r in _clean_laps(race):
        if r.stint is not None:
            by_stint.setdefault((r.driver, r.stint), []).append(r)

    records: list[dict] = []
    for (driver, stint), laps in sorted(by_stint.items()):
        if len(laps) < 3:
            continue
        compound = laps[0].compound
        actual = sum(r.lap_time_s for r in laps)  # type: ignore[misc]
        fit = model.fit_for(driver, compound)
        predicted = sum(fit.predict(r.tyre_age, r.lap_number) for r in laps)  # type: ignore[arg-type]
        records.append(
            {
                "race_id": race.race_id,
                "driver": driver,
                "stint": stint,
                "compound": compound,
                "n_laps": len(laps),
                "actual_s": round(actual, 3),
                "predicted_s": round(predicted, 3),
                "mae_per_lap_s": round(abs(predicted - actual) / len(laps), 3),
                "fit_source": fit.source,
            }
        )
    return records
