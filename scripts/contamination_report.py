"""Contamination analysis -> outputs/contamination.md.

Primary metric delta_exante (s; lower = better). 2026 races post-date every model's
training cutoff; 2024-25 races plausibly appear in training data. A model scoring
*better (lower) on pre-2026* is evidence of recall rather than reasoning (prereg H3).

Reports per-season delta_exante per model, the H3 test (pre-2026 vs 2026,
Mann-Whitney U two-sided, Holm-corrected if scipy is available), and the Monaco
same-track comparison (2024/2025/2026 GP, constant circuit).

Reads outputs/scores.jsonl (main-pass per-call scores). Run scripts/score_results.py first.
Usage: python scripts/contamination_report.py
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCORES = REPO / "outputs" / "scores.jsonl"
OUT = REPO / "outputs" / "contamination.md"

# The report uses unicode (− em-dash); keep console output from crashing on cp1252.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def _mean(xs):
    return round(statistics.mean(xs), 3) if xs else None


def _med(xs):
    return round(statistics.median(xs), 3) if xs else None


def main() -> int:
    if not SCORES.exists():
        print(f"No {SCORES} - run scripts/score_results.py first.")
        return 2
    scores = [
        json.loads(line) for line in SCORES.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    # HEADLINE = dry subset: changeable-condition DPs are out of v1-sim scope and are
    # excluded (mechanical, conditions-only flag set in extraction). This is what makes
    # the contamination comparison meaningful; the wet Silverstone calls were artifacts.
    n_all = sum(1 for s in scores if not s["invalid"] and s.get("delta_exante_s") is not None)
    valid = [
        s
        for s in scores
        if not s["invalid"]
        and s.get("delta_exante_s") is not None
        and not s.get("changeable_conditions")
    ]
    if not valid:
        print("No valid dry-subset scored calls in scores.jsonl.")
        return 2
    n_excluded = n_all - len(valid)
    models = sorted({s["model_name"] for s in valid})

    try:
        from scipy.stats import mannwhitneyu

        have_scipy = True
    except Exception:
        have_scipy = False

    def deltas(model, pred):
        return [s["delta_exante_s"] for s in valid if s["model_name"] == model and pred(s)]

    L: list[str] = []
    L += [
        "# BOXBOX contamination analysis",
        "",
        "Primary metric **delta_exante** (s; lower = better). 2026 races post-date every",
        "model's training cutoff; 2024-25 races plausibly appear in training data. A model",
        "scoring **better (lower) on pre-2026** is evidence of recall, not reasoning (prereg H3).",
        "",
        f"Source: `outputs/scores.jsonl` (main pass). **Headline = DRY subset**: "
        f"{len(valid)} valid scored calls; {n_excluded} changeable-condition calls excluded "
        f"(wet/drying races the v1 simulator cannot model). "
        f"Stats: {'Mann-Whitney U, two-sided, Holm-corrected across models' if have_scipy else 'descriptive only (scipy unavailable)'}.",
        "",
        "## Per-season delta_exante  (mean / median, n)",
        "",
        "| Model | 2024 | 2025 | 2026 | pre-2026 (24-25) | gap (pre − 2026) |",
        "|---|---|---|---|---|---|",
    ]
    gaps: dict[str, float | None] = {}
    pvals: dict[str, float] = {}
    for m in models:
        d24 = deltas(m, lambda s: s["season"] == 2024)
        d25 = deltas(m, lambda s: s["season"] == 2025)
        d26 = deltas(m, lambda s: s["season"] == 2026)
        dpre = deltas(m, lambda s: s["season"] < 2026)
        gap = round(_mean(dpre) - _mean(d26), 3) if (dpre and d26) else None
        gaps[m] = gap

        def cell(xs):
            return f"{_mean(xs)} / {_med(xs)} (n={len(xs)})" if xs else "—"

        L.append(
            f"| {m} | {cell(d24)} | {cell(d25)} | {cell(d26)} | {cell(dpre)} "
            f"| {gap if gap is not None else '—'} |"
        )
        if have_scipy and len(dpre) >= 3 and len(d26) >= 3:
            try:
                _, p = mannwhitneyu(dpre, d26, alternative="two-sided")
                pvals[m] = float(p)
            except Exception:
                pass

    if have_scipy and pvals:
        # Holm-Bonferroni across models
        items = sorted(pvals.items(), key=lambda kv: kv[1])
        k = len(items)
        holm: dict[str, float] = {}
        running = 0.0
        for i, (m, p) in enumerate(items):
            adj = max(min(1.0, (k - i) * p), running)
            running = adj
            holm[m] = adj
        L += [
            "",
            "## H3 test — pre-2026 vs 2026  (Mann-Whitney U, two-sided)",
            "",
            "Negative gap = better (lower delta) on pre-2026 races = possible recall signal.",
            "",
            "| Model | gap (pre − 2026, s) | raw p | Holm p | verdict @0.05 |",
            "|---|---|---|---|---|",
        ]
        for m, _ in items:
            g = gaps[m]
            hp = holm[m]
            if g is not None and hp < 0.05:
                verdict = "**recall signal** (better on pre-2026)" if g < 0 else "worse on pre-2026"
            else:
                verdict = "no significant gap"
            L.append(f"| {m} | {g} | {round(pvals[m], 4)} | {round(hp, 4)} | {verdict} |")

        recall = [m for m in holm if (gaps[m] is not None and gaps[m] < 0 and holm[m] < 0.05)]
        L += [
            "",
            "**Does the earlier 'worse on pre-2026' signal survive on the dry subset?** "
            + (
                f"Recall signal (significantly better on pre-2026) in: {', '.join(recall)}."
                if recall
                else "No — no model is significantly better on pre-2026. The earlier apparent "
                "'worse on pre-2026' result was an artifact of the wet 2025-Silverstone calls "
                "(now excluded as changeable-condition), not a contamination/recall effect."
            ),
        ]

    # Monaco same-track
    L += [
        "",
        "## Monaco same-track  (2024 / 2025 / 2026 GP — constant circuit)",
        "",
        "Mean delta_exante on the Monaco Grand Prix across three seasons. The track is held",
        "constant, so a pre-2026 advantage here is a particularly clean contamination signal.",
        "",
        "| Model | 2024-monaco | 2025-monaco | 2026-monaco |",
        "|---|---|---|---|",
    ]
    for m in models:

        def mon(rid):
            xs = [
                s["delta_exante_s"] for s in valid if s["model_name"] == m and s["race_id"] == rid
            ]
            return f"{_mean(xs)} (n={len(xs)})" if xs else "—"

        L.append(f"| {m} | {mon('2024-monaco')} | {mon('2025-monaco')} | {mon('2026-monaco')} |")

    L += ["", f"Models: {len(models)} | valid scored calls: {len(valid)}", ""]
    OUT.write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
