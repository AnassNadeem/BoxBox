> This is the autonomous build brief used to direct Claude Code for the initial end-to-end
> pipeline build. It is kept for transparency into the development process. All design
> decisions, thresholds, and judgment calls are logged in `docs/DECISIONS.md`, and the
> scientific design is fixed by the preregistration tags (see README).

---

# OVERNIGHT_TASK.md — BOXBOX Build Brief

You are Claude Code, working autonomously overnight. Your operator (Anas) is asleep.
Read this entire file before writing any code. Execute in priority order. Commit often.

---

## 1. MISSION & CONTEXT

**Project:** BOXBOX — a benchmark testing whether frontier LLMs can make Formula 1 race
strategy decisions. We reconstruct real "decision points" from 2026 F1 races (pit now or
stay out? which tyre compound?), feed identical frozen race states to multiple models via
OpenRouter, and score their calls against a hindsight-optimal strategy computed by a race
simulator. Output: a leaderboard, an analysis paper (preprint), and a live demo during the
Barcelona GP on Sunday June 14, 2026.

**Why 2026 races:** every completed 2026 race post-dates all models' training data, so the
test set is contamination-proof. Completed 2026 races: Australia, China, Japan, Miami,
Canada, Monaco. (Bahrain and Saudi Arabia 2026 were cancelled — do not query them.)

**Deadline pressure:** the live demo is Sunday. Tonight's job is the entire offline
pipeline, working end-to-end in mock mode, plus a replay-based live runner. Real API
spend and final analysis happen later with Anas.

**Models that will eventually run (do NOT call them tonight except optional smoke test):**
claude-fable-5, claude-opus-4.8, gpt-5.5, gemini-3.1-pro, deepseek-v3.2, claude-haiku-4.5
— all via OpenRouter. Exact OpenRouter IDs must be resolved by `scripts/verify_models.py`.

---

## 2. OPERATING RULES (HARD CONSTRAINTS)

1. **Money:** Default mode is MOCK — no network calls to paid model APIs. If and only if
   the env var `OPENROUTER_API_KEY` exists AND `ALLOW_SPEND=1`, you may run ONE smoke test:
   max 3 decision points × 2 cheapest models, hard-capped at $1.00 total computed cost.
   Abort all paid calls beyond that. Log every call's token usage and computed cost.
2. **Publishing:** Do not post, publish, upload, or share anything anywhere. No GitHub
   pushes to remotes unless a remote is already configured (local commits are fine and
   encouraged). No social media, no package registries.
3. **Secrets:** Never write API keys into code or commits. Use `.env` (gitignored) +
   `.env.example` (committed, with placeholder values).
4. **Honesty artifacts:** Every assumption, threshold, or judgment call you make goes into
   `docs/DECISIONS.md` with one-line rationale. You have authority to make these calls;
   you have the obligation to log them.
5. **When uncertain about an external API** (FastF1, OpenF1, OpenRouter), fetch the current
   official docs from the web and follow them. Do not guess function signatures.
6. **No MCP servers.** Not needed for this project. Do not install or configure any.
7. **Commit discipline:** Small commits, imperative messages, after every working unit.
   If you crash or hit limits, the repo must be resumable from commits + MORNING_REPORT.md.
8. **Python:** 3.11+, type hints everywhere, pydantic v2 for schemas, pytest for tests,
   black + ruff formatting. No core logic in notebooks. Allowed deps: fastf1, pandas,
   numpy, scipy, matplotlib, pydantic, httpx, requests, pyyaml, python-dotenv, openai
   (as OpenRouter client), pytest, rich. Ask-free; anything else, justify in DECISIONS.md.

---

## 3. SETUP TASKS (do these first)

- Create `CLAUDE.md` at repo root: project overview, conventions, how to run tests,
  module map, and the operating rules above. This is project memory for future sessions.
- Create a project skill at `.claude/skills/f1-data/SKILL.md` documenting: FastF1 session
  loading patterns, lap dataframe column meanings, track status codes (SC/VSC), known
  data quirks discovered tonight, OpenF1 endpoint map. Update it as you learn.
- Repo scaffolding per the structure in §4. `data/` and `outputs/` are gitignored except
  `.gitkeep`. FastF1's own cache directory goes under `data/fastf1_cache/`.

---

## 4. REPOSITORY STRUCTURE

```
boxbox/
  CLAUDE.md
  OVERNIGHT_TASK.md          # this file
  README.md                  # short: what BOXBOX is, how to run
  requirements.txt
  .env.example
  config/
    models.yaml              # model list: openrouter_id, pricing in/out per MTok, enabled
    extraction.yaml          # all decision-point thresholds (see §6)
    run.yaml                 # temperature, max_tokens, repeats, spend_cap_usd
  src/boxbox/
    data/
      schemas.py             # pydantic: RaceState, CarState, DecisionPoint, ModelCall, Score
      ingest.py              # FastF1 loading, normalization to internal schema
      openf1.py              # OpenF1 REST client (historic + live), fallback ingestion
    extract/
      decision_points.py     # rule-based extraction per §6
    sim/
      degradation.py         # per-stint lap-time model fitting per §7
      race_sim.py            # counterfactual simulator per §7
      optimal.py             # search over alternative strategies → optimal + deltas
    harness/
      prompts.py             # prompt builder, PROMPT_VERSION constant, template in §8
      cache.py               # disk cache: sha256(model_id, prompt_version, dp_id, temp, rep)
      runner.py              # OpenRouter calls, retries, mock mode, cost ledger
      parse.py               # strict JSON parsing + validation; invalid → recorded metric
    score/
      scoring.py             # per-call: sim delta vs optimal, agreement with real team call
      leaderboard.py         # aggregation → markdown + CSV tables
    live/
      replay.py              # replay a historic race through the live loop at Nx speed
      live_runner.py         # Sunday loop: poll OpenF1, trigger decisions, log + draft posts
  scripts/
    verify_models.py         # GET OpenRouter /models, resolve exact IDs into config
    build_dataset.py         # end-to-end: ingest → extract → save decision points
    run_benchmark.py         # decision points × models (mock or real) → raw results
    score_results.py         # raw results → scores → leaderboard
  tests/
  docs/
    DECISIONS.md
    MORNING_REPORT.md        # write last, see §11
    LIMITATIONS.md           # running list for the paper
  data/                      # gitignored
  outputs/                   # gitignored
```

---

## 5. PRIORITY ORDER (if you run out of time/limits, lower numbers must be done)

- **P0** — Scaffolding, CLAUDE.md, schemas, FastF1 ingestion working on a KNOWN-GOOD 2025
  race first (use Bahrain 2025 or Monaco 2025) to validate the pipeline shape.
- **P1** — Ingestion of all six completed 2026 races. If FastF1 chokes on 2026 data,
  implement the OpenF1 fallback and document in DECISIONS.md. Normalize both paths into
  the same internal schema.
- **P2** — Decision-point extraction (§6) + leakage tests. Print per-race counts.
- **P3** — Simulator (§7) + calibration report (predicted vs actual stint times) saved as
  figures in outputs/. This is the scientific core; do it carefully.
- **P4** — Harness in mock mode (§8) + scoring + leaderboard generation, end-to-end:
  `build_dataset.py && run_benchmark.py --mock && score_results.py` must produce a
  (fake-data) leaderboard markdown.
- **P5** — Live replay runner (§9): replay Monaco 2026 at 60× through the live loop.
- **P6** — Optional smoke test under the §2 spend rules; polish; extra tests.

---

## 6. DECISION-POINT EXTRACTION SPEC

A DecisionPoint freezes everything a strategist knows at lap t for one focal car, with
ZERO information from after lap t. Extraction is rule-based — no hand-picking.

Default rules (thresholds live in `config/extraction.yaml`, log changes):

- **Type A, pit-stop neighborhoods:** for each real pit stop by any classified car, emit
  decision points at laps {stop−2, stop−1, stop} for that car. Question: pit now or stay?
- **Type B, SC/VSC moments:** on the first lap of each Safety Car or VSC period, emit a
  decision point for every car running in the top 10. These are the chaos moments.
- **Type C, undercut threats:** when a car's direct rival (gap ≤ 3.5s either direction)
  pits, emit a decision point for that car on the following lap.
- **Dedupe:** if multiple rules fire for the same (car, lap), keep one, priority B > C > A.
- **Cap:** max 18 decision points per race, trimmed by priority B > C > A, then by
  closeness of the battle (smaller relevant gap = keep).
- **Exclude:** first 3 laps, last 2 laps, cars already lapped, retiring cars within 3 laps
  of retirement (no leakage of the retirement!).

RaceState contents (the prompt payload): track name, total laps, current lap, weather
(air/track temp, rain bool), track status (green/SC/VSC), pit-loss estimate for this
track (computed in §7), focal car {position, compound, tyre age, compounds already used,
compounds available, last 3 lap times, gap ahead/behind with those cars' compound+age},
plus a compact top-10 summary table. All values derived ONLY from laps ≤ t.

**Tests required:** (a) leakage test — assert no field changes if future laps are deleted
from the input data; (b) determinism — same input, same extraction; (c) per-race counts
within sane bounds.

---

## 7. SIMULATOR SPEC (v1 — simple, honest, documented)

Purpose: given a decision point and a candidate action, estimate total remaining race time
for the focal car. Used to find the hindsight-optimal action and score model calls as
`delta_seconds = sim(action_model) − sim(action_optimal)`. Also record
`beat_team = sim(action_model) < sim(action_actual_team)`.

- **Lap-time model per car:** fit `lap_time = a + b·tyre_age + c·lap_number` per
  (car, compound) using that race's clean laps: exclude in/out laps, SC/VSC laps, laps
  with large traffic deltas if identifiable, and outliers (>3 MAD). `b` = degradation,
  `c` = fuel effect (expect small negative). If a compound has <4 clean laps for a car,
  fall back to team-mate fit, then field-median fit for that compound. Log fallback rates.
- **Pit loss per track:** median(in-lap + out-lap − 2 × clean-lap median) across all real
  stops in that race. Under SC, multiply by the measured SC factor if computable from the
  race's own SC-era stops, else default 0.55. Log which path was used.
- **Counterfactual rollout:** simulate ONLY the focal car's remaining laps under candidate
  strategies (pit on lap t..t+8 × each available compound, or stay to a later window),
  holding all other cars' actual behavior fixed. No traffic interaction in v1 except an
  optional flat rejoin penalty (default 0s, configurable). DOCUMENT this as the headline
  limitation in LIMITATIONS.md.
- **Optimal:** argmin over the candidate grid, subject to the two-compound rule (dry races).
- **Calibration (required):** for every real stint, compare simulated stint time vs actual.
  Save a scatter + error histogram to outputs/. Report MAE in MORNING_REPORT.md. If MAE is
  embarrassing (>1.5s/lap), investigate before proceeding; the benchmark's credibility is
  this number.

---

## 8. HARNESS SPEC

- **Prompt (v1, iterate with Anas later).** System: "You are the chief race strategist for
  the focal car's team. Decide using only the provided state. Output strict JSON, nothing
  else." User: serialized RaceState JSON + the question + output schema:
  `{"action": "PIT" | "STAY", "compound": "<one of available or null>",
    "confidence": 0.0-1.0, "rationale": "<max 50 words>"}`
  Set `PROMPT_VERSION = "v1"` and include it in every cache key.
- **Runner:** OpenRouter via the OpenAI-compatible client. Per call: temperature from
  run.yaml (default 0), max_tokens 350, JSON-mode/response-format where supported, one
  retry on parse failure, then record `invalid=True` (invalid-rate is a leaderboard
  column). Exponential backoff on 429/5xx. Read REAL token usage from the response for
  the cost ledger (reasoning models may bill thinking tokens — record what the API reports,
  never your estimate). Maintain `outputs/cost_ledger.csv`; abort run if projected total
  exceeds `run.yaml: spend_cap_usd`.
- **Mock mode:** `--mock` (default tonight): a deterministic fake model (seeded by dp_id +
  model_id) emits schema-valid decisions with realistic distribution (~30% PIT) and fake
  token counts. Entire downstream pipeline must run on mock output.
- **Cache:** every response (mock or real) written to disk immediately, keyed by
  sha256(model_id, PROMPT_VERSION, dp_id, temperature, repeat_index). Runner checks cache
  before any call. A second identical run must cost $0.
- **verify_models.py:** GET OpenRouter `/api/v1/models` (free), search for our six models,
  write resolved exact IDs + listed prices into config/models.yaml, print a table. If a
  model is missing, mark `enabled: false` with a note — do not guess substitutes.

---

## 9. LIVE RUNNER SPEC (Sunday)

- **replay.py first.** Feed Monaco 2026 (historic OpenF1 data) through the live loop at
  configurable speed (60× default). The live loop must not know it's a replay.
- **Loop:** poll OpenF1 (intervals, laps, pit, race_control, stints) every 30–60s; maintain
  incremental RaceState for top-10 cars; trigger decision prompts on: SC/VSC deployment,
  rival-pit detection (Type C rule), and focal cars whose tyre age crosses the window
  threshold (Type A proxy). Dedupe per (car, lap).
- **Output:** rich console log + append-only `outputs/live_log.md` with UTC timestamps,
  the state snapshot hash, the model call, and a DRAFT social post line per event
  ("Lap 23 — [model] says BOX for NOR, medium → hard. Rationale: ..."). DRAFTS ONLY —
  a human posts them. No network posting of any kind.
- **Models on live day:** read from config `live_models:` (will be claude-fable-5 and
  gpt-5.5). In tonight's replay use mock mode.
- Handle OpenF1 hiccups gracefully: stale data tolerance, never crash the loop, log gaps.

---

## 10. TESTS (pytest, all green before you stop)

1. Leakage test (§6) — the most important test in the repo.
2. Extraction determinism + per-race count bounds.
3. Cache: second run produces zero new "API" calls (assert via call-counter on mock).
4. Parser: valid JSON, JSON in markdown fences, truncated JSON, garbage → correct
   valid/invalid classification, no exceptions.
5. Simulator sanity: more tyre age → slower; adding a stop adds ~pit-loss; optimal never
   worse than team-actual by construction of the search space.
6. Cost ledger math: synthetic usage → correct USD totals; cap triggers abort.
7. End-to-end mock: dataset → benchmark → leaderboard completes and emits files.

---

## 11. END-OF-RUN: MORNING_REPORT.md (write this even if you crash early — write it
incrementally, update after each priority level)

Must contain: status per priority level (done/partial/blocked + why); per-race decision
point counts; simulator calibration MAE + figure paths; FastF1-vs-OpenF1 path taken for
2026 data; total money spent (expected: $0.00, ledger attached); test suite status; the
exact commands Anas should run to see everything; and a numbered list titled
**"QUESTIONS FOR ANAS"** — every judgment call worth revisiting (extraction thresholds,
prompt wording, reasoning-effort settings per model, rejoin penalty on/off, anything that
felt arbitrary). Finish with a suggested next-session task list.

## 12. DEFINITION OF DONE (tonight)

`pip install -r requirements.txt && pytest && python scripts/build_dataset.py &&
python scripts/run_benchmark.py --mock && python scripts/score_results.py &&
python -m boxbox.live.replay --race monaco-2026 --speed 60 --mock`
runs clean from a fresh clone and produces: decision-point dataset for 6 races, a mock
leaderboard, calibration figures, a replayed live log, and the three docs files.

Now begin. P0 first. Commit early, commit often.

---

## 13. EXTENDED PRIORITIES (continue past P6 in order; same rules apply)

- **P7 — Contamination dataset:** run the identical ingestion + extraction on 4–6 races
  from 2024 and 2025 (try: Bahrain 2024, Monaco 2024, Monaco 2025, Silverstone 2025;
  substitute any race that fails to load cleanly and log it). Tag every decision point
  with its season. Purpose: the contamination-gap experiment — do models score
  suspiciously better on races that may appear in their training data?
- **P8 — Leaderboard site:** `site/index.html` — single static page, vanilla JS + CSS,
  no build step, reading `outputs/leaderboard.json`: sortable leaderboard table,
  per-model cards (mean delta vs optimal, beat-team %, invalid %, flip rate), a short
  methodology section, clean dark design. Must work opened from file:// and be
  GitHub Pages-ready. Populate with the mock results tonight.
- **P9 — Figure templates:** `analysis/figures.py` generating from results data:
  leaderboard bar chart, score-delta distribution per model, per-race performance
  heatmap, consistency flip-rate chart. Render from mock data to `outputs/figures/`.
- **P10 — Paper skeleton:** `paper/draft.md` — abstract stub, intro outline, a FULL
  Method section written from §6–§8 of this brief in plain academic prose, Limitations
  imported from docs/LIMITATIONS.md, Results section with empty table placeholders.

## 14. COMPLETION SENTINEL

When ALL priorities P0–P10 satisfy the Definition of Done (§12) plus the extended
deliverables above, append this exact line on its own to docs/MORNING_REPORT.md:

ALL PRIORITIES COMPLETE

Do not write that line under any other circumstances — an external resume loop greps
for it to decide whether to relaunch you.
