# BOXBOX — Paper Data Reference

Read-only data dump for writing the BOXBOX research paper. Every number is pulled from a
committed artifact or computed read-only from `outputs/scores.jsonl` /
`data/decision_points/manifest.json`. **No spend, no model calls, no pipeline changes.**

Sources of truth: `outputs/leaderboard.{json,md}`, `outputs/contamination.md`,
`data/decision_points/manifest.json`, `docs/PREREGISTRATION.md`, `docs/LIMITATIONS.md`,
`docs/DECISIONS.md`, `config/*.yaml`, and the `src/boxbox/` modules cited per section.

> **⚠️ Read these caveats first**
> - **The benchmark is 10 races. Barcelona / 2026 Spanish GP is NOT in it** — its
>   retrospective is blocked on incomplete tyre-compound data (FastF1 still has no 2026
>   Spain session; OpenF1 stints frozen at 27 rows → 58% UNKNOWN compounds). Do not cite a
>   Barcelona benchmark row; it does not exist.
> - **`docs/LIMITATIONS.md` items #10 and #11 were corrected** (commit after this doc): #10
>   now reflects the real paid run (not "mock"); #11 now reads **19 excluded / 159 dry**
>   (Silverstone 18, Canada 1) with the prereg-v4 `wet_running_near` criterion. Use the v4
>   numbers throughout (see §1, §10).
> - **H1 (bootstrap CIs), H2 (beat-team binomial), and H3 (contamination) are all now
>   computed.** H1/H2 → `outputs/hypothesis_tests.md` (both the 2026-only-107 and
>   all-seasons-159 dry sets; all H1 CIs exclude 0, all H2 tests significant & below 50%);
>   H3 → `outputs/contamination.md`. See §8e.
> - Two distinct "headline" definitions exist — the leaderboard's all-seasons dry mean vs
>   the prereg's 2026-only primary mean. They rank differently in the middle. See §8.

Generated from the run dated **2026-06-13T22:00:36Z** (mode: real), prereg-v4.

---

## 1. DATASET

**Totals:** 10 races, **178 decision points** (full set). By type: **A = 65, B = 42, C =
71**. Headline **dry subset = 159 DPs**; **19 excluded** as changeable-condition
(2025-Silverstone 18 + 2026-Canada 1). Source: `manifest.json`, `leaderboard.json`.

### Per-race table

| race_id | Season | Circuit | Total laps | DPs | A | B | C | Excluded (changeable) | Era |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| 2026-australia | 2026 | Melbourne | 58 | 18 | 6 | 6 | 6 | 0 | post-cutoff |
| 2026-china | 2026 | Shanghai | 56 | 18 | 6 | 6 | 6 | 0 | post-cutoff |
| 2026-japan | 2026 | Suzuka | 53 | 18 | 6 | 6 | 6 | 0 | post-cutoff |
| 2026-miami | 2026 | Miami Gardens | 57 | 18 | 6 | 6 | 6 | 0 | post-cutoff |
| 2026-canada | 2026 | Montréal | 68 | 18 | 6 | 6 | 6 | **1** | post-cutoff |
| 2026-monaco | 2026 | Monte Carlo | 78 | 18 | 6 | 6 | 6 | 0 | post-cutoff |
| 2024-bahrain | 2024 | Sakhir | 57 | 18 | 6 | 0 | 12 | 0 | pre-cutoff (contam) |
| 2024-monaco | 2024 | Monaco | 78 | 16 | 11 | 0 | 5 | 0 | pre-cutoff (contam) |
| 2025-monaco | 2025 | Monaco | 78 | 18 | 6 | 0 | 12 | 0 | pre-cutoff (contam) |
| 2025-silverstone | 2025 | Silverstone | 52 | 18 | 6 | 6 | 6 | **18** (all) | pre-cutoff (contam) |

Notes:
- **B = 0 for all three Monaco races and 2024-Bahrain** (no SC/VSC period was detected in
  those races, OR none with a top-10 car at deployment); the per-type quota donated B's 6
  slots to C then A, so those races skew to C/A. 2024-Monaco yields only 16 DPs (not 18) —
  the candidate pool after excludes was short of the cap.
- **Excluded-by-race** (changeable-condition, from `is_changeable`): only 2025-Silverstone
  (18/18, genuinely wet, inters laps 1–44) and 2026-Canada (1/18, lap L004 right after a
  damp start). Every other race contributes 0 exclusions. Source: `leaderboard.json
  → excluded_by_race`.

### Dry-headline n vs full n

- **Full set:** 178 DPs.
- **Dry headline:** **159 DPs** (`n_decision_points`). **Excluded: 19** (`n_excluded_changeable_dps`).
- Headline dry races list = **9 races** (Silverstone drops out entirely):
  2024-bahrain, 2024-monaco, 2025-monaco, 2026-australia, 2026-canada, 2026-china,
  2026-japan, 2026-miami, 2026-monaco.

### Contamination-set membership (era split)

- **Post-cutoff (2026, primary eval set):** Australia, China, Japan, Miami, Canada, Monaco.
  **108 full DPs (6 × 18); 107 dry** (Canada −1). All post-date every model's training cutoff.
- **Pre-cutoff (contamination control):** 2024 → Bahrain, Monaco; 2025 → Monaco, Silverstone.
  **70 full DPs; 52 dry** (Silverstone's 18 excluded). Plausibly documented in training data.
- Bahrain 2026 and Saudi Arabia 2026 were cancelled — never queried.

---

## 2. EXTRACTION METHOD

Source: `src/boxbox/extract/decision_points.py`, `config/extraction.yaml`. A DecisionPoint
at lap *t* asks: **"pit at the end of lap t, or stay out; if pitting, which compound?"**

### Type A/B/C trigger rules (exact)

- **Type A (pit-window):** for every real pit stop on lap *s* by a **classified** car, emit
  candidates at laps **{s−2, s−1, s}** (`type_a.offsets: [2, 1, 0]`).
- **Type B (safety-car):** at the **first lap of each SC or VSC period**, emit for every car
  running in the **top `top_n_positions = 10`** (ordered at end of lap *t−1*). A period
  "starts" when `field_status(t) ∈ {SC,VSC}` and the previous lap's status differed.
- **Type C (undercut-threat):** when a **directly adjacent rival** pits on lap *s*, emit for
  the threatened car at lap **s+1**. "Direct" = within **±1 race position** AND within
  **`rival_gap_s = 3.5` s**, both measured at the end of lap *s−1*.

### Dedupe, quota, redistribution (`apply_type_quota`)

- Overlaps for the same **(car, lap)** are deduplicated with priority **B > C > A**
  (`_TYPE_PRIORITY = {B:0, C:1, A:2}`, lower kept).
- Per race: cap **`max_dp_per_race = 18`**, target **`quota_per_type = 6`** per type.
- **Redistribution:** a type with fewer than 6 available **donates its unused slots to the
  others in order B → C → A**. (Shedding order when over cap is A, C, B — only reachable if
  cap < 3×target.)
- **Within a type, closest battles are kept first:** sort key `(relevant_gap_s, lap, driver)`.
  For Type C, `relevant_gap_s` = the rival gap; otherwise = min(car-ahead, car-behind gap).

### Exclusion rules (`config/extraction.yaml → exclude`)

- `first_laps: 3` — drop any DP at lap *t* ≤ 3.
- `last_laps: 2` — drop any DP at lap *t* > total_laps − 2.
- `lapped_cars: true` — drop lapped cars (leak-free test: gap to leader at end of *t−1*
  exceeds the leader's lap time, `_is_lapped`).
- `retirement_window_laps: 3` — for an **unclassified** (retiring) car, drop any DP within 3
  laps of its last completed lap (no leakage of an upcoming retirement).
- A DP is also dropped if `build_state` returns None (focal has no lap *t−1* record, no
  position, or UNKNOWN compound).

### Leakage-prevention guarantee + the test that proves it

- **Guarantee (structural):** `build_state(race, driver, t, …)` first truncates the race to
  laps ≤ *t* (`visible = [r for r in race.laps if r.lap_number <= t]`) and then reads only
  fields from completed laps ≤ *t−1*, **plus exactly one lap-*t* field: `track_status`**
  (real-time pit-wall knowledge the models legitimately have).
- **Proof:** deleting all laps > *t* from the input cannot change any emitted state field.
  Helper `truncate_race(race, t)`. **The asserting test exists and is named**
  `tests/test_extraction.py::test_leakage_states_identical_without_future_laps` (line 33);
  a companion `test_leakage_no_future_lap_times_in_state` (line 46) asserts no future lap
  times leak into the state. Both pass.
- **Hindsight fields never reach the model:** `team_action` / `team_compound` are stored on
  the DecisionPoint for scoring but `build_messages` serializes only `dp.state` + `dp.question`
  (confirmed in `prompts.py`).

### Exact fields in a decision-point state (`RaceState`, from `build_state`)

Top level: `race_id, track, total_laps, current_lap (= t), weather, track_status (lap-t),
pit_loss_s`.
`focal` (FocalCar): `driver, position (end of t−1), compound, tyre_age (completed laps on set),
compounds_used, compounds_available, last_lap_times_s (last 3), car_ahead, car_behind`.
Each rival (`car_ahead`/`car_behind`, RivalInfo): `driver, gap_s (|end-time delta| at t−1),
compound, tyre_age`.
`top10`: list of TopNRow `{position, driver, compound, tyre_age, gap_to_leader_s}` (top 10
at end of t−1).
- **`compounds_available`** = all dry compounds, **plus** INTER/WET **only if** the field
  actually ran wet tyres / had rain-affected laps within `wet.window_laps = 5` of *t*
  (range `[t−5, t]`, ≤ t so leakage-safe). This is `wet_running_near()`, replacing the v1
  race-level rain flag + latch (prereg-v4).

---

## 3. SIMULATOR

Source: `src/boxbox/sim/degradation.py`, `race_sim.py`, `optimal.py`.

### Lap-time model

**`lap_time = a + b·tyre_age + c·lap_number`** (`LapTimeFit.predict`), fit by least squares
on **clean laps** = timed, **GREEN** flag, **dry**, not an in/out lap, known compound, known
tyre age. (`IsAccurate` is deliberately NOT required — several 2026 sessions flag whole
drivers inaccurate; MAD filtering covers it.)
- **a** = base pace (s); **b** = degradation (s per lap of tyre age); **c** = fuel/track
  evolution (s per race lap).
- **Degradation vs fuel separation:** `b` carries tyre-age effect, `c` carries race-lap
  (fuel-burn + track-evolution) effect. **Collinearity guard:** if all clean laps come from
  one stint, age and lap_number are near-collinear and the 3-param fit explodes, so **`c` is
  dropped (=0)** when `|corr(age, lap)| ≥ 0.95` or lap_number has no variance; if tyre age
  itself has no variance, only `a` is fit.
- **Outliers:** one round of **>3·MAD** residual removal (refit on survivors if ≥4 remain).
- **Clamps (physical bounds):** tyre age capped at the **max age observed on that compound**
  in clean running; predicted lap can never be faster than the race's **fastest clean lap**.

**Fallback chain** (`fit_for`): **driver fit → team-mate fit → field (pooled) fit →
unseen-compound** (slowest field fit `a` + **1.0 s/lap** penalty). Requires ≥ `min_clean_laps
= 4` for a driver fit. Per-race lookup counts are in `manifest.json → fit_report`
(overwhelmingly `driver`; a little `teammate`; `field`/`unseen-compound` ≈ 0 across the set).

### Pit-loss estimation (`estimate_pit_loss`)

- Per real stop: **loss = in_lap + out_lap − 2 × (driver's clean-lap median)**; valid only if
  5 ≤ loss ≤ 120 s (rejects red-flag stops / glitches).
- **Green pit loss** = median over green-flag stops (fallback: back-compute from SC stops /
  0.55; final fallback 22.0 s).
- **SC pit-loss factor** = `median(SC stops) / green` if ≥ 2 SC-era stops, clamped to
  [0.2, 1.0]; else **default 0.55**.
- Per-race values (`manifest.json`): pit_loss_s ranges 17.89 (2024-Monaco) – 33.23
  (2026-China); SC factor measured (1.0) for the 2026 races + 2025-Monaco/Silverstone,
  default 0.55 for 2024-Bahrain and 2024-Monaco.

| race | pit_loss_s | SC factor | note |
|---|---:|---:|---|
| 2026-australia | 23.28 | 1.0 | 9 green / 20 SC stops |
| 2026-china | 33.23 | 1.0 | 7 green / 4 SC |
| 2026-japan | 25.42 | 1.0 | 14 green / 13 SC |
| 2026-miami | 19.42 | 1.0 | 19 green / 2 SC |
| 2026-canada | 28.71 | 1.0 | 17 green / 17 SC |
| 2026-monaco | 22.98 | 1.0 | 22 green / 46 SC |
| 2024-bahrain | 24.97 | 0.55 (default) | 41 green / 0 SC |
| 2024-monaco | 17.89 | 0.55 (default) | 7 green / 0 SC |
| 2025-monaco | 19.08 | 1.0 | 36 green / 3 SC |
| 2025-silverstone | 24.38 | 1.0 | 28 green / 2 SC |

### Counterfactual rollout (`RaceSimulator.rollout`)

- **Only the focal car is simulated**; all other cars and the **SC/VSC timeline are held
  fixed** at what actually happened. No traffic interaction (headline limitation).
- For laps `from_lap..total_laps`: tyre age += 1 each lap; a stop `(n, compound)` adds
  `pit_loss_s × factor + rejoin_penalty_s` on lap *n* (factor = SC factor if lap *n* is
  SC/VSC, else 1.0), resets compound + age=0.
- **Neutralized laps** (SC/VSC/RED, or >30% rain-affected cars) are charged the **lap's
  field-median actual time**, not the degradation model. `rejoin_penalty_s` default **0.0**.

### Ex-ante vs hindsight oracles (`optimal.py`) — exact definitions

Candidate space (both oracles, identical): **pit at the end of any lap from *t* to
total_laps−1 onto any available compound, or no further stop**, subject to the **two-compound
rule in dry races** (waived once wet tyres are in play).

- **Hindsight oracle (`sim_optimal_s`):** picks the plan **minimizing realized time** (full
  knowledge of the future SC/VSC timeline). Secondary metric.
- **Ex-ante oracle (`sim_exante_optimal_s`):** picks the plan minimizing time under a
  **green-flag assumption for every lap after *t*** (the current lap's known status is kept —
  it's real-time knowledge the models also receive). **The chosen plan is then valued in the
  realized race**, so both deltas share one currency. **By construction
  `sim_exante_optimal ≥ sim_optimal`**, hence `delta_exante ≤ delta_hindsight` per call.
- **Q-value framing:** each immediate action (STAY / PIT-onto-X at lap *t*) is valued as the
  best realized time achievable conditional on that action, minimized over continuations.
  `sim_stay` = best legal plan **not** stopping at *t*; `sim_pit[comp]` = best plan stopping
  at *t* onto `comp`. The team's real call is valued the **same** way, so agreement with the
  team at the decision instant scores as a tie.

### Documented assumptions & limitations (`docs/LIMITATIONS.md`, authoritative)

1. **No traffic interaction** in rollouts (headline limitation) — counterfactual pits scored
   as if track is clear (flat optional rejoin penalty, default 0).
2. **Single-further-stop** candidate space (≤ 1 more stop from *t*).
3. **Linear degradation** — ignores cliff, warm-up, nonlinear track evolution.
4. **Compound availability assumed** (all dry compounds available to everyone; remaining
   sets not in public data).
5. **SC/VSC laps = field-median time** — ignores concertina / track-position value.
6. **Oracle information sets** — ex-ante uses models' info set; **residual hindsight**: the
   realized valuation still uses the actual SC timeline + field-median paces, and the ex-ante
   oracle carries **no probabilistic SC model** (assumes zero SC likelihood; a real
   strategist hedges).
7. Gap figures are end-of-lap interval approximations, not live GPS.
8. Pit loss is a per-race scalar.
9. Tyre age for used sets may carry hidden pre-race usage in 2026 data.
10. **Corrected** — now reflects the real paid run (mock mode is plumbing-only).
11. **Corrected** — now reads **19 excluded / 159 dry (Silverstone 18, Canada 1)** with the
    prereg-v4 `wet_running_near` criterion; the wet→dry crossover mechanism is retained.

---

## 4. CALIBRATION

Per-race MAE (`manifest.json → calibration_mae_per_lap_s`), one stint-time MAE/lap value.

| race | MAE (s/lap) | stints |
|---|---:|---:|
| 2024-bahrain | **0.045** (best) | 62 |
| 2026-china | 0.083 | 35 |
| 2026-monaco | 0.100 | 51 |
| 2024-monaco | 0.144 | 23 |
| 2025-silverstone | 0.177 | 40 |
| 2025-monaco | 0.205 | 52 |
| 2026-japan | 0.208 | 43 |
| 2026-canada | 0.302 | 47 |
| 2026-miami | 0.475 | 42 |
| 2026-australia | **0.480** (worst) | 50 |

- **Per-race aggregation:** mean **0.222**, median **0.191**, min 0.045, max 0.480.
- **Per-stint aggregation (445 stint records, computed read-only via `calibration_records`):**
  mean **0.2224**, median **0.0900**. ⚠️ The prereg/leaderboard cite **"mean ≈ 0.22 s/lap
  (median 0.09)"** — that median is the **per-stint** median (0.090), NOT the per-race median
  (0.191). Use whichever aggregation you describe; don't mix them.

### Worst stints (per-stint, for the limitations section)

| race | driver | stint | compound | n_laps | MAE/lap | fit source |
|---|---|---:|---|---:|---:|---|
| 2026-miami | BOT | 1 | MEDIUM | 4 | **8.257** | driver |
| 2026-australia | COL | 1 | HARD | 8 | 2.258 | driver |
| 2025-monaco | HUL | 1 | MEDIUM | 3 | 2.241 | teammate |
| 2026-miami | HAD | 1 | HARD | 3 | 1.925 | teammate |
| 2026-australia | STR | 1 | MEDIUM | 10 | 1.464 | driver |
| 2026-australia | LAW | 1 | MEDIUM | 10 | 1.405 | driver |
| 2026-canada | ALB | 1 | SOFT | 11 | 1.384 | driver |
| 2025-monaco | HAM | 1 | HARD | 9 | 1.272 | driver |

**Why worst:** dominated by **thin first stints** (n = 3–4) where a linear fit overshoots —
the Miami BOT MEDIUM n=4 fit (MAE 8.26) is the degenerate case flagged in DECISIONS #45.
Australia (worst race, 0.48) is full of high-MAE early MEDIUM stints; Miami (0.475) carries
the BOT outlier. ⚠️ Note: fit-hardening (rejecting thin fits → teammate/field fallback) was
tested and **rejected** — it regressed in-sample MAE 0.222 → 0.239 (DECISIONS #45 /
prereg-v3), because a driver's own clamped fit beats any pooled fallback on their own laps.

### Calibration figure paths
`outputs/calibration/{2024-bahrain, 2024-monaco, 2025-monaco, 2025-silverstone,
2026-australia, 2026-canada, 2026-china, 2026-japan, 2026-miami, 2026-monaco}.png` — one
per race; each plots predicted vs actual stint time (title "<race>: stint calibration").
(`manifest.json` lists `calibration_figure: null` because the build wrote them to a fixed
path rather than recording it — the PNGs exist on disk.)

---

## 5. MODELS

Source: `config/models.yaml`, `config/run.yaml`. **5 models in the benchmark**
(Claude Fable 5 removed, prereg-v2). Pricing = $/M tokens (in/out), for the cost ledger only,
not scoring.

| Model (config) | OpenRouter ID | In $/MTok | Out $/MTok | In benchmark? |
|---|---|---:|---:|---|
| claude-opus-4.8 | `anthropic/claude-opus-4.8` | 5.0 | 25.0 | ✅ |
| gpt-5.5 | `openai/gpt-5.5` | 5.0 | 30.0 | ✅ |
| gemini-3.1-pro | `google/gemini-3.1-pro-preview` | 2.0 | 12.0 | ✅ |
| deepseek-v3.2 | `deepseek/deepseek-v3.2` | 0.2288 | 0.3432 | ✅ |
| claude-haiku-4.5 | `anthropic/claude-haiku-4.5` | 1.0 | 5.0 | ✅ |
| claude-fable-5 | `anthropic/claude-fable-5` | 10.0 | 50.0 | ❌ removed (export-control, see §10) |

### Run config (`config/run.yaml`)

- **Main pass:** temperature **0.0**, **max_tokens 1200**, **repeats 1** (single-shot per
  model × DP), `response_format` = JSON where supported, **1 parse retry** (parser takes the
  **last balanced JSON object**), invalid recorded as a column (not dropped from call count),
  **spend_cap_usd 20.00** (hard abort on projected breach), each (model, DP, repeat) disk-cached
  by content hash.
- **Consistency probe (`consistency_probe`):** the **20** highest cross-model action-
  disagreement DPs (selection logged to `probe_selection.json`), **5 samples** each,
  **temperature 1.0** (provider-default sampling). Sole source of the flip rate.
- Mock mode is default; paid calls require `OPENROUTER_API_KEY` **and** `ALLOW_SPEND=1`.
- Live-demo subset (`live_models`, separate from the benchmark): claude-opus-4.8, gpt-5.5,
  deepseek-v3.2 (current value; was claude-fable-5/gpt-5.5 in prereg-v1).

---

## 6. PROMPT (`PROMPT_VERSION = "v1"`, `src/boxbox/harness/prompts.py`)

**System prompt (verbatim):**
> You are the chief race strategist for the focal car's team. Decide using only the provided
> state. Output strict JSON, nothing else.

**User prompt (template):**
```
RACE STATE:
<json.dumps(dp.state.model_dump(), indent=1)>

QUESTION: <dp.question>

Answer with strict JSON only, exactly this schema:
{"action": "PIT" | "STAY", "compound": "<one of compounds_available or null>", "confidence": 0.0-1.0, "rationale": "<max 50 words>"}
```
`dp.question` = "It is lap {t} of {total_laps}. Decide for {driver}: pit at the end of this
lap, or stay out? If pitting, choose the new compound."

**Output JSON schema (`OUTPUT_SCHEMA`):**
```json
{"action": "PIT" | "STAY", "compound": "<one of compounds_available or null>", "confidence": 0.0-1.0, "rationale": "<max 50 words>"}
```
Only `dp.state` and `dp.question` are serialized — hindsight fields never reach the model.

---

## 7. SCORING (`src/boxbox/score/scoring.py`, `leaderboard.py`)

Let `sim_model` = Q-value of the model's answer, `sim_exante_optimal` / `sim_optimal` =
realized time of the ex-ante / hindsight oracle plan, `sim_team` = Q-value of the team's call.

- **`delta_exante = sim_model − sim_exante_optimal` — PRIMARY.** Distance from the optimum
  under the models' own info set (green after *t*). Lower = better; basis of ranking, H1, H3.
- **`delta_hindsight = sim_model − sim_optimal`** — secondary (optimum knowing future SC/VSC).
  Always ≥ delta_exante per call.
- **`delta_vs_team = sim_model − sim_team`**; **`beat_team = sim_model < sim_team − 1e-9`**
  (strict). **`beat_team_pct`** = share of valid calls beating the team.
- **`agree_team_action`** = same PIT/STAY as team; **`agree_team_exact`** = also same compound
  when pitting. **`agree_team_pct`** = share agreeing on action.
- **`invalid`** = answer couldn't be parsed into the schema OR couldn't be valued
  (`value_of` returns None — e.g. PIT onto a compound with no scorable plan). A PIT with no/
  unknown compound is charitably valued at the cheapest PIT (`min(sim_pit.values())`).
- **Invalid handling:** invalids are **excluded from delta means** (and beat/agree %, which
  are over valid calls) but **counted in the denominator of `invalid_pct`** (over ALL calls)
  and never drop a model. (`_model_rows`: `valid = not invalid and delta_exante is not None`.)
- **Flip rate (`flip_rate_pct`), probe only:** for each model, over probe DPs sampled ≥ 2
  times, a DP "flips" if its samples yield **> 1 distinct action**. `flip_rate_pct = flipped /
  (DPs with ≥2 samples)`. Single-shot main pass never contributes. Computed on the **dry**
  probe subset (**18** dry probe DPs of the 20 selected).

---

## 8. RESULTS

### 8a. Headline leaderboard — DRY subset (159 DPs, all 9 dry races, all seasons)

`leaderboard.json → models`. Ranked by mean `delta_exante` ascending.

| # | Model | Mean Δexante (s) | Median | Mean Δhindsight (s) | Median | Beat team % | Agree team % | Invalid % | Flip % | Calls | Valid |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | deepseek-v3.2 | **5.303** | 0.0 | 5.676 | 0.0 | 18.2 | 73.0 | 0.0 | 38.9 | 159 | 159 |
| 2 | claude-opus-4.8 | 7.126 | 0.0 | 7.502 | 0.773 | 22.2 | 58.9 | 0.6 | 5.6 | 159 | 158 |
| 3 | gemini-3.1-pro | 7.375 | 0.171 | 7.751 | 0.522 | 19.6 | 60.1 | 0.6 | 22.2 | 159 | 158 |
| 4 | gpt-5.5 | 9.203 | 1.021 | 9.577 | 1.564 | 18.2 | 59.1 | 0.0 | 55.6 | 159 | 159 |
| 5 | claude-haiku-4.5 | 12.764 | 0.312 | 13.137 | 0.438 | 17.0 | 64.2 | 0.0 | 0.0 | 159 | 159 |

Aggregate: **793 valid scored calls** (159 × 5 − 2 invalids: opus 1, gemini 1).

### 8b. Appendix — FULL set (178 DPs, includes wet artifacts; NOT the headline)

`leaderboard.json → appendix_full_set`. Means inflated by the wet 2025-Silverstone calls.

| # | Model | Mean Δexante (s) | Median | Beat team % | Agree % | Invalid % | Flip % | Calls |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | gpt-5.5 | 19.769 | 1.829 | 16.9 | 59.6 | 0.0 | 55.0 | 178 |
| 2 | claude-opus-4.8 | 20.832 | 0.721 | 20.3 | 58.8 | 0.6 | 5.0 | 178 |
| 3 | gemini-3.1-pro | 20.928 | 1.603 | 18.1 | 59.9 | 0.6 | 25.0 | 178 |
| 4 | deepseek-v3.2 | 24.058 | 0.339 | 16.9 | 70.2 | 0.0 | 40.0 | 178 |
| 5 | claude-haiku-4.5 | 30.948 | 0.934 | 15.7 | 62.4 | 0.0 | 0.0 | 178 |

### 8c. ⚠️ Two "headline" definitions — they rank differently

- **Leaderboard headline (above):** mean over **all 159 dry DPs (all seasons)**.
- **Prereg §3 PRIMARY:** "mean `delta_exante` over the **108 2026 DPs**" (here 107 dry). The
  2026-only means (computed read-only from `scores.jsonl`):

  | Model | 2026-only mean Δexante (s) | n |
  |---|---:|---:|
  | deepseek-v3.2 | **5.809** | 107 |
  | claude-haiku-4.5 | 8.321 | 107 |
  | gemini-3.1-pro | 8.635 | 107 |
  | gpt-5.5 | 8.996 | 107 |
  | claude-opus-4.8 | 9.232 | 106 |

  **deepseek is #1 under both**, but **opus moves #2 (all-dry) → #5 (2026-only)** because it
  is unusually strong on pre-2026 (2024 mean 2.661) and weaker on 2026. Decide which
  definition the paper's headline uses and be consistent.

### 8d. Per-decision-type performance (dry subset, computed from `scores.jsonl`)

Mean `delta_exante` (s):

| Model | A (pit-window) | B (safety-car) | C (undercut) |
|---|---:|---:|---:|
| claude-haiku-4.5 | 19.785 | 2.467 | 12.083 |
| claude-opus-4.8 | 8.266 | 7.655 | 5.755 |
| deepseek-v3.2 | 3.613 | 5.013 | 7.023 |
| gemini-3.1-pro | 9.775 | 6.858 | 5.422 |
| gpt-5.5 | 14.278 | 10.002 | 4.076 |

Per-type overall (all models pooled, dry): **A:** mean 11.143 / median 1.598 (n=295);
**B:** mean 6.399 / median 0.000 (n=180); **C:** mean 6.880 / median 0.000 (n=318). Type A
(pit-window timing) is the hardest type on average. (H6, exploratory.)

### 8e. Contamination (H3) — `outputs/contamination.md`

Per-season mean / median `delta_exante` (n), and the **H3 test: two-sided Mann–Whitney U on
per-DP `delta_exante`, pre-2026 vs 2026, Holm-corrected across the 5 models.** Negative gap =
better (lower) on pre-2026 = possible recall.

| Model | 2024 | 2025 | 2026 | pre-2026 (24–25) | gap (pre−2026) | raw p | Holm p | verdict @0.05 |
|---|---|---|---|---|---:|---:|---:|---|
| claude-haiku-4.5 | 28.336 / 4.176 (n=34) | 9.756 / 3.691 (n=18) | 8.321 / 0.0 (n=107) | 21.905 / 3.691 (n=52) | **+13.584** | 0.0002 | **0.0008** | **worse on pre-2026** |
| deepseek-v3.2 | 1.35 / 0.0 (n=34) | 9.756 / 3.691 (n=18) | 5.809 / 0.0 (n=107) | 4.26 / 0.824 (n=52) | −1.549 | 0.0167 | 0.0669 | no significant gap |
| gpt-5.5 | 12.964 / 3.612 (n=34) | 3.331 / 3.104 (n=18) | 8.996 / 0.0 (n=107) | 9.629 / 3.104 (n=52) | +0.633 | 0.0203 | 0.0669 | no significant gap |
| gemini-3.1-pro | 5.332 / 1.901 (n=34) | 3.527 / 3.146 (n=17) | 8.635 / 0.0 (n=107) | 4.73 / 2.987 (n=51) | −3.905 | 0.0593 | 0.1185 | no significant gap |
| claude-opus-4.8 | 2.661 / 0.0 (n=34) | 3.156 / 3.024 (n=18) | 9.232 / 0.0 (n=106) | 2.832 / 0.961 (n=52) | −6.4 | 0.613 | 0.613 | no significant gap |

**Key result:** **No model is significantly BETTER on pre-2026** (the contamination-proof
framing holds). The only significant effect is haiku being *worse* on pre-2026. The earlier
apparent "worse on pre-2026" signal was an artifact of the wet 2025-Silverstone calls (now
excluded). Pooled: **793 valid scored calls**, **95 changeable-condition calls excluded**
(= 19 DPs × 5 models).

### 8f. Monaco same-track (2024 / 2025 / 2026, constant circuit) — mean `delta_exante`

| Model | 2024-monaco (n=16) | 2025-monaco (n=18) | 2026-monaco (n=18) |
|---|---:|---:|---:|
| claude-haiku-4.5 | 49.154 | 9.756 | 3.788 |
| claude-opus-4.8 | 2.766 | 3.156 | 2.8 |
| deepseek-v3.2 | 2.766 | 9.756 | 4.169 |
| gemini-3.1-pro | 5.528 | 3.527 | 4.867 |
| gpt-5.5 | 14.006 | 3.331 | 0.716 |

No clean monotone pre-2026 advantage; if anything most models are **best on 2026-Monaco**
(opposite of a recall signal).

### 8g. Claude Fable 5 head-to-head (exploratory, n = 3) — `outputs/fable_comparison.md`

Cached pre-suspension smoke-v2 calls (temp 0, single-shot), scored with the same oracle.
**Not in the leaderboard.** 3 DPs, not balanced across types/races — anecdote only.

| DP | Type · race · lap | Team | Ex-ante optimal | Fable call | Fable Δexante (s) |
|---|---|---|---|---|---:|
| 2026-australia-L007-COL-A | A · AUS · L7 | STAY | PIT MEDIUM | STAY | 1.60 (= all 5 models) |
| 2026-china-L010-ANT-B | B · CHN · L10 | PIT HARD | STAY | PIT HARD | 23.34 (= opus, gpt-5.5; gemini/deepseek/haiku STAY = 0.00) |
| 2026-japan-L018-ANT-C | C · JPN · L18 | STAY | PIT HARD | PIT HARD | 0.00 (= gemini; the 4 others STAY = 1.56) |

Read: Fable matched the cluster on DP1, sided with opus/gpt-5.5 (and lost 23.34 s) on DP2,
and was one of two to hit the ex-ante optimum on DP3.

---

## 9. FIGURES

### Already generated — `outputs/figures/`

| File | Title (from `analysis/figures.py`) | Shows |
|---|---|---|
| `leaderboard_bar.png` | "BOXBOX leaderboard (real data)" | bar of mean Δexante per model |
| `delta_distribution.png` | "score-delta distribution per model" | per-model Δ distribution |
| `race_heatmap.png` | "per-race performance heatmap" | model × **race** mean Δ heatmap |
| `flip_rate.png` | "consistency: how often repeated prompts flip the call" | per-model flip rate |
| `season_gap.png` | "contamination gap: old vs new races" | per-model pre-2026 vs 2026 gap |

### Already generated — `outputs/calibration/` (10 per-race)
`{2024-bahrain, 2024-monaco, 2025-monaco, 2025-silverstone, 2026-australia, 2026-canada,
2026-china, 2026-japan, 2026-miami, 2026-monaco}.png` — predicted vs actual stint time.

### Your 7 planned figures — exist vs need generating

| Planned figure | Status |
|---|---|
| 1. Leaderboard bar | ✅ EXISTS — `figures/leaderboard_bar.png` |
| 2. Accuracy-vs-consistency scatter | ❌ **MISSING** — ingredients exist (mean Δexante from leaderboard, flip rate from probe); needs a new plot |
| 3. Per-type / heatmap | ⚠️ PARTIAL — `race_heatmap.png` is per-**race**, not per-**type**. Per-type numbers in §8d, but **no per-type figure exists** → needs generating |
| 4. Per-season contamination | ✅ EXISTS — `figures/season_gap.png` |
| 5. Calibration scatter | ✅ EXISTS — `calibration/*.png` (per race) |
| 6. Decision-point schematic | ❌ **MISSING** — conceptual diagram, never auto-generated |
| 7. (7th unspecified in your list) | `delta_distribution.png` and `flip_rate.png` exist as extras; clarify which is the intended 7th |

**Net: 2 clearly missing (accuracy-vs-consistency scatter, decision-point schematic), plus a
per-type figure if you want type broken out beyond the per-race heatmap.**

---

## 10. PREREGISTRATION TRAIL (v1 → v4)

Source: `docs/PREREGISTRATION.md` (amendments), `docs/DECISIONS.md`.

- **prereg-v1** (2026-06-13, tag `prereg-v1`): original **six-model** design, methodology
  frozen before any full results. Froze hypotheses (H1–H6), the 178-DP dataset + extraction
  rules, simulator/oracle, prompt v1, run/probe config. Committed before the paid run.
- **prereg-v2** (2026-06-13) — **Claude Fable 5 removed** (six → five models). **Verified
  reason:** on 2026-06-12 the US government issued an export-control directive suspending all
  access to Fable 5 / Mythos 5 (national-security; triggered by a demonstrated jailbreak).
  Empirically confirmed: a real `Runner` call on 2026-06-13T10:42:20Z returned **HTTP 404**
  from every provider ("Claude Fable 5 is not available. Please use Opus 4.8"), 0 tokens / $0
  (`outputs/fable_unavailable_check.md`). The ledger shows Fable was reachable on the morning
  of 2026-06-12 (6 smoke calls) → access ceased after the directive. Only the roster changed.
- **prereg-v3** (2026-06-13) — **headline metric on the DRY subset** (wet exclusion).
  **Verified reason:** the v1 single-stint simulator cannot model a wet→dry crossover, so a
  model that pits onto INTER/WET is run to the flag at wet pace — an **artifact** (~235 s
  mean "loss" on wet-tyre calls vs ~8.5 s otherwise), not a strategy error. At this commit
  excluded 36/178 (Miami 18, Silverstone 18) → dry = 142. (Also: fit-hardening attempted and
  **rejected** for regressing calibration MAE 0.222 → 0.239.)
- **prereg-v4** (2026-06-13) — **wet detection corrected at the source.** **Verified reason:**
  a conditions audit found v3's race-level `weather.rain` flag + "any wet lap seen" latch
  over-offered INTER in two dry cases: **Miami** (`rain=True` from 3 stray samples of 168 on a
  33–42 °C track, never ran an inter; 60 model picks → artifact) and **Canada** (damp laps
  1–3 latched INTER on for the whole dry race). Fix: one conditions-only test
  `wet_running_near(t, window=5)` (range `[t−5, t]`, leakage-safe) for **both** the offered
  set and `is_changeable`. **Verified outcomes:** Silverstone stays fully excluded (18/18);
  **Miami now INCLUDED** (changeable 18→0); Canada dry-phase included (only L004 stays).
  **Re-ran only the 35 affected DPs** (175 calls, projected $1.358 / actual **$1.375**;
  ledger $11.13 → $12.50). **Result: dry subset 142 → 159, exclusions 36 → 19.** Miami mean
  Δexante collapsed 92.56 → 13.65 s. (DECISIONS #46; #47 added compound-not-offered parser
  enforcement, affecting exactly 1 call: opus on miami-L033-OCO.)

---

## 11. REPRODUCIBILITY

### Commands (`CLAUDE.md`)
```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest                                   # all green
python scripts/build_dataset.py          # ingest -> extract -> data/decision_points/  (--force to re-ingest)
python scripts/run_benchmark.py          # main pass -> outputs/raw_results/results.jsonl  (needs OPENROUTER_API_KEY + ALLOW_SPEND=1)
python scripts/run_consistency_probe.py  # top-disagreement DPs x5 -> sole flip-rate source
python scripts/score_results.py          # scores -> outputs/leaderboard.{md,csv,json} + contamination.md
python analysis/figures.py               # outputs/figures/
```
The frozen procedure is the code/config at tag `prereg-v1`; amendments are prereg-v2…v4.
Public timing feeds only (FastF1, OpenF1 fallback). Secrets only in `.env` (gitignored).

### Total spend (`outputs/cost_ledger.csv`, run logs)

| Component | Calls | Spend |
|---|---:|---:|
| Main pass (178 DPs × 5 models × 1) | 890 | (part of $11.13) |
| Consistency probe (20 DPs × 5 models × 5) | 500 | (part of $11.13) |
| Main + probe (full_run_log, 2026-06-13) | 1390 | **$11.1256** |
| prereg-v4 re-run (35 DPs, 175 calls) | 175 | **$1.3746** → cumulative **$12.5002** |
| Smoke tests (v1 + v2) | ~36 | ~$0.40 (included in non-live total) |
| **Benchmark total (non-live)** | 5884 ledger rows | **$12.4986** |
| Live Barcelona demo (separate, NOT benchmark) | 555 | **$0.6936** |
| **Grand total (ledger)** | 6439 | **$13.1922** |

Quote the **benchmark** spend as **≈ $12.50** (main + probe + smoke + v4 reruns); the
**$0.69 live demo is separate** from the paper's benchmark. Spend cap was $20.00 (never hit).

### Test count
**61 tests** now (`pytest --co` → "61 tests collected"), all green. Spread across 7 test
files: test_extraction 14, test_parser 18, test_openf1_auth 9, test_sim 8, test_harness 5,
test_probe 3, test_end_to_end 1. **At the benchmark / prereg-v4 commit the count was ~52** —
the 9 `tests/test_openf1_auth.py` tests were added later for the live demo (post-benchmark).
Cite **52** for "tests at the benchmark commit", **61** for the current repo state.

---

### Open items to resolve before submission (flagged, not guessed)
1. ✅ Resolved — `docs/LIMITATIONS.md` #10 (mock→real) and #11 (→ 19/159) corrected.
2. ✅ Resolved — H1 (bootstrap CIs) and H2 (beat-team binomial) computed in
   `outputs/hypothesis_tests.md`: all H1 CIs exclude 0 (every model sub-optimal), all H2
   significant with beat rates below 50%, on both candidate headline sets.
3. **Decide the single headline definition** (all-seasons dry 159 vs 2026-only 107) and use it
   consistently — they reorder models 2–5.
4. **Generate the 2 missing figures** (accuracy-vs-consistency scatter; decision-point
   schematic) and optionally a per-type figure.
5. ✅ Resolved — leakage test confirmed:
   `tests/test_extraction.py::test_leakage_states_identical_without_future_laps` (+ companion).
6. **Barcelona is excluded** from the 10-race benchmark (compound data incomplete). If you
   want it as an 11th race, it needs FastF1 (or complete OpenF1 stints) first.
