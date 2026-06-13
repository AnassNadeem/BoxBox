# BOXBOX — Preregistration

**Version history.** *prereg-v1* — original six-model design, frozen 2026-06-13 (tag
`prereg-v1`), preserved unedited in the "Preregistration (v1)" section below and in git
history. ***prereg-v2*** *(2026-06-13)* — model roster reduced from six to five after
Claude Fable 5 became inaccessible; see the amendment immediately below. Only the roster
changed; every other frozen element is identical to v1.

## Amendment v2 (2026-06-13) — Claude Fable 5 removed from the roster

prereg-v1 froze a **six-model** roster (§4 below). After it was frozen, **Claude Fable 5
became unavailable through the API**, so it is removed from the benchmark. The paid run
uses the **five remaining models**: claude-opus-4.8, gpt-5.5, gemini-3.1-pro,
deepseek-v3.2, claude-haiku-4.5. This supersedes the six-model roster in §4.

**Cause (verified against the provider's own statement).** On **2026-06-12** the US
government, citing national-security authorities, issued an **export-control directive
suspending all access to Claude Fable 5 and Claude Mythos 5** (Anthropic's notice,
linked from the API error itself: <https://www.anthropic.com/news/fable-mythos-access> —
"The US government, citing national security authorities, has issued an export control
directive to suspend all access to Fable 5 and Mythos 5"; the trigger was a demonstrated
jailbreak technique, and access to all other Anthropic models is unaffected). Anthropic
states it disagrees with the directive and is working to restore access.

**Empirical confirmation.** One real call to `anthropic/claude-fable-5` through the
normal benchmark `Runner` path on **2026-06-13T10:42:20Z** returned **HTTP 404** from
every OpenRouter provider (Anthropic, Amazon Bedrock, Google Vertex): *"Claude Fable 5
is not available. Please use Opus 4.8."* The call consumed 0 tokens and $0; the exact
error is recorded in `outputs/fable_unavailable_check.md`. Our cost ledger shows Fable 5
was still reachable on the morning of 2026-06-12 (six successful smoke-test calls at
09:57 and 10:09 UTC), so access ceased after the directive took effect — between those
calls and the 2026-06-13 check — rather than instantaneously at issuance.

**Captured Fable 5 data — separate observation, not in the leaderboard.** The three
Claude Fable 5 smoke-test calls captured on 2026-06-12 (decision points
`2026-australia-L007-COL-A`, `2026-china-L010-ANT-B`, `2026-japan-L018-ANT-C`; full
responses in `outputs/smoke_test_v2.md`) are **preserved** and will be reported only as
a **separate, time-limited observation** (n = 3, single-shot, not balanced across
decision types or races) — explicitly **not** part of the main leaderboard, which covers
the five available models over the full 178-DP dataset.

**Scope.** Only the model roster changes. The hypotheses, the `delta_exante` primary
metric, the 178-DP dataset and extraction rules, the simulator/oracle scoring, the
prompt (`v1`), and the run/probe configuration are all unchanged from prereg-v1, which
remains intact in git history (tag `prereg-v1`) and unedited below. Projected cost of the
five-model run: ~$10.90 (temp-0) / ~$12.27 with the temperature-1.0 probe, within the
$20 cap.

---

# BOXBOX — Preregistration (v1)

**Status: methodology frozen. This document is committed _before_ any full benchmark
results exist.**

At the time this file is committed and tagged `prereg-v1` (2026-06-13), the only model
outputs that exist are (a) deterministic **mock**-pipeline runs that exercise the code
without spend, and (b) an **18-call real connectivity smoke test** (6 models × 3
decision points; see `outputs/smoke_test_v2.md`, which is a local/gitignored artifact).
**The full main pass and the consistency probe have not been run, and no real
leaderboard has been computed.** This preregistration fixes the hypotheses, dataset,
metrics, models, and scoring procedure so that the forthcoming results cannot be
shaped by knowledge of how any model scores.

The frozen procedure is defined by the code and configuration at the commit carrying
this file (tag `prereg-v1`): `config/run.yaml`, `config/models.yaml`,
`config/extraction.yaml`, prompt `PROMPT_VERSION = "v1"` in
`src/boxbox/harness/prompts.py`, the simulator/oracle in `src/boxbox/sim/`, scoring in
`src/boxbox/score/`, and the judgment-call log in `docs/DECISIONS.md`. Any change to
these after this tag is an amendment and will be recorded as `prereg-v2`, etc.

---

## 1. Research question

Can frontier large language models make competent Formula 1 race-strategy decisions
(pit now or stay out; which tyre compound) under the information constraints of a real
pit wall, and is any apparent competence attributable to reasoning rather than
recall of documented races?

## 2. Hypotheses

Confirmatory hypotheses are **H1** and **H3**; the rest are secondary or exploratory.
All tests use α = 0.05. Where multiple models are tested for the same hypothesis,
p-values are Holm–Bonferroni corrected across the six models.

- **H1 (primary — models are sub-optimal and separable).** On the 108 post-cutoff
  2026 decision points, each model's mean `delta_exante` is **> 0** (every model loses
  time relative to the ex-ante optimum), and the six models are separable on this
  metric. *Decision rule:* for each model, reject "ex-ante-optimal on average" if the
  95% bootstrap CI (10,000 resamples over decision points) for mean `delta_exante`
  excludes 0. The headline ranking is by mean `delta_exante` ascending (lower = better).

- **H2 (human pit wall is a strong baseline — secondary).** For every model, the share
  of valid 2026 calls that beat the real team's decision (`beat_team`) is **< 50%**.
  *Test:* two-sided binomial test per model against p = 0.5.

- **H3 (primary — contamination / recall check).** For each model, `delta_exante` on the
  pre-cutoff 2024–25 races is **not better (not lower)** than on the 2026 races.
  *Test:* two-sided Mann–Whitney U on the per-decision-point `delta_exante`
  distributions, pre-cutoff vs 2026, per model, Holm-corrected. A **significantly lower
  (better) pre-cutoff** delta is interpreted as evidence of recall/contamination rather
  than reasoning; a null or worse pre-cutoff result supports the contamination-proof
  framing. We report the median gap (2024–25 minus 2026) as the effect size.

- **H4 (output validity — secondary).** Output-validity rate (`1 − invalid_pct`) is
  reported per model; invalid answers are **not excluded from the denominator** of
  validity but **are excluded from delta means** (counted in their own column). No
  model is dropped for invalidity.

- **H5 (answer consistency — exploratory).** On the 20 highest-disagreement decision
  points (the consistency probe), reasoning-enabled models show a lower **flip rate**
  than non-reasoning models. Directional, exploratory.

- **H6 (difficulty by type — exploratory).** Mean `delta_exante` differs across the
  three decision-point types — pit-window (A), safety-car (B), undercut-threat (C).

## 3. Metrics

All times are in seconds; lower is better. For a decision point at lap *t*, the
simulator assigns each candidate action its **Q-value**: the best achievable realized
remaining-race time conditional on taking that action at lap *t*, minimized over all
continuations in the candidate strategy space (see §5). Let `sim_model` be the Q-value
of the model's answer, `sim_exante_optimal` the realized time of the ex-ante oracle's
plan, `sim_optimal` the realized time of the hindsight oracle's plan, and `sim_team`
the Q-value of the real team's call.

- **`delta_exante = sim_model − sim_exante_optimal` — PRIMARY METRIC.** Distance from
  the optimum computed under the *models' own information set* (green-flag assumption
  for every lap after *t*; the current lap's track status is kept). This is the
  headline number and the basis of the ranking and of H1/H3.
- `delta_hindsight = sim_model − sim_optimal` — secondary context (optimum that knows
  the future SC/VSC timeline). By construction `sim_exante_optimal ≥ sim_optimal`, so
  `delta_exante ≤ delta_hindsight`.
- `delta_vs_team = sim_model − sim_team`; `beat_team = sim_model < sim_team` (strict,
  1e-9 tolerance).
- `agree_team_action` (same PIT/STAY as the team) and `agree_team_exact` (also same
  compound when pitting).
- `invalid` — the answer could not be parsed into the schema or could not be valued.

**Aggregation (per model), as implemented in `src/boxbox/score/leaderboard.py`:**
mean and median `delta_exante` and `delta_hindsight` over valid calls; `beat_team_pct`;
`agree_team_pct`; `invalid_pct` (over all calls); `flip_rate_pct` (probe only); and
per-race and per-season mean `delta_exante`. **The PRIMARY headline figure is the mean
`delta_exante` over the 108 2026 decision points** (the season-2026 per-season mean);
the per-era split is the input to the H3 contamination test.

## 4. Models (frozen roster, resolved OpenRouter IDs)

All six are `enabled: true` and `verified: true` against OpenRouter `/models` in
`config/models.yaml`. Pricing ($/M tokens, in/out) is recorded for the cost ledger
only and is not part of scoring.

| Model (config name) | Resolved OpenRouter ID | In | Out |
|---|---|---:|---:|
| claude-fable-5 | `anthropic/claude-fable-5` | 10.0 | 50.0 |
| claude-opus-4.8 | `anthropic/claude-opus-4.8` | 5.0 | 25.0 |
| gpt-5.5 | `openai/gpt-5.5` | 5.0 | 30.0 |
| gemini-3.1-pro | `google/gemini-3.1-pro-preview` | 2.0 | 12.0 |
| deepseek-v3.2 | `deepseek/deepseek-v3.2` | 0.2288 | 0.3432 |
| claude-haiku-4.5 | `anthropic/claude-haiku-4.5` | 1.0 | 5.0 |

The live Sunday demo uses a separate `live_models` subset (claude-fable-5, gpt-5.5);
it is **not** part of this benchmark and is out of scope for this preregistration.

## 5. Dataset (frozen)

Mechanically extracted from official FastF1 timing data (OpenF1 fallback), re-ingested
and recalibrated 2026-06-13. **178 decision points across 10 races**, by type
A (pit-window) = 65, B (safety-car) = 42, C (undercut-threat) = 71.

- **Primary evaluation set — 108 DPs from six 2026 races** (Australia, China, Japan,
  Miami, Canada, Monaco), all post-dating every evaluated model's training cutoff.
  (Bahrain 2026 and Saudi Arabia 2026 were cancelled and are never queried.)
- **Contamination-control set — 70 DPs from four pre-2026 races** (Bahrain 2024,
  Monaco 2024, Monaco 2025, Silverstone 2025), plausibly documented in training data.

**Extraction rules** (`config/extraction.yaml`, `src/boxbox/extract/decision_points.py`):
Type A = laps {s−2, s−1, s} around every real pit stop *s* by a classified car;
Type B = the first lap of each Safety Car / VSC period for cars running in the top 10;
Type C = the lap after a directly adjacent rival (within ±1 race position **and**
within 3.5 s) pits, for the threatened car. Overlaps for the same (car, lap) are
deduplicated with priority **B > C > A**. Each race is capped at **18** points under a
per-type quota of **6**; a short type donates unused slots to the others (B > C > A),
and within a type the closest battles are kept first. Excluded: first 3 laps, last 2
laps, lapped cars, and any DP within 3 laps of a car's retirement.

**Information freeze.** A decision point at lap *t* exposes only fields derived from
completed laps ≤ *t−1*, plus the track status current during lap *t*. A structural
leakage test asserts that deleting all laps > *t* changes no emitted field. Hindsight
fields (the team's actual action/compound) are stored for scoring and **never**
serialized into the prompt.

The dataset is regenerable via `python scripts/build_dataset.py --force`; per-race
counts, fitted-degradation reports, pit losses, and calibration MAE are in
`data/decision_points/manifest.json`.

## 6. Scoring oracle (simulator)

Per-(driver, compound) lap-time models `lap_time = a + b·tyre_age + c·lap_number` are
fit on clean laps (green, dry, no in/out laps, >3-MAD outliers removed), with a
driver → team-mate → field fallback chain; the fuel term is dropped where age and lap
number are collinear; predictions are clamped to physical bounds. Pit loss is the
median of (in-lap + out-lap − 2 × clean median) over the race's real stops; the SC-era
pit-loss factor is measured from the race's own SC stops where possible (default 0.55).

Given a decision point and a candidate action, the simulator rolls out **only the focal
car's** remaining laps, holding all other cars and the SC/VSC timeline fixed at what
actually happened; SC/VSC and rain-neutralized laps are charged at that lap's
field-median time. Candidate space: pit at the end of any lap from *t* to the
penultimate lap onto any available compound, or no further stop, subject to the
two-compound rule in dry races.

Two oracles share the same fitted models: the **hindsight oracle** minimizes realized
time (knows the future SC/VSC timeline); the **ex-ante oracle** minimizes time under a
green-flag assumption for every lap after *t* (the models' information set), then is
**valued in the realized race** so both baselines share one currency. The Q-value
framing (§3) is applied identically to model answers and to the team's call, so
agreement with the team at the decision instant scores as a tie.

**Calibration:** across the ten races the simulator reproduces real stint times with
mean MAE ≈ 0.22 s/lap (median 0.09). Per-race calibration figures ship with the build.
Known limitations are catalogued in `docs/LIMITATIONS.md` (authoritative): no traffic
interaction in rollouts, single-further-stop space, linear degradation, SC laps as
field-median time, residual hindsight in the ex-ante baseline (realized valuation, no
probabilistic SC model), scalar per-race pit loss.

## 7. Evaluation harness (frozen run configuration)

Identical prompt for every model — `PROMPT_VERSION = "v1"`:
- **System:** "You are the chief race strategist for the focal car's team. Decide using
  only the provided state. Output strict JSON, nothing else."
- **User:** serialized race state + the question + the output schema
  `{"action": "PIT"|"STAY", "compound": <one of compounds_available or null>,
  "confidence": 0.0–1.0, "rationale": "<max 50 words>"}`.

Frozen settings (`config/run.yaml`):

| Parameter | Value |
|---|---|
| temperature (main pass) | 0.0 |
| max_tokens | 1200 |
| repeats (main pass) | 1 (single-shot per model × DP) |
| response_format | JSON object where supported; graceful fallback otherwise |
| parse retries | 1 retry on parse failure; parser takes the **last** balanced JSON object |
| invalid handling | recorded as a column, never excluded from the call count |
| spend_cap_usd | 20.00 (hard abort on projected breach) |
| caching | each (model, DP, repeat) disk-cached by content hash; reruns are free |

Default mode is mock; paid calls require `OPENROUTER_API_KEY` **and** `ALLOW_SPEND=1`.

**Consistency probe (sole source of the flip rate), `config/run.yaml`:** after the main
pass, the **20** decision points with the highest cross-model action disagreement are
selected (ties broken by more voters, then `dp_id`; selection logged to
`outputs/probe_selection.json`) and rerun for **all six models × 5 samples at
temperature 1.0**. A decision point "flips" for a model if its samples yield more than
one distinct action; `flip_rate_pct` is the share of flipped DPs among those with ≥2
samples. The single-shot main pass never contributes to the flip rate.

## 8. Contamination analysis (pre-registered)

The identical pipeline runs on the four 2024–25 races. Every decision point is
season-tagged. H3 is tested per model as specified in §2. We additionally report each
model's full per-season and per-race mean `delta_exante` (already emitted by the
leaderboard) for transparency.

## 9. What is committed vs. what is pending

- **Committed now (frozen):** hypotheses, metrics with `delta_exante` primary, the
  six-model roster and resolved IDs, the 178-DP dataset and its extraction rules, the
  simulator/oracle and its calibration, the prompt (`v1`), and the run/probe
  configuration.
- **Pending (not yet executed):** the paid main pass (6 models × 178 DPs × 1),
  the consistency probe (20 DPs × 6 models × 5), scoring, and the leaderboard. No real
  results inform this document.

## 10. Reproducibility

Every reported number is regenerable from `scripts/` entry points against the
configuration at tag `prereg-v1`. Public timing feeds only; no proprietary data; no
betting use intended. Secrets live solely in `.env` (gitignored); `.env.example`
carries non-secret placeholders.
