# MORNING REPORT — BOXBOX overnight build

*Written by Claude Code, night of 2026-06-10 → 06-11; **updated 2026-06-11 after
Anas resolved Q1–Q11** (see DECISIONS.md #26–36). Everything below ran on this
machine; every number is reproducible with the commands in "How to see everything".*

## TL;DR

The entire offline pipeline works end-to-end in mock mode: **10 races ingested,
178 leakage-tested decision points under a 6/6/6 per-type quota, simulator
calibrated to 0.22 s/lap mean MAE (median 0.09, unchanged by today's changes), a
dual-oracle scoring system (ex-ante primary, hindsight secondary), a 20-DP
consistency probe, mock leaderboard + site + figures, and the paper Method updated.
43/43 tests green. $0.00 spent.**

## What changed in the 2026-06-11 resolution pass

1. **Type quota (Q2/Q10):** 6 A / 6 B / 6 C target inside the 18-per-race cap;
   a type short of 6 donates its slots B > C > A. Every 2026 race is now exactly
   6/6/6.
2. **Type C tightened (Q3):** the pitting rival must be within ±1 race position
   AND within 3.5s.
3. **Ex-ante oracle (Q1):** a second optimal-strategy computation with no
   knowledge of future SC/VSC (green assumed after the decision lap; the current
   lap's known status is kept). Both oracles are valued in the realized race, so
   `delta_exante` (PRIMARY) and `delta_hindsight` (secondary) share one currency
   and ex-ante can never beat hindsight (tested). Leaderboard, site, and figures
   headline `delta_exante`.
4. **Q-value framing (Q4):** confirmed in code and stated formally in
   paper/draft.md §3.2 — every action is scored as its Q-value.
5. **Run config (Q6/Q9):** main pass repeats=1, temperature=0, spend_cap_usd=20.
   New `scripts/run_consistency_probe.py`: the 20 highest cross-model-disagreement
   DPs (selection logged to `outputs/probe_selection.json`), all models × 5
   samples at temperature 1.0. **Flip rate comes only from the probe.**
6. Dataset rebuilt; full mock pipeline rerun; simulator fitting/calibration
   untouched.

## Per-race decision points and calibration

| Race | DPs | A/B/C | Calibration MAE (s/lap) | Source |
|---|---|---|---|---|
| 2026 Australia | 18 | 6/6/6 | 0.480 | FastF1 |
| 2026 China | 18 | 6/6/6 | 0.083 | FastF1 |
| 2026 Japan | 18 | 6/6/6 | 0.208 | FastF1 |
| 2026 Miami | 18 | 6/6/6 | 0.475 | FastF1 |
| 2026 Canada | 18 | 6/6/6 | 0.302 | FastF1 |
| 2026 Monaco | 18 | 6/6/6 | 0.100 | FastF1 |
| 2024 Bahrain | 18 | 6/0/12 | 0.045 | FastF1 |
| 2024 Monaco | 16 | 11/0/5 | 0.144 | FastF1 |
| 2025 Monaco | 18 | 6/0/12 | 0.205 | FastF1 |
| 2025 Silverstone | 18 | 6/6/6 | 0.177 | FastF1 |

**Overall: 178 DPs; calibration MAE 0.222 s/lap mean, 0.090 median** — identical to
the overnight numbers, confirming the ex-ante oracle sits on top of an unchanged
simulator. Races with no SC/VSC have B=0 and the slots flow to C then A; Monaco
2024 only has 16 candidates that survive the excludes at all.

## Mock pipeline state (today's rerun)

- Main pass: 178 DPs × 6 models × 1 repeat = **1068 calls**, $0.00.
- Probe: 20 DPs × 6 models × 5 samples = **600 calls**, $0.00 (selection +
  reasons in `outputs/probe_selection.json`).
- Leaderboard mode badge: MOCK — ordering is meaningless by construction
  (mock answers are random), it validates plumbing only.

## FastF1 vs OpenF1 for 2026

FastF1 3.8.3 loaded all six 2026 races cleanly (quirk: some drivers fail its lap
accuracy check entirely — we don't gate on `IsAccurate`, see SKILL.md). The OpenF1
client + fallback ingestion path exists (`boxbox/data/openf1.py`) and is the planned
live source on Sunday, but was never needed for historic ingestion.

## Money

**$0.00 spent, total, including today's rerun.** No key, no `ALLOW_SPEND` → mock
everywhere. `outputs/cost_ledger.csv` contains only $0.00 mock rows.
`scripts/verify_models.py` made one free, unauthenticated GET to OpenRouter
`/models` overnight and resolved all six models (real ids + prices in
`config/models.yaml`, all `enabled: true, verified: true`).

## Tests

`pytest`: **43 passed** (leakage ×2, determinism, quota unit tests ×5 +
integration, Type C ±1-position and gap-threshold tests, exclusion windows, SC
typing, team-action labeling, 9 parser cases, sim monotonicity/pit-loss/optimal-
dominance + Q-value consistency/SC-pacing, ex-ante ≥ hindsight ×2 + current-lap
status retention, probe selection ×3, cache zero-cost rerun, mock determinism,
cost math, cap abort, ledger resume, end-to-end mock incl. probe + flip-rate
provenance). black + ruff clean.

## How to see everything

```powershell
.\venv\Scripts\Activate.ps1
pytest                                              # 43 green
python scripts/build_dataset.py                     # rebuilds dataset (cached, fast)
python scripts/run_benchmark.py --mock              # main pass, $0
python scripts/run_consistency_probe.py --mock      # probe (after the main pass)
python scripts/score_results.py                     # leaderboard (flip rate from probe)
python -m boxbox.live.replay --race monaco-2026 --speed 60 --mock   # ~2.5 min
python analysis/figures.py                          # outputs/figures/*.png
start site\index.html                               # the leaderboard site
```

Key artifacts: `outputs/leaderboard.{md,csv,json}`, `outputs/scores.jsonl`,
`outputs/probe_scores.jsonl`, `outputs/probe_selection.json`,
`outputs/calibration/*.png`, `outputs/figures/*.png`, `outputs/live_log.md`,
`data/decision_points/*.json` + `manifest.json`, `paper/draft.md`.

## Q1–Q11 status

All resolved 2026-06-11 — see DECISIONS.md #26–36. Q1 (ex-ante oracle), Q2/Q10
(quota), Q3 (±1 position), Q4 (Q-value framing), Q6/Q9 (repeats=1 @ temp 0,
$20 cap, probe-only flip rate) implemented today. Q5, Q7, Q8, Q11 left as-is by
the resolution pass (rejoin penalty 0s and the gemini preview id should be
revisited before the real run / paper).

## Suggested next session

1. `verify_models` re-check → real smoke test (3 DPs × 2 cheapest models) under
   the $20 cap → inspect raw outputs.
2. Full real benchmark run (178 DPs × 6 models × 1 repeat) → then
   `run_consistency_probe.py --real` → regenerate leaderboard/site/figures.
3. Dry-run the live loop against OpenF1 during FP/quali (Sat) to validate the
   OpenF1LiveSource path before Sunday; wire `live_models` to real (non-mock)
   runner.
4. Sunday: `live_runner` during the Barcelona GP; human posts the drafts.
5. Paper: fill Results, add contamination-gap stats (per-season deltas already in
   leaderboard.json), tighten Limitations.

ALL PRIORITIES COMPLETE
