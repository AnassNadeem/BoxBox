"""Run decision points x models -> outputs/raw_results/results.jsonl.

Usage:
    python scripts/run_benchmark.py --mock                # default, $0
    python scripts/run_benchmark.py --real                # requires key + ALLOW_SPEND=1
    python scripts/run_benchmark.py --mock --models claude-fable-5,gpt-5.5 --limit 10
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from dotenv import load_dotenv

from boxbox.config import load_config
from boxbox.dataset import load_all_decision_points
from boxbox.harness.runner import Runner, SpendCapExceeded

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "outputs" / "raw_results"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    load_dotenv(REPO_ROOT / ".env")

    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--mock", action="store_true", default=True, help="mock mode (default)")
    mode.add_argument("--real", action="store_true", help="real OpenRouter calls (gated)")
    parser.add_argument("--models", help="comma-separated model names to run")
    parser.add_argument("--races", help="comma-separated race_ids to include")
    parser.add_argument("--limit", type=int, help="max decision points (smoke tests)")
    parser.add_argument("--repeats", type=int, help="override run.yaml repeats")
    args = parser.parse_args()
    mock = not args.real

    dps = load_all_decision_points()
    if args.races:
        wanted = set(args.races.split(","))
        dps = [dp for dp in dps if dp.race_id in wanted]
    if args.limit:
        dps = dps[: args.limit]
    if not dps:
        print("No decision points found - run scripts/build_dataset.py first.")
        return 2

    run_cfg = load_config("run")
    models_cfg = load_config("models")
    if args.models:
        wanted_models = set(args.models.split(","))
        models_cfg["models"] = [m for m in models_cfg["models"] if m["name"] in wanted_models]

    runner = Runner(run_cfg, models_cfg, mock=mock)
    try:
        results = runner.run_all(dps, repeats=args.repeats)
    except SpendCapExceeded as exc:
        print(f"ABORTED: {exc}")
        return 3

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / "results.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(r.model_dump_json() + "\n")

    n_invalid = sum(1 for r in results if r.invalid)
    n_cached = sum(1 for r in results if r.cached)
    print(
        f"{len(results)} results ({len(dps)} DPs x {len(runner.models())} models) | "
        f"mode={'MOCK' if mock else 'REAL'} | new calls: {runner.api_calls} | "
        f"cache hits: {n_cached} | invalid: {n_invalid} | "
        f"total spend: ${runner.ledger.total_usd:.4f}"
    )
    print(f"-> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
