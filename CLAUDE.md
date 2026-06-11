# BOXBOX — F1 Strategy Benchmark for LLMs

## What this is
A benchmark testing whether frontier LLMs can make Formula 1 race strategy decisions.
We reconstruct "decision points" from real 2026 F1 races (pit now or stay out? which
compound?), feed identical frozen race states to multiple models via OpenRouter, and
score their calls against a hindsight-optimal strategy computed by a race simulator.
2026 races post-date all models' training data → contamination-proof test set.

Completed 2026 races used: Australia, China, Japan, Miami, Canada, Monaco.
(Bahrain and Saudi Arabia 2026 were cancelled — never query them.)
Contamination-control races (P7): Bahrain 2024, Monaco 2024, Monaco 2025, Silverstone 2025.

## How to run everything
```powershell
.\venv\Scripts\Activate.ps1            # or: & .\venv\Scripts\python.exe ...
pip install -r requirements.txt
pytest                                  # all tests must be green
python scripts/build_dataset.py         # ingest -> extract -> data/decision_points/
python scripts/run_benchmark.py --mock  # mock model calls -> outputs/raw_results/
python scripts/score_results.py         # scores -> outputs/leaderboard.{md,csv,json}
python -m boxbox.live.replay --race monaco-2026 --speed 60 --mock
python scripts/verify_models.py         # free GET to OpenRouter /models, fixes config IDs
python analysis/figures.py              # paper figures from results -> outputs/figures/
```

## Module map
- `src/boxbox/data/schemas.py` — all pydantic v2 models: LapRecord, RaceData, RaceState,
  DecisionPoint, ModelDecision, CallResult, Score. Single source of truth for shapes.
- `src/boxbox/data/ingest.py` — FastF1 → RaceData normalization; saves JSON to
  `data/processed/{race_id}.json`. Race IDs look like `2026-monaco`.
- `src/boxbox/data/openf1.py` — OpenF1 REST client (historic + live) + fallback
  ingestion to the same RaceData schema.
- `src/boxbox/extract/decision_points.py` — rule-based Type A/B/C extraction (§6 of
  OVERNIGHT_TASK.md). State builder guarantees no info from laps > t-1 except current
  track status.
- `src/boxbox/sim/degradation.py` — per (driver, compound) lap-time fits with fallbacks.
- `src/boxbox/sim/race_sim.py` — counterfactual rollout of focal car only.
- `src/boxbox/sim/optimal.py` — strategy grid search → optimal action + per-action deltas.
- `src/boxbox/harness/` — prompts (PROMPT_VERSION), sha256 disk cache, OpenRouter runner
  with mock mode + cost ledger, strict JSON parser.
- `src/boxbox/score/` — per-call scoring + leaderboard aggregation.
- `src/boxbox/live/` — replay.py (historic data through live loop at Nx) and
  live_runner.py (Sunday's loop; drafts social posts, never publishes).
- `scripts/` — thin CLIs over the library.
- `site/index.html` — static leaderboard page reading outputs/leaderboard.json.
- `analysis/figures.py` — paper figures.

## Conventions
- Python 3.11+, full type hints, pydantic v2 (`model_dump`/`model_validate`), pytest.
- black + ruff. Run: `python -m black src tests scripts analysis && python -m ruff check --fix src tests scripts analysis`
- No core logic in notebooks. No MCP servers.
- All thresholds live in `config/extraction.yaml`; never hardcode.
- Time units: seconds (float) everywhere internally. Laps are 1-indexed ints.
- Every judgment call goes in `docs/DECISIONS.md` with one-line rationale.
- Data/outputs are gitignored; FastF1 cache lives in `data/fastf1_cache/`.

## Operating rules (hard constraints — from OVERNIGHT_TASK.md §2)
1. Default mode MOCK; paid calls only with OPENROUTER_API_KEY + ALLOW_SPEND=1, capped.
2. Never publish/post/push to remotes unless a remote is already configured.
3. Secrets only in `.env` (gitignored); `.env.example` carries placeholders.
4. Assumptions → `docs/DECISIONS.md`.
5. Uncertain about an external API → fetch official docs, don't guess.
6. Small imperative commits after every working unit.

## Key data facts (see .claude/skills/f1-data/SKILL.md for details)
- FastF1 lap columns used: Driver, LapNumber, LapTime, Compound, TyreLife, Stint,
  Position, PitInTime, PitOutTime, TrackStatus, IsAccurate, LapStartTime, Time, Team.
- TrackStatus codes: '1' green, '2' yellow, '4' SC, '5' red, '6' VSC deployed, '7' VSC ending.
  A lap's TrackStatus is a concatenation like '2645'.
- Decision point at lap t = info through end of lap t-1 + current track status. The
  question is "pit at the end of lap t?"
