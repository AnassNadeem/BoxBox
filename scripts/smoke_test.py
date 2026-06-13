"""REAL connectivity smoke test under strict cost control.

Runs every enabled model in config/models.yaml against exactly 3 decision points
(one Type A, one Type B, one Type C, each from a different race), 1 sample each,
temperature 0. Mirrors Runner._call_real's request parameters exactly so this
exercises the same code path the real benchmark will use, but additionally captures
reasoning tokens, finish_reason, and OpenRouter's own reported cost.

Hard aborts if the worst-case projected cost exceeds the cap, and re-checks the cap
before every individual call. Writes outputs/smoke_test_v2.md, then projects the
full-run cost (180 main-pass + 600 probe calls) from the observed token counts.

Usage:
    python scripts/smoke_test.py        # requires OPENROUTER_API_KEY in .env
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from boxbox.config import load_config  # noqa: E402
from boxbox.data.schemas import DecisionPoint  # noqa: E402
from boxbox.dataset import load_all_decision_points  # noqa: E402
from boxbox.harness.parse import parse_decision  # noqa: E402
from boxbox.harness.prompts import PROMPT_VERSION, build_messages  # noqa: E402
from boxbox.harness.runner import (  # noqa: E402
    _JSON_MODE_UNSUPPORTED,
    CostLedger,
    create_chat_completion,
)

SMOKE_CAP_USD = 1.50
OUT_PATH = REPO_ROOT / "outputs" / "smoke_test_v2.md"

# Full-run sizing for the cost projection. Main pass = every decision point in the
# dataset (178 at prereg-v1) x 6 enabled models = 1068 calls; consistency probe =
# 20 DPs x 6 models x 5 samples = 600 calls. (An earlier 180 here was a wrong
# placeholder that under-counted the main pass by ~6x; the real benchmark loads the
# DP count dynamically, so treat these as sizing constants for this script only.)
FULL_RUN_MAIN_CALLS = 1068
FULL_RUN_PROBE_CALLS = 600

# (dp_type, race_id) picks — three different races, one of each type
DP_PICKS = [("A", "2026-australia"), ("B", "2026-china"), ("C", "2026-japan")]


def pick_decision_points() -> list[DecisionPoint]:
    all_dps = load_all_decision_points()
    picked: list[DecisionPoint] = []
    for dp_type, race_id in DP_PICKS:
        candidates = [d for d in all_dps if d.dp_type == dp_type and d.race_id == race_id]
        if not candidates:
            raise RuntimeError(f"no Type {dp_type} decision point in {race_id}")
        picked.append(sorted(candidates, key=lambda d: d.dp_id)[0])
    return picked


def estimate_prompt_tokens(dp: DecisionPoint) -> int:
    return sum(len(m["content"]) for m in build_messages(dp)) // 4


def worst_case_call_cost(model: dict, prompt_tokens: int, max_tokens: int) -> float:
    return CostLedger.compute_cost(
        prompt_tokens,
        max_tokens,
        model.get("pricing_in_per_mtok"),
        model.get("pricing_out_per_mtok"),
    )


def usage_field(usage: Any, name: str) -> Optional[Any]:
    """Read a field off the SDK usage object, falling back to provider extras."""
    val = getattr(usage, name, None)
    if val is None and usage is not None:
        extra = getattr(usage, "model_extra", None) or {}
        val = extra.get(name)
    return val


def reasoning_tokens(usage: Any) -> Optional[int]:
    details = usage_field(usage, "completion_tokens_details")
    if details is None:
        return None
    val = getattr(details, "reasoning_tokens", None)
    if val is None and isinstance(details, dict):
        val = details.get("reasoning_tokens")
    return int(val) if val is not None else None


def call_model(
    client: Any, model: dict, dp: DecisionPoint, temperature: float, max_tokens: int
) -> dict:
    """One real call, mirroring Runner._call_real's parameters. Never raises."""
    messages = build_messages(dp)
    rec: dict[str, Any] = {
        "model_name": model["name"],
        "model_id": model["openrouter_id"],
        "dp_id": dp.dp_id,
        "raw_response": "",
        "parsed": None,
        "parse_error": None,
        "transport_error": None,
        "finish_reason": None,
        "json_mode": None,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "reasoning_tokens": None,
        "api_reported_cost_usd": None,
        "cost_usd": 0.0,
        "latency_s": None,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    usage = None
    for attempt in range(3):
        try:
            t0 = time.monotonic()
            resp = create_chat_completion(
                client,
                model["openrouter_id"],
                messages,
                temperature,
                max_tokens,
                extra_body={"usage": {"include": True}},  # ask OpenRouter for its cost
            )
            rec["latency_s"] = round(time.monotonic() - t0, 2)
            rec["raw_response"] = resp.choices[0].message.content or ""
            rec["finish_reason"] = resp.choices[0].finish_reason
            rec["json_mode"] = model["openrouter_id"] not in _JSON_MODE_UNSUPPORTED
            usage = resp.usage
            rec["transport_error"] = None
            break
        except Exception as exc:
            rec["transport_error"] = f"{type(exc).__name__}: {exc}"
            status = getattr(exc, "status_code", None)
            if status is not None and status != 429 and status < 500:
                break  # non-retryable client error
            time.sleep(2.0**attempt)

    decision, reason = parse_decision(rec["raw_response"])
    rec["parsed"] = decision.model_dump() if decision else None
    rec["parse_error"] = reason
    rec["prompt_tokens"] = int(usage_field(usage, "prompt_tokens") or 0)
    rec["completion_tokens"] = int(usage_field(usage, "completion_tokens") or 0)
    rec["reasoning_tokens"] = reasoning_tokens(usage)
    api_cost = usage_field(usage, "cost")
    rec["api_reported_cost_usd"] = float(api_cost) if api_cost is not None else None
    rec["cost_usd"] = (
        rec["api_reported_cost_usd"]
        if rec["api_reported_cost_usd"] is not None
        else CostLedger.compute_cost(
            rec["prompt_tokens"],
            rec["completion_tokens"],
            model.get("pricing_in_per_mtok"),
            model.get("pricing_out_per_mtok"),
        )
    )
    return rec


def project_full_run(records: list[dict], models: list[dict]) -> dict:
    """Project main-pass + probe cost from observed per-call costs.
    Calls are split evenly across models (same DPs x same models everywhere)."""
    calls_per_model = (FULL_RUN_MAIN_CALLS + FULL_RUN_PROBE_CALLS) // len(models)
    rows = []
    total = 0.0
    for model in models:
        recs = [r for r in records if r["model_name"] == model["name"] and r["prompt_tokens"] > 0]
        if not recs:
            rows.append({"model": model["name"], "mean_call_usd": None, "projected_usd": None})
            continue
        mean_cost = sum(r["cost_usd"] for r in recs) / len(recs)
        mean_prompt = sum(r["prompt_tokens"] for r in recs) / len(recs)
        mean_completion = sum(r["completion_tokens"] for r in recs) / len(recs)
        projected = mean_cost * calls_per_model
        total += projected
        rows.append(
            {
                "model": model["name"],
                "mean_prompt_tok": round(mean_prompt),
                "mean_completion_tok": round(mean_completion),
                "mean_call_usd": mean_cost,
                "calls": calls_per_model,
                "projected_usd": projected,
            }
        )
    return {"rows": rows, "total_usd": total, "calls_per_model": calls_per_model}


def write_report(
    records: list[dict],
    dps: list[DecisionPoint],
    projected_usd: float,
    total_usd: float,
    projection: Optional[dict] = None,
) -> None:
    lines: list[str] = []
    add = lines.append
    add("# BOXBOX smoke test — real OpenRouter connectivity")
    add("")
    add(f"- Run at: {datetime.now(timezone.utc).isoformat(timespec='seconds')} UTC")
    add(
        f"- Prompt version: {PROMPT_VERSION} | temperature 0.0 | 1 sample | max_tokens from run.yaml"
    )
    add(f"- Worst-case projected cost: ${projected_usd:.4f} (cap ${SMOKE_CAP_USD:.2f})")
    add(f"- **Actual total spend: ${total_usd:.4f}**")
    add("")
    add("## Decision points")
    add("")
    for dp in dps:
        add(f"- `{dp.dp_id}` — Type {dp.dp_type}, {dp.race_id}, lap {dp.lap}, driver {dp.driver}")
        add(f"  - Question: {dp.question}")
    add("")
    add("## Summary")
    add("")
    add(
        "| model | dp | ok | action | compound | prompt tok | completion tok | reasoning tok "
        "| json mode | cost USD | latency s |"
    )
    add("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in records:
        ok = "yes" if r["parsed"] else ("ERROR" if r["transport_error"] else "PARSE-FAIL")
        action = r["parsed"]["action"] if r["parsed"] else "—"
        compound = (r["parsed"].get("compound") or "—") if r["parsed"] else "—"
        rtok = r["reasoning_tokens"] if r["reasoning_tokens"] is not None else "n/r"
        lat = r["latency_s"] if r["latency_s"] is not None else "—"
        jm = {True: "yes", False: "fallback", None: "—"}[r.get("json_mode")]
        add(
            f"| {r['model_name']} | {r['dp_id']} | {ok} | {action} | {compound} "
            f"| {r['prompt_tokens']} | {r['completion_tokens']} | {rtok} | {jm} "
            f"| {r['cost_usd']:.6f} | {lat} |"
        )
    add("")
    add(
        "`reasoning tok = n/r` means the API did not report a separate reasoning-token count. "
        "`json mode = fallback` means the provider rejected response_format=json_object and the "
        "call was retried without it."
    )
    add("")
    if projection is not None:
        add("## Full-run cost projection")
        add("")
        add(
            f"Projected from this run's observed per-call costs: {FULL_RUN_MAIN_CALLS} main-pass "
            f"+ {FULL_RUN_PROBE_CALLS} probe calls = {FULL_RUN_MAIN_CALLS + FULL_RUN_PROBE_CALLS} "
            f"calls ({projection['calls_per_model']} per model)."
        )
        add("")
        add(
            "| model | mean prompt tok | mean completion tok | mean $/call | calls | projected USD |"
        )
        add("|---|---|---|---|---|---|")
        for row in projection["rows"]:
            if row["mean_call_usd"] is None:
                add(f"| {row['model']} | — | — | — | — | no usable calls |")
                continue
            add(
                f"| {row['model']} | {row['mean_prompt_tok']} | {row['mean_completion_tok']} "
                f"| {row['mean_call_usd']:.6f} | {row['calls']} | {row['projected_usd']:.2f} |"
            )
        add("")
        add(
            f"**Projected full-run total: ${projection['total_usd']:.2f}** (cap in run.yaml: $20.00)"
        )
        add("")
    add("## Per-call detail")
    for r in records:
        add("")
        add(f"### {r['model_name']} × `{r['dp_id']}`")
        add("")
        add(f"- OpenRouter id: `{r['model_id']}`")
        add(
            f"- Timestamp: {r['timestamp_utc']} | finish_reason: `{r['finish_reason']}` | latency: {r['latency_s']}s"
        )
        add(
            f"- Tokens: prompt {r['prompt_tokens']}, completion {r['completion_tokens']}, "
            f"reasoning {r['reasoning_tokens'] if r['reasoning_tokens'] is not None else 'not reported'}"
        )
        api_c = r["api_reported_cost_usd"]
        add(
            f"- Cost: ${r['cost_usd']:.6f} "
            f"({'API-reported' if api_c is not None else 'computed from config pricing'})"
        )
        if r["transport_error"]:
            add(f"- **Transport error:** `{r['transport_error']}`")
        add("")
        add("Raw response (full):")
        add("")
        add("````text")
        add(r["raw_response"] if r["raw_response"] else "<empty>")
        add("````")
        add("")
        if r["parsed"]:
            add("Parsed JSON:")
            add("")
            add("```json")
            add(json.dumps(r["parsed"], indent=2))
            add("```")
        else:
            add(f"**Parse failure:** {r['parse_error']}")
    add("")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    load_dotenv(REPO_ROOT / ".env")
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY missing from .env - aborting (no calls made).")
        return 2
    os.environ["ALLOW_SPEND"] = "1"  # scoped to this process only

    run_cfg = load_config("run")
    temperature = 0.0
    max_tokens = int(run_cfg.get("max_tokens", 350))

    models = [m for m in load_config("models")["models"] if m.get("enabled")]
    dps = pick_decision_points()

    # ---- upfront worst-case projection: every completion at full max_tokens ----
    projected = sum(
        worst_case_call_cost(m, estimate_prompt_tokens(dp), max_tokens)
        for m in models
        for dp in dps
    )
    print(f"{len(models)} models x {len(dps)} DPs = {len(models) * len(dps)} calls")
    print(f"Worst-case projected cost: ${projected:.4f} (cap ${SMOKE_CAP_USD:.2f})")
    if projected > SMOKE_CAP_USD:
        print("ABORT: projection exceeds cap - no calls made.")
        return 3

    from openai import OpenAI

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1", api_key=os.environ["OPENROUTER_API_KEY"]
    )
    ledger = CostLedger(spend_cap_usd=float(run_cfg.get("spend_cap_usd", 20.0)))

    records: list[dict] = []
    total = 0.0
    for model in models:
        for dp in dps:
            worst_next = worst_case_call_cost(model, estimate_prompt_tokens(dp), max_tokens)
            if total + worst_next > SMOKE_CAP_USD:
                print(
                    f"ABORT mid-run: ${total:.4f} spent + ${worst_next:.4f} worst-case next exceeds cap."
                )
                write_report(records, dps, projected, total)
                return 3
            print(f"calling {model['name']} on {dp.dp_id} ...", flush=True)
            rec = call_model(client, model, dp, temperature, max_tokens)
            records.append(rec)
            total += rec["cost_usd"]
            # mirror into the central cost ledger
            from boxbox.data.schemas import CallResult

            ledger.record(
                CallResult(
                    dp_id=dp.dp_id,
                    model_name=model["name"],
                    model_id=model["openrouter_id"],
                    prompt_version=PROMPT_VERSION,
                    temperature=temperature,
                    repeat_index=0,
                    raw_response=rec["raw_response"],
                    invalid=rec["parsed"] is None,
                    error=rec["transport_error"]
                    or (rec["parse_error"] if not rec["parsed"] else None),
                    prompt_tokens=rec["prompt_tokens"],
                    completion_tokens=rec["completion_tokens"],
                    cost_usd=rec["cost_usd"],
                    timestamp_utc=rec["timestamp_utc"],
                )
            )

    projection = project_full_run(records, models)
    write_report(records, dps, projected, total, projection)
    n_ok = sum(1 for r in records if r["parsed"])
    print(f"\n{n_ok}/{len(records)} calls returned valid decisions")
    print(f"TOTAL SPEND: ${total:.4f}")
    print(
        f"FULL-RUN PROJECTION ({FULL_RUN_MAIN_CALLS} main + {FULL_RUN_PROBE_CALLS} probe calls): "
        f"${projection['total_usd']:.2f}"
    )
    for row in projection["rows"]:
        if row["mean_call_usd"] is not None:
            print(
                f"  {row['model']:<18} ${row['mean_call_usd']:.6f}/call x {row['calls']} "
                f"= ${row['projected_usd']:.2f}"
            )
    print(f"-> {OUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
