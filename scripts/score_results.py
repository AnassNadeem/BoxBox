"""Score raw results against the simulator -> outputs/leaderboard.{md,csv,json}.

If outputs/raw_results/probe_results.jsonl exists it is scored too; the flip
rate on the leaderboard comes only from those probe results.

Usage: python scripts/score_results.py [--results outputs/raw_results/results.jsonl]
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from boxbox.config import load_config
from boxbox.data.ingest import load_race
from boxbox.data.schemas import CallResult
from boxbox.dataset import load_all_decision_points
from boxbox.score.leaderboard import aggregate, to_markdown, write_outputs
from boxbox.score.scoring import score_all

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results",
        default=str(REPO_ROOT / "outputs" / "raw_results" / "results.jsonl"),
    )
    parser.add_argument(
        "--probe-results",
        default=str(REPO_ROOT / "outputs" / "raw_results" / "probe_results.jsonl"),
    )
    args = parser.parse_args()

    def read_results(path: Path) -> list[CallResult]:
        return [
            CallResult.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    results_path = Path(args.results)
    if not results_path.exists():
        print(f"No results at {results_path} - run scripts/run_benchmark.py first.")
        return 2
    results = read_results(results_path)

    probe_path = Path(args.probe_results)
    probe_results = read_results(probe_path) if probe_path.exists() else []

    dps = load_all_decision_points()
    used_race_ids = {dp.race_id for dp in dps}
    races = {rid: load_race(rid) for rid in used_race_ids}
    sim_cfg = load_config("run").get("simulator", {})

    scores = score_all(dps, results, races, sim_cfg)
    probe_scores = score_all(dps, probe_results, races, sim_cfg) if probe_results else []

    # persist per-call scores for analysis/figures.py
    scores_path = REPO_ROOT / "outputs" / "scores.jsonl"
    with scores_path.open("w", encoding="utf-8") as fh:
        for s in scores:
            fh.write(s.model_dump_json() + "\n")
    if probe_scores:
        probe_scores_path = REPO_ROOT / "outputs" / "probe_scores.jsonl"
        with probe_scores_path.open("w", encoding="utf-8") as fh:
            for s in probe_scores:
                fh.write(s.model_dump_json() + "\n")

    mode = "mock" if all(r.model_id.startswith("mock") for r in results) else "real"
    board = aggregate(scores, mode=mode, probe_scores=probe_scores)
    paths = write_outputs(board)
    print(to_markdown(board))
    print("Wrote: " + ", ".join(str(p) for p in [scores_path, *paths]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
