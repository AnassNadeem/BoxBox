"""End-to-end dataset build: ingest -> extract -> save decision points + calibration.

Usage:
    python scripts/build_dataset.py [--races 2026-monaco,2026-miami] [--force]
                                    [--groups races_2026,races_contamination] [--no-figures]
"""

from __future__ import annotations

import argparse
import json
import logging
import statistics
import sys
from pathlib import Path

from boxbox.config import load_config
from boxbox.data.ingest import ingest_race
from boxbox.dataset import DP_DIR, race_specs, save_decision_points
from boxbox.extract.decision_points import extract_decision_points
from boxbox.sim.degradation import calibration_records
from boxbox.sim.race_sim import make_simulator

REPO_ROOT = Path(__file__).resolve().parents[1]
CALIB_DIR = REPO_ROOT / "outputs" / "calibration"

log = logging.getLogger("build_dataset")


def calibration_figure(race_id: str, records: list[dict]) -> Path | None:
    if not records:
        return None
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    CALIB_DIR.mkdir(parents=True, exist_ok=True)
    actual = [r["actual_s"] / r["n_laps"] for r in records]
    predicted = [r["predicted_s"] / r["n_laps"] for r in records]
    errors = [(r["predicted_s"] - r["actual_s"]) / r["n_laps"] for r in records]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))
    ax1.scatter(actual, predicted, s=22, alpha=0.7, color="#e10600")
    lo, hi = min(actual + predicted), max(actual + predicted)
    ax1.plot([lo, hi], [lo, hi], "k--", lw=1)
    ax1.set_xlabel("actual mean lap time per stint (s)")
    ax1.set_ylabel("simulated mean lap time (s)")
    ax1.set_title(f"{race_id}: stint calibration")
    ax2.hist(errors, bins=20, color="#15151e", edgecolor="white")
    ax2.set_xlabel("per-lap error (s)")
    ax2.set_ylabel("stints")
    ax2.set_title("error distribution")
    fig.tight_layout()
    path = CALIB_DIR / f"{race_id}.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    return path


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--races", help="comma-separated race_ids (default: all configured)")
    parser.add_argument("--groups", help="comma-separated config groups to build")
    parser.add_argument("--force", action="store_true", help="re-ingest even if processed")
    parser.add_argument("--no-figures", action="store_true")
    args = parser.parse_args()

    groups = args.groups.split(",") if args.groups else None
    specs = race_specs(groups)
    if args.races:
        wanted = set(args.races.split(","))
        specs = [s for s in specs if s["race_id"] in wanted]
    if not specs:
        print("No races matched.", file=sys.stderr)
        return 2

    extraction_cfg = load_config("extraction")
    sim_cfg = load_config("run").get("simulator", {})

    manifest: dict[str, dict] = {}
    all_maes: list[float] = []
    for spec in specs:
        race_id = spec["race_id"]
        print(f"=== {race_id} ===")
        race = ingest_race(race_id, int(spec["year"]), str(spec["event"]), force=args.force)

        sim, deg, pit_loss, sc_factor, note = make_simulator(race, sim_cfg)
        records = calibration_records(race, deg)
        maes = [r["mae_per_lap_s"] for r in records]
        mae = round(statistics.mean(maes), 3) if maes else None
        if maes:
            all_maes.extend(maes)
        fig_path = None if args.no_figures else calibration_figure(race_id, records)

        dps = extract_decision_points(race, pit_loss, extraction_cfg)
        save_decision_points(race_id, dps)

        counts = {t: sum(1 for d in dps if d.dp_type == t) for t in "ABC"}
        manifest[race_id] = {
            "season": race.season,
            "track": race.track,
            "source": race.source,
            "total_laps": race.total_laps,
            "n_decision_points": len(dps),
            "dp_type_counts": counts,
            "pit_loss_s": round(pit_loss, 2),
            "sc_pit_factor": round(sc_factor, 2),
            "pit_loss_note": note,
            "calibration_mae_per_lap_s": mae,
            "calibration_stints": len(records),
            "calibration_figure": str(fig_path) if fig_path else None,
            "fit_report": deg.fit_report(),
        }
        print(
            f"  {len(dps)} decision points {counts} | pit loss {pit_loss:.1f}s "
            f"| calibration MAE {mae} s/lap over {len(records)} stints"
        )

    DP_DIR.mkdir(parents=True, exist_ok=True)
    (DP_DIR / "manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    if all_maes:
        print(f"\nOverall calibration MAE: {statistics.mean(all_maes):.3f} s/lap "
              f"(median {statistics.median(all_maes):.3f})")
    print(f"Manifest: {DP_DIR / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
