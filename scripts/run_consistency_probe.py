"""Consistency probe: rerun the most contentious decision points with sampling.

Selects the N decision points with the highest cross-model action disagreement
in the main pass (logged to outputs/probe_selection.json and the console), then
runs all models x `samples` at the probe temperature from config/run.yaml's
`consistency_probe` block. The flip rate is computed ONLY from these results.

Usage:
    python scripts/run_consistency_probe.py --mock     # default, $0
    python scripts/run_consistency_probe.py --real     # requires key + ALLOW_SPEND=1
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from dotenv import load_dotenv

from boxbox.config import load_config
from boxbox.data.schemas import CallResult
from boxbox.dataset import load_all_decision_points
from boxbox.harness.probe import select_probe_dps
from boxbox.harness.runner import Runner, SpendCapExceeded

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = REPO_ROOT / "outputs" / "raw_results"

log = logging.getLogger("run_consistency_probe")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    load_dotenv(REPO_ROOT / ".env")

    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--mock", action="store_true", default=True, help="mock mode (default)")
    mode.add_argument("--real", action="store_true", help="real OpenRouter calls (gated)")
    args = parser.parse_args()
    mock = not args.real

    main_results_path = RESULTS_DIR / "results.jsonl"
    if not main_results_path.exists():
        print(f"No main-pass results at {main_results_path} - run scripts/run_benchmark.py first.")
        return 2
    main_results = [
        CallResult.model_validate_json(line)
        for line in main_results_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    run_cfg = load_config("run")
    probe_cfg = run_cfg.get("consistency_probe", {})
    n_dps = int(probe_cfg.get("n_decision_points", 20))
    samples = int(probe_cfg.get("samples", 5))
    temperature = float(probe_cfg.get("temperature", 1.0))

    selections = select_probe_dps(main_results, n_dps)
    if not selections:
        print("No valid main-pass answers to select from - nothing to probe.")
        return 2
    for sel in selections:
        log.info("probe pick %s: %s", sel.dp_id, sel.reason)
    selection_path = REPO_ROOT / "outputs" / "probe_selection.json"
    selection_path.write_text(
        json.dumps([sel.to_dict() for sel in selections], indent=1), encoding="utf-8"
    )

    wanted = {sel.dp_id for sel in selections}
    dps = [dp for dp in load_all_decision_points() if dp.dp_id in wanted]
    if not dps:
        print("Selected dp_ids not found in data/decision_points/ - rebuild the dataset.")
        return 2

    probe_run_cfg = {**run_cfg, "temperature": temperature, "repeats": samples}
    runner = Runner(probe_run_cfg, load_config("models"), mock=mock)
    try:
        results = runner.run_all(dps)
    except SpendCapExceeded as exc:
        print(f"ABORTED: {exc}")
        return 3

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / "probe_results.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for r in results:
            fh.write(r.model_dump_json() + "\n")

    n_invalid = sum(1 for r in results if r.invalid)
    n_cached = sum(1 for r in results if r.cached)
    print(
        f"{len(results)} probe results ({len(dps)} DPs x {len(runner.models())} models "
        f"x {samples} samples) | mode={'MOCK' if mock else 'REAL'} | "
        f"temperature={temperature} | new calls: {runner.api_calls} | "
        f"cache hits: {n_cached} | invalid: {n_invalid} | "
        f"total spend: ${runner.ledger.total_usd:.4f}"
    )
    print(f"-> {out} (selection log: {selection_path})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
