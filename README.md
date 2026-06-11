# BOXBOX

**Can frontier LLMs call an F1 race?** BOXBOX reconstructs real strategy decision points
from 2026 Formula 1 races — *pit now or stay out? which compound?* — feeds the identical
frozen race state to multiple frontier models, and scores every call against a
hindsight-optimal strategy computed by a race simulator.

Because every completed 2026 race post-dates all current models' training data, the test
set is contamination-proof. A 2024/2025 control set measures the contamination gap.

## Quick start

```bash
pip install -r requirements.txt
pytest
python scripts/build_dataset.py          # ingest races -> extract decision points
python scripts/run_benchmark.py --mock   # run models (mock mode: $0, deterministic)
python scripts/score_results.py          # score + build leaderboard
python -m boxbox.live.replay --race monaco-2026 --speed 60 --mock   # live-loop replay
```

Outputs land in `outputs/`: `leaderboard.md`, `leaderboard.csv`, `leaderboard.json`
(consumed by `site/index.html`), calibration figures, cost ledger, live log.

Real model runs require `.env` with `OPENROUTER_API_KEY` and `ALLOW_SPEND=1`
(see `.env.example`), plus `python scripts/verify_models.py` to resolve model IDs.

## How it works

1. **Ingest** (`boxbox.data`) — FastF1 (OpenF1 fallback) → normalized `RaceData`.
2. **Extract** (`boxbox.extract`) — rule-based decision points: pit-stop neighborhoods,
   SC/VSC moments, undercut threats. A decision point at lap *t* contains zero
   information from after lap *t−1* (plus the current track status). Leakage is tested.
3. **Simulate** (`boxbox.sim`) — per-car tyre-degradation fits + pit-loss estimates →
   counterfactual total remaining race time for any candidate strategy → hindsight optimum.
4. **Harness** (`boxbox.harness`) — identical prompts to every model via OpenRouter,
   strict JSON answers, disk cache, cost ledger, mock mode.
5. **Score** (`boxbox.score`) — `delta_seconds = sim(model action) − sim(optimal)`;
   plus beat-the-team rate, invalid-output rate, consistency flip rate → leaderboard.
6. **Live** (`boxbox.live`) — Sunday demo loop: poll OpenF1, trigger decisions, draft
   (never post) social updates. Replay mode runs historic races through the same loop.

## Project docs

- `docs/DECISIONS.md` — every assumption and threshold, with rationale.
- `docs/LIMITATIONS.md` — honest limitations list (feeds the paper).
- `docs/MORNING_REPORT.md` — build status report.
- `paper/draft.md` — paper skeleton.
