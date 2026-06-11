# MORNING REPORT — BOXBOX overnight build

*Written by Claude Code, night of 2026-06-10 → 06-11. Everything below ran on this
machine tonight; every number is reproducible with the commands in "How to see
everything".*

## TL;DR

The entire offline pipeline works end-to-end in mock mode: **10 races ingested
(FastF1 worked for all 2026 races — no OpenF1 fallback needed), 180 leakage-tested
decision points, simulator calibrated to 0.22 s/lap mean MAE (median 0.09), a full
mock leaderboard, the live-loop replay of Monaco 2026 at 60×, the static site, paper
figures, and the paper skeleton. 30/30 tests green. $0.00 spent.**

## Status by priority

| Priority | Status | Notes |
|---|---|---|
| P0 scaffolding + schemas + 2025 ingestion | **done** | Monaco 2025 validated the pipeline shape first |
| P1 six 2026 races ingested | **done** | all via FastF1 3.8.3; OpenF1 fallback implemented but never triggered |
| P2 decision-point extraction + leakage tests | **done** | 18 DPs per race (cap binds everywhere); leakage test asserts state equality after deleting laps > t |
| P3 simulator + calibration | **done** | figures in `outputs/calibration/<race>.png`; see MAE table below |
| P4 mock harness + scoring + leaderboard | **done** | 180 DPs × 6 models × 3 repeats = 3240 calls; rerun = 100% cache hits, 0 new calls |
| P5 live replay runner | **done** | Monaco 2026 at 60×; `outputs/live_log.md` has SC/rival-pit/tyre-age triggered calls + draft posts |
| P6 smoke test | **skipped — no OPENROUTER_API_KEY / ALLOW_SPEND in env** (per §2 this is the required behavior) | polish + extra tests done instead |
| P7 contamination dataset | **done** | Bahrain 2024, Monaco 2024, Monaco 2025, Silverstone 2025; all DPs season-tagged; season-gap figure template ready |
| P8 leaderboard site | **done** | `site/index.html`, dark theme, sortable, file://-safe (manual file picker fallback when the browser blocks local fetch) |
| P9 figure templates | **done** | 5 figures in `outputs/figures/` incl. a bonus contamination-gap chart |
| P10 paper skeleton | **done** | `paper/draft.md` with full Method section |

## Per-race decision points and calibration

| Race | DPs | A/B/C | Calibration MAE (s/lap) | Source |
|---|---|---|---|---|
| 2026 Australia | 18 | 0/18/0 | 0.480 | FastF1 |
| 2026 China | 18 | 0/10/8 | 0.083 | FastF1 |
| 2026 Japan | 18 | 0/10/8 | 0.208 | FastF1 |
| 2026 Miami | 18 | 0/9/9 | 0.475 | FastF1 |
| 2026 Canada | 18 | 0/18/0 | 0.302 | FastF1 |
| 2026 Monaco | 18 | 0/13/5 | 0.100 | FastF1 |
| 2024 Bahrain | 18 | 0/0/18 | 0.045 | FastF1 |
| 2024 Monaco | 18 | 9/0/9 | 0.144 | FastF1 |
| 2025 Monaco | 18 | 0/0/18 | 0.205 | FastF1 |
| 2025 Silverstone | 18 | 0/10/8 | 0.177 | FastF1 |

**Overall: 180 DPs; calibration MAE 0.222 s/lap mean, 0.090 median** — well under the
1.5 s/lap credibility bar. Two calibration problems were found and fixed during the
night (collinear single-stint fits exploding; Miami's damp-phase laps) — see
DECISIONS.md #13–#19. Per-race scatter+histogram figures: `outputs/calibration/`.

Note the cap (18/race) binds everywhere and the B > C > A priority means Type A
points only survive in races with no SC and few close battles. If you want guaranteed
Type A representation, see QUESTIONS #2.

## FastF1 vs OpenF1 for 2026

FastF1 3.8.3 loaded all six 2026 races cleanly (quirk: some drivers fail its lap
accuracy check entirely — we don't gate on `IsAccurate`, see SKILL.md). The OpenF1
client + fallback ingestion path exists (`boxbox/data/openf1.py`) and is the planned
live source on Sunday, but was never needed for historic ingestion.

## Money

**$0.00 spent.** No key, no `ALLOW_SPEND` → mock everywhere. `outputs/cost_ledger.csv`
contains only $0.00 mock rows. `scripts/verify_models.py` made one free, unauthenticated
GET to OpenRouter `/models` and resolved all six models (real ids + prices now in
`config/models.yaml`, all `enabled: true, verified: true`).

## Tests

`pytest`: **30 passed** (leakage ×2, determinism, count bounds, exclusion windows,
SC typing, team-action labeling, 9 parser cases, sim monotonicity/pit-loss/optimal-
dominance/SC-pacing, cache zero-cost rerun, mock determinism, cost math, cap abort,
ledger resume, end-to-end mock). black + ruff clean.

## How to see everything

```powershell
.\venv\Scripts\Activate.ps1
pytest                                              # 30 green
python scripts/build_dataset.py                     # rebuilds dataset (cached, fast)
python scripts/run_benchmark.py --mock              # 3240 calls, all cache hits, $0
python scripts/score_results.py                     # prints the mock leaderboard
python -m boxbox.live.replay --race monaco-2026 --speed 60 --mock   # ~2.5 min
python analysis/figures.py                          # outputs/figures/*.png
start site\index.html                               # the leaderboard site
type outputs\live_log.md                            # replayed live log + draft posts
```

Key artifacts: `outputs/leaderboard.{md,csv,json}`, `outputs/scores.jsonl`,
`outputs/calibration/*.png`, `outputs/figures/*.png`, `outputs/live_log.md`,
`data/decision_points/*.json` + `manifest.json`, `paper/draft.md`.

## QUESTIONS FOR ANAS

1. **Hindsight-SC optimal.** The oracle knows future SC periods (deliberate, disclosed).
   Models can't. Fine for "distance from hindsight-perfect", but if you want an
   ex-ante-fair metric too, we could add a second score vs a no-future-SC simulator.
2. **Type B/C dominance.** With the 18/race cap and B > C > A priority, Type A pit-window
   points rarely survive (only Monaco 2024). Raise the cap, quota per type (e.g. 6/6/6),
   or accept as-is?
3. **Type C gap definition.** "Direct rival within 3.5s" is implemented as *any* car
   within 3.5s at the pre-stop lap, not just the adjacent car. Tighten to ±1 position?
4. **STAY valuation.** STAY = best legal deferred plan (charitable optimum). Alternative:
   value team-STAY with the team's *actual* later strategy. Current choice makes
   model-team agreement an exact tie; the alternative is more "real" but asymmetric.
5. **Invalid outputs** are excluded from delta means (separate column). Penalize instead?
6. **Repeats=3 at temperature 0** for real runs too? Costs 3× and reasoning models may
   not be deterministic anyway; flip rate is only meaningful with repeats ≥ 2.
7. **Rejoin penalty** is 0s (config `simulator.rejoin_penalty_s`). Want a sensitivity run
   at 2–4s before the paper?
8. **gemini-3.1-pro resolved to `google/gemini-3.1-pro-preview`** — confirm that's the
   intended target. Also confirm prompt wording + per-model reasoning-effort settings
   before real runs.
9. **Spend cap is $1.00 in run.yaml.** A full real run is 180 DPs × 6 models × 3 repeats;
   with verified prices and ~1.6k tokens/call this is roughly $15–25 (Fable 5 dominates
   at $10/$50 per MTok). Set the real budget and repeats and I'll project precisely.
10. **2026 Australia & Canada had no Type C points** because every SC fell early enough
    to flood the cap with Type B. OK, or quota as in #2?
11. **Mock invalid rate (4%) and PIT rate (30%)** are arbitrary (run.yaml). Fine for
    plumbing; flagging that mock leaderboard ordering is meaningless by construction.

## Suggested next session

1. Decide Q1–Q5 + Q9 (metric design + budget), then: `verify_models` re-check →
   real smoke test (3 DPs × 2 cheapest) under the $1 cap → inspect raw outputs.
2. Full real benchmark run with chosen repeats; regenerate leaderboard/site/figures.
3. Dry-run the live loop against OpenF1 during FP/quali (Sat) to validate the
   OpenF1LiveSource path before Sunday; wire `live_models` to real (non-mock) runner.
4. Sunday: `live_runner` during the Barcelona GP; human posts the drafts.
5. Paper: fill Results, add contamination-gap stats (per-season deltas already in
   leaderboard.json), tighten Limitations.

ALL PRIORITIES COMPLETE
