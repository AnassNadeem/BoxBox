"""Full real benchmark run (prereg-v2 roster: 5 models, Fable 5 disabled).

Main pass (178 DPs x enabled models x 1 sample, temp 0) + consistency probe
(top-20 disagreement DPs x models x 5 samples, temp 1.0). Operational controls:
  - hard spend cap $25 on a single ledger shared across main + probe (cumulative)
  - 90s per-call request timeout (OpenAI client), the Runner's own 4-attempt loop
    (= up to 3 retries) handles 429/5xx/timeout backoff; SDK retries disabled to
    avoid double-retrying
  - every response cached (outputs/cache/), so an interrupted run resumes for $0

Writes outputs/raw_results/{results,probe_results}.jsonl and probe_selection.json.
Does NOT score or push. Run scripts/score_results.py afterwards.

Usage: ALLOW_SPEND is set internally; needs OPENROUTER_API_KEY in .env.
    python scripts/run_full_benchmark.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
load_dotenv(REPO / ".env")
os.environ["ALLOW_SPEND"] = "1"  # scoped to this process only

from boxbox.config import load_config  # noqa: E402
from boxbox.dataset import load_all_decision_points  # noqa: E402
from boxbox.harness.cache import ResponseCache  # noqa: E402
from boxbox.harness.probe import select_probe_dps  # noqa: E402
from boxbox.harness.runner import CostLedger, Runner, SpendCapExceeded  # noqa: E402

CAP_USD = 25.0
TIMEOUT_S = 90.0
RESULTS_DIR = REPO / "outputs" / "raw_results"


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def make_client():
    from openai import OpenAI

    # max_retries=0: the Runner does its own 4-attempt backoff loop.
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
        timeout=TIMEOUT_S,
        max_retries=0,
    )


def run_phase(runner, tasks, out_path, label, collect=False):
    n = len(tasks)
    done = 0
    t0 = time.time()
    collected = []
    with out_path.open("w", encoding="utf-8") as fh:
        for model, dp, rep in tasks:
            res = runner.call(dp, model, rep)
            if collect:
                collected.append(res)
            fh.write(res.model_dump_json() + "\n")
            fh.flush()
            done += 1
            if done % 25 == 0 or done == n:
                el = time.time() - t0
                print(
                    f"[{label}] {done}/{n} | spend ${runner.ledger.total_usd:.4f} "
                    f"| {el / max(done, 1):.1f}s/call | elapsed {el / 60:.1f}m",
                    flush=True,
                )
    return collected


def main() -> int:
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY missing from .env - aborting (no calls).")
        return 2

    run_cfg = load_config("run")
    run_cfg["spend_cap_usd"] = CAP_USD
    models_cfg = load_config("models")
    cache = ResponseCache()
    ledger = CostLedger(spend_cap_usd=CAP_USD)  # resumes cumulative from cost_ledger.csv
    client = make_client()
    dps = load_all_decision_points()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    print(
        f"START {_utc()} | cap=${CAP_USD} | timeout={TIMEOUT_S}s | "
        f"ledger starts at ${ledger.total_usd:.4f}"
    )

    # ----- MAIN PASS (temp 0, 1 sample) -----------------------------------------
    main_runner = Runner(run_cfg, models_cfg, mock=False, cache=cache, ledger=ledger)
    main_runner._client = client
    models = main_runner.models()
    print(f"main: {[m['name'] for m in models]} x {len(dps)} DPs = {len(models) * len(dps)} calls")
    main_tasks = [(m, dp, 0) for m in models for dp in dps]
    try:
        main_results = run_phase(
            main_runner, main_tasks, RESULTS_DIR / "results.jsonl", "main", collect=True
        )
    except SpendCapExceeded as exc:
        print(f"CAP HIT during main pass: {exc}")
        return 3

    # ----- PROBE (temp 1.0, 5 samples on top-disagreement DPs) ------------------
    pcfg = run_cfg.get("consistency_probe", {})
    n_dps = int(pcfg.get("n_decision_points", 20))
    samples = int(pcfg.get("samples", 5))
    ptemp = float(pcfg.get("temperature", 1.0))
    selections = select_probe_dps(main_results, n_dps)
    (REPO / "outputs" / "probe_selection.json").write_text(
        json.dumps([s.to_dict() for s in selections], indent=1), encoding="utf-8"
    )
    wanted = {s.dp_id for s in selections}
    probe_dps = [dp for dp in dps if dp.dp_id in wanted]
    print(
        f"probe: {len(probe_dps)} DPs x {len(models)} models x {samples} samples "
        f"= {len(probe_dps) * len(models) * samples} calls (temp {ptemp})"
    )

    probe_run_cfg = {**run_cfg, "temperature": ptemp, "repeats": samples}
    probe_runner = Runner(probe_run_cfg, models_cfg, mock=False, cache=cache, ledger=ledger)
    probe_runner._client = client
    probe_tasks = [
        (m, dp, rep) for m in probe_runner.models() for dp in probe_dps for rep in range(samples)
    ]
    try:
        run_phase(probe_runner, probe_tasks, RESULTS_DIR / "probe_results.jsonl", "probe")
    except SpendCapExceeded as exc:
        print(f"CAP HIT during probe: {exc}")
        return 3

    print(
        f"DONE {_utc()} | TOTAL SPEND ${ledger.total_usd:.4f} | "
        f"main {len(main_tasks)} + probe {len(probe_tasks)} calls"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
