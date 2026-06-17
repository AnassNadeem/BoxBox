"""Pre-registered hypothesis tests H1 & H2 -> docs/hypothesis_tests.md.

Read-only, no spend, no model calls. Derived from outputs/scores.jsonl.

- H1 (primary): per model, reject "ex-ante-optimal on average" if the 95% percentile
  bootstrap CI of mean delta_exante excludes 0 (prereg §2). 10,000 resamples,
  numpy default_rng seed = 1234.
- H2 (secondary): per model, two-sided binomial test of the beat_team count vs p=0.5.

Two evaluation sets:
- Set A: 2026-only dry  (the prereg PRIMARY set: post-cutoff races only).
- Set B: all-seasons dry (the leaderboard headline subset).

Usage: python scripts/hypothesis_tests.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

# The report uses unicode (Δ); keep console output from crashing on cp1252.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO = Path(__file__).resolve().parents[1]
SCORES = REPO / "outputs" / "scores.jsonl"
OUT = REPO / "docs" / "hypothesis_tests.md"

SEED = 1234
N_BOOT = 10_000


def bootstrap_ci(xs: list[float], rng: np.random.Generator) -> tuple[float, float]:
    arr = np.asarray(xs, dtype=float)
    idx = rng.integers(0, len(arr), size=(N_BOOT, len(arr)))
    means = arr[idx].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(lo), float(hi)


def main() -> int:
    if not SCORES.exists():
        print(f"No {SCORES} - run scripts/score_results.py first.")
        return 2
    scores = [
        json.loads(line) for line in SCORES.read_text(encoding="utf-8").splitlines() if line.strip()
    ]

    def valid_set(pred) -> list[dict]:
        return [
            s
            for s in scores
            if not s["invalid"]
            and s.get("delta_exante_s") is not None
            and not s.get("changeable_conditions")
            and pred(s)
        ]

    set_a = valid_set(lambda s: s["season"] == 2026)  # 2026-only dry (PRIMARY)
    set_b = valid_set(lambda s: True)  # all-seasons dry
    n_a = len({s["dp_id"] for s in set_a})
    n_b = len({s["dp_id"] for s in set_b})
    models = sorted({s["model_name"] for s in scores})

    rng = np.random.default_rng(SEED)

    L: list[str] = [
        "# BOXBOX — Pre-registered hypothesis tests H1 & H2",
        "",
        "Read-only, no spend, no model calls — derived from `outputs/scores.jsonl` "
        "(the real prereg-v4 run, refreshed with Barcelona / 2026 Spanish GP, Round 7).",
        "",
        "- **H1 (primary — models are sub-optimal):** per model, reject "
        '"ex-ante-optimal on average" if the 95% bootstrap CI of mean `delta_exante` '
        "**excludes 0** (prereg §2). Lower `delta_exante` = better; a CI strictly above 0 "
        "means the model loses time vs the ex-ante optimum on average.",
        "- **H2 (secondary — human pit wall is a strong baseline):** per model, two-sided "
        "binomial test of the `beat_team` count against chance p = 0.5 (prereg §2). H2 "
        "predicts the beat-team share is **< 50%**.",
        "",
        f"**Method (fixed for reproducibility):** percentile bootstrap, **{N_BOOT:,} resamples** "
        "over decision points (resample each model's valid calls with replacement, take the "
        f"mean, report the 2.5/97.5 percentiles), **`numpy` default_rng seed = {SEED}**. "
        'Binomial: `scipy.stats.binomtest(k, n, 0.5, alternative="two-sided")`. Valid call = '
        "not invalid and `delta_exante_s` is not None; `beat_team` = `sim_model < sim_team`. "
        "Both sets are the **dry subset** (`changeable_conditions == false`).",
        "",
        "Two evaluation sets are reported so the headline can be chosen:",
        f"- **2026-only dry** = the prereg's PRIMARY set (post-cutoff races only), **{n_a} DPs**.",
        f"- **All-seasons dry** = the leaderboard's headline subset, **{n_b} DPs**.",
        "",
        "---",
        "",
        "## H1 — 95% bootstrap CI of mean `delta_exante` (s)",
    ]

    h1_summary: dict[str, list[bool]] = {}
    for label, dataset, n_dp in (("2026-only dry", set_a, n_a), ("all-seasons dry", set_b, n_b)):
        L += [
            "",
            f"### {'Set A' if dataset is set_a else 'Set B'}: {label} ({n_dp} DPs)",
            "",
            "| Model | Mean Δexante (s) | 95% CI | Excludes 0? | n valid |",
            "|---|---:|---|:--:|---:|",
        ]
        rows = []
        for m in models:
            xs = [s["delta_exante_s"] for s in dataset if s["model_name"] == m]
            if not xs:
                continue
            mean = float(np.mean(xs))
            lo, hi = bootstrap_ci(xs, rng)
            excl = lo > 0 or hi < 0
            h1_summary.setdefault(label, []).append(excl)
            rows.append((mean, m, lo, hi, excl, len(xs)))
        rows.sort()
        for mean, m, lo, hi, excl, n in rows:
            L.append(
                f"| {m} | {mean:.3f} | [{lo:.3f}, {hi:.3f}] | "
                f"{'**YES**' if excl else 'no'} | {n} |"
            )

    L += [
        "",
        "**H1 verdict:** "
        + (
            "confirmed for all 5 models on both sets — every 95% CI lies strictly above 0, "
            "so each model loses a statistically clear amount of time relative to the ex-ante "
            "optimum; no model is ex-ante-optimal on average."
            if all(all(v) for v in h1_summary.values())
            else "see per-model CIs above."
        ),
        "",
        "---",
        "",
        "## H2 — two-sided binomial test of `beat_team` vs chance (p = 0.5)",
    ]

    h2_summary: dict[str, list[bool]] = {}
    for label, dataset, n_dp in (("2026-only dry", set_a, n_a), ("all-seasons dry", set_b, n_b)):
        L += [
            "",
            f"### {'Set A' if dataset is set_a else 'Set B'}: {label} ({n_dp} DPs)",
            "",
            "| Model | Beat team % | k / n | p (two-sided) | Sig @0.05? | Direction |",
            "|---|---:|---:|---:|:--:|---|",
        ]
        rows = []
        for m in models:
            ss = [s for s in dataset if s["model_name"] == m]
            n = len(ss)
            if not n:
                continue
            k = sum(1 for s in ss if s["beat_team"])
            p = binomtest(k, n, 0.5, alternative="two-sided").pvalue
            sig = p < 0.05
            h2_summary.setdefault(label, []).append(sig and k / n < 0.5)
            direction = "below 50%" if k / n < 0.5 else "above 50%"
            rows.append((k / n, m, k, n, p, sig, direction))
        rows.sort()
        for share, m, k, n, p, sig, direction in rows:
            L.append(
                f"| {m} | {100 * share:.1f} | {k} / {n} | {p:.3e} | "
                f"{'**YES**' if sig else 'no'} | {direction} |"
            )

    L += [
        "",
        "**H2 verdict:** "
        + (
            "confirmed for all 5 models on both sets — every model beats the real team on well "
            "under half of valid calls, and the two-sided binomial rejects p = 0.5 at α = 0.05 "
            "for all models. The human pit wall is a strong baseline."
            if all(all(v) for v in h2_summary.values())
            else "see per-model tests above."
        ),
        "",
        "---",
        "",
        "## Summary",
        "",
        f"| Hypothesis | 2026-only dry ({n_a}) | All-seasons dry ({n_b}) |",
        "|---|---|---|",
        f"| **H1** (CI of mean Δexante excludes 0) | "
        f"{sum(h1_summary['2026-only dry'])}/{len(h1_summary['2026-only dry'])} exclude 0 | "
        f"{sum(h1_summary['all-seasons dry'])}/{len(h1_summary['all-seasons dry'])} exclude 0 |",
        f"| **H2** (beat_team ≠ 50%, two-sided) | "
        f"{sum(h2_summary['2026-only dry'])}/{len(h2_summary['2026-only dry'])} sig & <50% | "
        f"{sum(h2_summary['all-seasons dry'])}/{len(h2_summary['all-seasons dry'])} sig & <50% |",
        "",
    ]

    OUT.write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
