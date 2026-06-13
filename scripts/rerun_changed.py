"""Targeted re-run of decision points whose offered compound set changed after the
wet-detection fix (Miami + Canada dry-phase). Re-calls ONLY those DP x model prompts;
every unchanged call is left untouched (its cache entry and results.jsonl row are not
modified). Projects cost first and aborts if over the gate. ALLOW_SPEND set internally.

Usage: python scripts/rerun_changed.py
"""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
load_dotenv(REPO / ".env")
os.environ["ALLOW_SPEND"] = "1"  # scoped to this process

from boxbox.config import load_config  # noqa: E402
from boxbox.dataset import load_all_decision_points  # noqa: E402
from boxbox.harness.cache import ResponseCache, cache_key  # noqa: E402
from boxbox.harness.prompts import PROMPT_VERSION  # noqa: E402
from boxbox.harness.runner import CostLedger, Runner, SpendCapExceeded  # noqa: E402

CAP_USD = 25.0
TIMEOUT_S = 90.0
GATE_USD = 5.0
RESULTS = REPO / "outputs" / "raw_results" / "results.jsonl"


def main() -> int:
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("no OPENROUTER_API_KEY")
        return 2
    changed = set(json.loads((REPO / "outputs/_changed_dps.json").read_text()))
    run_cfg = load_config("run")
    run_cfg["spend_cap_usd"] = CAP_USD
    models_cfg = load_config("models")
    enabled = [m for m in models_cfg["models"] if m.get("enabled")]
    dps = [d for d in load_all_decision_points() if d.dp_id in changed]
    assert len(dps) == len(changed), f"{len(dps)} != {len(changed)}"
    n_calls = len(enabled) * len(dps)

    # ---- projection from the prior observed cost of these exact dp x model calls ----
    rows = list(csv.DictReader((REPO / "outputs/cost_ledger.csv").open(encoding="utf-8")))
    prior: dict[tuple[str, str], float] = {}
    for r in rows:
        if (
            not r["model_id"].startswith("mock")
            and r["dp_id"] in changed
            and float(r["cost_usd"]) > 0
        ):
            prior[(r["model_name"], r["dp_id"])] = float(r["cost_usd"])
    proj = sum(prior.get((m["name"], d.dp_id), 0.0) for m in enabled for d in dps)
    print(
        f"PROJECTION: {len(dps)} DPs x {len(enabled)} models = {n_calls} calls; "
        f"projected ${proj:.4f} (from prior observed tokens); gate ${GATE_USD:.2f}"
    )
    if proj > GATE_USD:
        print(f"ABORT: projection ${proj:.4f} exceeds gate ${GATE_USD:.2f} — no spend.")
        return 3

    # ---- invalidate cache ONLY for changed dp x enabled model (temp 0, repeat 0) ----
    cache = ResponseCache()
    ledger = CostLedger(spend_cap_usd=CAP_USD)
    deleted = 0
    for m in enabled:
        for d in dps:
            p = (
                cache.cache_dir
                / f"{cache_key(m['openrouter_id'], PROMPT_VERSION, d.dp_id, 0.0, 0)}.json"
            )
            if p.exists():
                p.unlink()
                deleted += 1
    print(f"invalidated {deleted} cache entries (changed prompts only)")

    # ---- re-run only the changed DPs ----
    from openai import OpenAI

    runner = Runner(run_cfg, models_cfg, mock=False, cache=cache, ledger=ledger)
    runner._client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ["OPENROUTER_API_KEY"],
        timeout=TIMEOUT_S,
        max_retries=0,
    )
    new_results = []
    t0 = time.time()
    done = 0
    for m in enabled:
        for d in dps:
            try:
                new_results.append(runner.call(d, m, 0))
            except SpendCapExceeded as exc:
                print(f"CAP HIT: {exc}")
                return 3
            done += 1
            if done % 25 == 0 or done == n_calls:
                print(
                    f"  {done}/{n_calls} | spend ${ledger.total_usd:.4f} | {time.time() - t0:.0f}s",
                    flush=True,
                )

    # ---- merge: keep unchanged rows verbatim, replace changed ----
    existing = [ln for ln in RESULTS.read_text(encoding="utf-8").splitlines() if ln.strip()]
    kept = [ln for ln in existing if json.loads(ln)["dp_id"] not in changed]
    with RESULTS.open("w", encoding="utf-8") as fh:
        for ln in kept:
            fh.write(ln + "\n")
        for r in new_results:
            fh.write(r.model_dump_json() + "\n")
    print(
        f"merged results.jsonl: {len(kept)} unchanged (untouched) + {len(new_results)} re-run "
        f"= {len(kept) + len(new_results)} total"
    )
    print(
        f"ACTUAL re-run spend: ${ledger.total_usd - float(rows[-1]['cumulative_usd']):.4f} "
        f"(cumulative ${ledger.total_usd:.4f})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
