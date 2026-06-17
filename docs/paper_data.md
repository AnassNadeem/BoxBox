# BOXBOX — Paper Data Reference

Read-only data dump for writing the BOXBOX research paper. Every number is pulled from a
committed artifact or computed read-only from `outputs/scores.jsonl` /
`data/decision_points/manifest.json`.

Sources of truth: `outputs/leaderboard.{json,md}`, `outputs/contamination.md`,
`docs/hypothesis_tests.md`, `data/decision_points/manifest.json`, `docs/PREREGISTRATION.md`,
`docs/LIMITATIONS.md`, `docs/DECISIONS.md`, `config/*.yaml`, and the `src/boxbox/` modules
cited per section.

> **⚠️ Read these caveats first**
> - **The benchmark is now 11 races.** Barcelona / **2026 Spanish GP (Round 7, raced
>   2026-06-14)** was added as race #11 on 2026-06-17 and the whole pipeline re-run. It is a
>   **post-cutoff, fully dry, 18-DP** race in the PRIMARY 2026 set (0 excluded). The earlier
>   "Barcelona is blocked on incomplete compound data" caveat is **resolved** — FastF1/OpenF1
>   now resolve the Barcelona-Catalunya race (config `event: barcelona`, race_id
>   `2026-barcelona`; bare "Spain" still points at the future Madrid round and is avoided).
> - **`docs/LIMITATIONS.md` items #10 and #11**: #10 reflects the real paid run (not "mock");
>   #11 reads **19 excluded / 177 dry** (Silverstone 18, Canada 1) with the prereg-v4
>   `wet_running_near` criterion.
> - **H1 (bootstrap CIs), H2 (beat-team binomial), and H3 (contamination) are all computed.**
>   H1/H2 → `docs/hypothesis_tests.md` (both the **2026-only 125** and **all-seasons 177** dry
>   sets; all H1 CIs exclude 0, all H2 tests significant & below 50%); H3 → `outputs/
>   contamination.md`. See §8e. **H3 shifted with Barcelona** — see the bold note in §8e.
> - Two distinct "headline" definitions exist — the leaderboard's all-seasons dry mean (177)
>   vs the prereg's 2026-only primary mean (125). They rank differently in the middle. See §8.

Generated from the real run **refreshed 2026-06-17** (Barcelona added; prereg-v4 method).

---

## 1. DATASET

**Totals:** 11 races, **196 decision points** (full set). By type: **A = 71, B = 48, C =
77**. Headline **dry subset = 177 DPs**; **19 excluded** as changeable-condition
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
| **2026-barcelona** | 2026 | Barcelona-Catalunya | 66 | 18 | 6 | 6 | 6 | 0 | **post-cutoff (new #11)** |
| 2024-bahrain | 2024 | Sakhir | 57 | 18 | 6 | 0 | 12 | 0 | pre-cutoff (contam) |
| 2024-monaco | 2024 | Monaco | 78 | 16 | 11 | 0 | 5 | 0 | pre-cutoff (contam) |
| 2025-monaco | 2025 | Monaco | 78 | 18 | 6 | 0 | 12 | 0 | pre-cutoff (contam) |
| 2025-silverstone | 2025 | Silverstone | 52 | 18 | 6 | 6 | 6 | **18** (all) | pre-cutoff (contam) |

Notes:
- **Barcelona** is a clean A/B/C 6-6-6 split, 0 exclusions, fully dry; it lands in the PRIMARY
  2026 set. dp_ids are `2026-barcelona-L###-DRV-{A,B,C}`.
- **B = 0 for all three Monaco races and 2024-Bahrain** (no SC/VSC period with a top-10 car at
  deployment); the per-type quota donated B's 6 slots to C then A. 2024-Monaco yields only 16
  DPs — the candidate pool after excludes was short of the cap.
- **Excluded-by-race** (changeable-condition): only 2025-Silverstone (18/18, genuinely wet) and
  2026-Canada (1/18, lap L004 after a damp start). Every other race contributes 0.

### Dry-headline n vs full n

- **Full set:** 196 DPs.
- **Dry headline:** **177 DPs** (`n_decision_points`). **Excluded: 19** (`n_excluded_changeable_dps`).
- Headline dry races list = **10 races** (Silverstone drops out entirely):
  2024-bahrain, 2024-monaco, 2025-monaco, 2026-australia, **2026-barcelona**, 2026-canada,
  2026-china, 2026-japan, 2026-miami, 2026-monaco.

### Contamination-set membership (era split)

- **Post-cutoff (2026, primary eval set):** Australia, China, Japan, Miami, Canada, Monaco,
  **Barcelona**. **126 full DPs (7 × 18); 125 dry** (Canada −1). All post-date every model's
  training cutoff.
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
  others in order B → C → A**. (Shedding order when over cap is A, C, B.)
- **Within a type, closest battles are kept first:** sort key `(relevant_gap_s, lap, driver)`.

### Exclusion rules (`config/extraction.yaml → exclude`)

- `first_laps: 3` — drop any DP at lap *t* ≤ 3.
- `last_laps: 2` — drop any DP at lap *t* > total_laps − 2.
- `lapped_cars: true` — drop lapped cars (leak-free: gap to leader at end of *t−1* exceeds the
  leader's lap time, `_is_lapped`).
- `retirement_window_laps: 3` — for an **unclassified** (retiring) car, drop any DP within 3
  laps of its last completed lap.
- A DP is also dropped if `build_state` returns None (focal has no lap *t−1* record, no
  position, or UNKNOWN compound).

### Leakage-prevention guarantee + the test that proves it

- **Guarantee (structural):** `build_state(race, driver, t, …)` first truncates the race to
  laps ≤ *t* and then reads only fields from completed laps ≤ *t−1*, **plus exactly one lap-*t*
  field: `track_status`** (real-time pit-wall knowledge the models legitimately have).
- **Proof:** deleting all laps > *t* from the input cannot change any emitted state field.
  Asserting test: `tests/test_extraction.py::test_leakage_states_identical_without_future_laps`
  (+ companion `test_leakage_no_future_lap_times_in_state`). Both pass.
- **Hindsight fields never reach the model:** `team_action` / `team_compound` are stored for
  scoring; `build_messages` serializes only `dp.state` + `dp.question`.

### Exact fields in a decision-point state (`RaceState`, from `build_state`)

Top level: `race_id, track, total_laps, current_lap (= t), weather, track_status (lap-t),
pit_loss_s`. `focal`: `driver, position (end of t−1), compound, tyre_age, compounds_used,
compounds_available, last_lap_times_s (last 3), car_ahead, car_behind`. Each rival: `driver,
gap_s, compound, tyre_age`. `top10`: TopNRow `{position, driver, compound, tyre_age,
gap_to_leader_s}`.
- **`compounds_available`** = all dry compounds **plus** INTER/WET **only if** the field ran
  wet tyres / had rain-affected laps within `wet.window_laps = 5` of *t* (range `[t−5, t]`,
  leakage-safe; `wet_running_near()`, prereg-v4).

---

## 3. SIMULATOR

Source: `src/boxbox/sim/degradation.py`, `race_sim.py`, `optimal.py`.

### Lap-time model

**`lap_time = a + b·tyre_age + c·lap_number`** (`LapTimeFit.predict`), fit by least squares
on **clean laps** = timed, **GREEN** flag, **dry**, not an in/out lap, known compound, known
tyre age.
- **a** = base pace; **b** = degradation (s/lap of tyre age); **c** = fuel/track evolution
  (s/race lap). **Collinearity guard:** `c` dropped (=0) when `|corr(age, lap)| ≥ 0.95`.
- **Outliers:** one round of **>3·MAD** residual removal (refit on survivors if ≥4 remain).
- **Clamps:** tyre age capped at max age observed on that compound; predicted lap never faster
  than the race's fastest clean lap.

**Fallback chain** (`fit_for`): **driver fit → team-mate fit → field (pooled) fit →
unseen-compound** (slowest field `a` + **1.0 s/lap**). Requires ≥ `min_clean_laps = 4` for a
driver fit. Per-race counts in `manifest.json → fit_report` (overwhelmingly `driver`).

### Pit-loss estimation (`estimate_pit_loss`)

- Per real stop: **loss = in_lap + out_lap − 2 × (driver's clean-lap median)**; valid only if
  5 ≤ loss ≤ 120 s.
- **Green pit loss** = median over green-flag stops (fallback: SC stops / 0.55; final 22.0 s).
- **SC pit-loss factor** = `median(SC stops) / green` if ≥ 2 SC-era stops, clamped to [0.2,1.0];
  else **default 0.55**.

| race | pit_loss_s | SC factor | note |
|---|---:|---:|---|
| 2026-australia | 23.28 | 1.0 | 9 green / 20 SC stops |
| 2026-china | 33.23 | 1.0 | 7 green / 4 SC |
| 2026-japan | 25.42 | 1.0 | 14 green / 13 SC |
| 2026-miami | 19.42 | 1.0 | 19 green / 2 SC |
| 2026-canada | 28.71 | 1.0 | 17 green / 17 SC |
| 2026-monaco | 22.98 | 1.0 | 22 green / 46 SC |
| **2026-barcelona** | **25.04** | **1.0** | new race #11 |
| 2024-bahrain | 24.97 | 0.55 (default) | 41 green / 0 SC |
| 2024-monaco | 17.89 | 0.55 (default) | 7 green / 0 SC |
| 2025-monaco | 19.08 | 1.0 | 36 green / 3 SC |
| 2025-silverstone | 24.38 | 1.0 | 28 green / 2 SC |

Range: 17.89 (2024-Monaco) – 33.23 (2026-China).

### Counterfactual rollout (`RaceSimulator.rollout`)

- **Only the focal car is simulated**; all other cars and the **SC/VSC timeline are held
  fixed** at what actually happened. No traffic interaction (headline limitation).
- For laps `from_lap..total_laps`: tyre age += 1 each lap; a stop `(n, compound)` adds
  `pit_loss_s × factor + rejoin_penalty_s` on lap *n*, resets compound + age=0.
- **Neutralized laps** (SC/VSC/RED, or >30% rain-affected cars) charged the **lap's field-median
  actual time**. `rejoin_penalty_s` default **0.0**.

### Ex-ante vs hindsight oracles (`optimal.py`) — exact definitions

Candidate space (both oracles): **pit at the end of any lap from *t* to total_laps−1 onto any
available compound, or no further stop**, subject to the **two-compound rule in dry races**.

- **Hindsight oracle (`sim_optimal_s`):** plan **minimizing realized time** (full future SC/VSC
  knowledge). Secondary metric.
- **Ex-ante oracle (`sim_exante_optimal_s`):** plan minimizing time under a **green-flag
  assumption for every lap after *t*** (current lap's known status kept), then **valued in the
  realized race**. **By construction `sim_exante_optimal ≥ sim_optimal`**, hence
  `delta_exante ≤ delta_hindsight` per call.
- **Q-value framing:** each immediate action (STAY / PIT-onto-X at lap *t*) is valued as the
  best realized time achievable conditional on that action. The team's real call is valued the
  same way.

### Documented assumptions & limitations (`docs/LIMITATIONS.md`, authoritative)

1. **No traffic interaction** in rollouts (headline limitation).
2. **Single-further-stop** candidate space (≤ 1 more stop from *t*).
3. **Linear degradation** — ignores cliff, warm-up, nonlinear track evolution.
4. **Compound availability assumed** (all dry compounds available).
5. **SC/VSC laps = field-median time** — ignores concertina / track-position value.
6. **Oracle information sets** — ex-ante uses models' info set; residual hindsight in the
   realized valuation; ex-ante oracle carries **no probabilistic SC model**.
7. Gap figures are end-of-lap interval approximations.
8. Pit loss is a per-race scalar.
9. Tyre age for used sets may carry hidden pre-race usage in 2026 data.
10. **Corrected** — reflects the real paid run (mock mode is plumbing-only).
11. **Corrected** — reads **19 excluded / 177 dry (Silverstone 18, Canada 1)** with the
    prereg-v4 `wet_running_near` criterion.

---

## 4. CALIBRATION

Per-race MAE (`manifest.json → calibration_mae_per_lap_s`).

| race | MAE (s/lap) | stints |
|---|---:|---:|
| 2024-bahrain | **0.045** (best) | 62 |
| 2026-china | 0.083 | 35 |
| 2026-monaco | 0.100 | 51 |
| 2024-monaco | 0.144 | 23 |
| 2025-silverstone | 0.177 | 40 |
| 2025-monaco | 0.205 | 52 |
| 2026-japan | 0.208 | 43 |
| **2026-barcelona** | **0.214** | 65 |
| 2026-canada | 0.302 | 47 |
| 2026-miami | 0.475 | 42 |
| 2026-australia | **0.480** (worst) | 50 |

- **Per-race aggregation (11 races):** mean **0.221**, median **0.205**, min 0.045, max 0.480.
- **Per-stint aggregation (510 stint records):** mean ≈ **0.22 s/lap**, median ≈ **0.09**.
  ⚠️ The "mean ≈ 0.22 / median 0.09" quote uses the **per-stint** median (0.09), NOT the
  per-race median (0.205). Don't mix aggregations.
- Barcelona calibrates cleanly (0.214 over 65 stints — the most stints of any race).

### Calibration figures
`outputs/calibration/{race}.png` — one per race (now incl. `2026-barcelona.png`); each plots
predicted vs actual stint time.

---

## 5. MODELS

Source: `config/models.yaml`, `config/run.yaml`. **5 models in the benchmark** (Claude Fable 5
removed, prereg-v2). Pricing = $/M tokens (in/out), for the cost ledger only.

| Model (config) | OpenRouter ID | In $/MTok | Out $/MTok | In benchmark? |
|---|---|---:|---:|---|
| claude-opus-4.8 | `anthropic/claude-opus-4.8` | 5.0 | 25.0 | ✅ |
| gpt-5.5 | `openai/gpt-5.5` | 5.0 | 30.0 | ✅ |
| gemini-3.1-pro | `google/gemini-3.1-pro-preview` | 2.0 | 12.0 | ✅ |
| deepseek-v3.2 | `deepseek/deepseek-v3.2` | 0.2288 | 0.3432 | ✅ |
| claude-haiku-4.5 | `anthropic/claude-haiku-4.5` | 1.0 | 5.0 | ✅ |
| claude-fable-5 | `anthropic/claude-fable-5` | 10.0 | 50.0 | ❌ removed (export-control, §10) |

### Run config (`config/run.yaml`)

- **Main pass:** temperature **0.0**, **max_tokens 1200**, **repeats 1** (single-shot per
  model × DP), 1 parse retry, invalid recorded as a column, **spend_cap_usd 20.00**, each
  (model, DP, repeat) disk-cached by content hash.
- **Consistency probe (`consistency_probe`):** the **20** highest cross-model action-
  disagreement DPs (logged to `probe_selection.json`), **5 samples** each, **temperature 1.0**.
  Sole source of the flip rate. **⚠️ Selection changed when Barcelona was added** — see §7.
- Mock mode is default; paid calls require `OPENROUTER_API_KEY` **and** `ALLOW_SPEND=1`.
- Live-demo subset (`live_models`, separate from the benchmark): claude-opus-4.8, gpt-5.5,
  deepseek-v3.2.

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

Only `dp.state` and `dp.question` are serialized — hindsight fields never reach the model.

---

## 7. SCORING (`src/boxbox/score/scoring.py`, `leaderboard.py`)

Let `sim_model` = Q-value of the model's answer, `sim_exante_optimal` / `sim_optimal` =
realized time of the ex-ante / hindsight oracle plan, `sim_team` = Q-value of the team's call.

- **`delta_exante = sim_model − sim_exante_optimal` — PRIMARY.** Lower = better; basis of
  ranking, H1, H3. (Can be slightly **negative** on a call where the realized SC made a model's
  choice beat the green-flag-optimal plan — e.g. several Barcelona DPs.)
- **`delta_hindsight = sim_model − sim_optimal`** — secondary. Always ≥ delta_exante per call.
- **`delta_vs_team = sim_model − sim_team`**; **`beat_team = sim_model < sim_team − 1e-9`**.
- **`agree_team_action`** = same PIT/STAY; **`agree_team_exact`** = also same compound.
- **`invalid`** = answer couldn't be parsed OR couldn't be valued. **Invalids are excluded from
  delta means** (and beat/agree %, over valid calls) but **counted in `invalid_pct`** (over ALL
  calls) and never drop a model.
- **Flip rate (`flip_rate_pct`), probe only:** for each model, over probe DPs sampled ≥ 2 times,
  a DP "flips" if its samples yield **> 1 distinct action**. Computed on the **dry** probe
  subset (**18** dry probe DPs of the 20 selected).

### ⚠️ Probe selection CHANGED when Barcelona was added (re-run, not frozen)

The probe selects the **20** highest cross-model action-disagreement DPs globally; selection
sorts by `(−disagreement, −n_models, dp_id ascending)`. Adding Barcelona introduced
**`2026-barcelona-L038-HAM-B`** at **disagreement 0.5** (PIT=2 / STAY=2 across 4 valid voters —
gpt-5.5 was invalid there), which outranks the large 0.4 tier. It **displaced the previous 20th
pick `2026-australia-L012-LIN-C`** (0.4, lost on the alphabetical dp_id tiebreak). **Net: one
swap**; the other 19 are unchanged. Per the decision on record, the consistency probe was
**re-run on the new selection** (25 new calls for the swapped-in DP; the 19 retained DPs hit
cache). Both swapped DPs are dry, so the **dry probe count stays 18 of 20**. The only flip-rate
that moved: **gpt-5.5 55.6% → 50.0%** (it had flipped on the dropped Australia DP). All other
flip rates are unchanged.

---

## 8. RESULTS

### 8a. Headline leaderboard — DRY subset (177 DPs, all 10 dry races, all seasons)

`leaderboard.json → models`. Ranked by mean `delta_exante` ascending.

| # | Model | Mean Δexante (s) | Median | Mean Δhindsight (s) | Beat team % | Agree team % | Invalid % | Flip % | Calls | Valid |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | deepseek-v3.2 | **4.736** | 0.0 | 5.562 | 18.1 | 72.9 | 0.0 | 38.9 | 177 | 177 |
| 2 | gemini-3.1-pro | 7.107 | 0.0 | 7.938 | 18.2 | 60.8 | 0.6 | 22.2 | 177 | 176 |
| 3 | claude-opus-4.8 | 7.337 | 0.0 | 8.163 | 21.5 | 59.3 | 0.0 | 5.6 | 177 | 177 |
| 4 | gpt-5.5 | 8.535 | 0.481 | 9.341 | 17.6 | 60.8 | 0.6 | 50.0 | 177 | 176 |
| 5 | claude-haiku-4.5 | 12.656 | 0.0 | 13.482 | 15.3 | 64.4 | 0.0 | 0.0 | 177 | 177 |

Aggregate: **883 valid scored calls** (177 × 5 − 2 invalids: gpt-5.5 on
`2026-barcelona-L038-HAM-B`, gemini on `2025-monaco-L032-ALB-C`). Note gemini moved
**#3 → #2** and opus **#2 → #3** vs the 10-race run (they were 7.37 vs 7.13, now reordered by
Barcelona).

### 8b. Appendix — FULL set (196 DPs, includes wet artifacts; NOT the headline)

`leaderboard.json → appendix_full_set`. Means inflated by the wet 2025-Silverstone calls.

| # | Model | Mean Δexante (s) | Median | Beat team % | Agree % | Invalid % | Flip % | Calls |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | gpt-5.5 | 18.245 | 1.607 | 16.4 | 61.0 | 0.5 | 50.0 | 196 |
| 2 | gemini-3.1-pro | 19.436 | 0.941 | 16.9 | 60.5 | 0.5 | 25.0 | 196 |
| 3 | claude-opus-4.8 | 19.694 | 0.363 | 19.9 | 59.2 | 0.0 | 5.0 | 196 |
| 4 | deepseek-v3.2 | 21.824 | 0.0 | 16.8 | 70.4 | 0.0 | 40.0 | 196 |
| 5 | claude-haiku-4.5 | 29.181 | 0.875 | 14.3 | 62.8 | 0.0 | 0.0 | 196 |

### 8c. ⚠️ Two "headline" definitions — they rank differently

- **Leaderboard headline (8a):** mean over **all 177 dry DPs (all seasons)**.
- **Prereg §3 PRIMARY:** mean `delta_exante` over the **126 2026 DPs** (here **125 dry**). Full
  2026-primary rows (computed read-only from `scores.jsonl`):

  | # | Model | Mean Δexante (s) | Median | Mean Δhindsight | Beat % | Agree % | Invalid % | Flip % | Valid |
  |---|---|---:|---:|---:|---:|---:|---:|---:|---:|
  | 1 | deepseek-v3.2 | **4.934** | 0.0 | 6.103 | 19.2 | 69.6 | 0.0 | 38.9 | 125 |
  | 2 | gpt-5.5 | 8.076 | 0.0 | 9.220 | 19.4 | 58.1 | 0.8 | 50.0 | 124 |
  | 3 | gemini-3.1-pro | 8.077 | 0.0 | 9.246 | 20.0 | 56.0 | 0.0 | 22.2 | 125 |
  | 4 | claude-haiku-4.5 | 8.809 | 0.0 | 9.978 | 16.0 | 64.0 | 0.0 | 0.0 | 125 |
  | 5 | claude-opus-4.8 | 9.211 | 0.0 | 10.380 | 24.0 | 51.2 | 0.0 | 5.6 | 125 |

  **deepseek is #1 under both definitions.** But the middle reorders: on the 2026-only set
  **gpt-5.5 and gemini are tied at ~8.08** and **opus falls to #5 (9.21)** — opus is unusually
  strong on pre-2026 (2024 mean 2.661) and weaker on 2026. **Pick one definition for the paper's
  headline and use it consistently.** The figures (§9) use the **2026 primary set**.

### 8d. Per-decision-type performance (dry subset, 177; from `scores.jsonl`)

Mean `delta_exante` (s):

| Model | A (pit-window) | B (safety-car) | C (undercut) |
|---|---:|---:|---:|
| claude-haiku-4.5 | 19.453 | 2.940 | 12.175 |
| claude-opus-4.8 | 8.672 | 8.993 | 5.103 |
| deepseek-v3.2 | 3.150 | 4.946 | 6.083 |
| gemini-3.1-pro | 10.503 | 5.960 | 4.607 |
| gpt-5.5 | 13.218 | 9.899 | 3.388 |

Per-type overall (all models pooled, dry): **A:** mean 10.999 / median 1.381 (n=325);
**B:** mean 6.532 / median 0.000 (n=209); **C:** mean 6.276 / median 0.000 (n=349). Type A
(pit-window timing) remains the hardest type on average. (H6, exploratory.)

### 8e. Contamination (H3) — `outputs/contamination.md` — ⚠️ SHIFTED with Barcelona

Per-season mean / median `delta_exante` (n), and the **H3 test: two-sided Mann–Whitney U on
per-DP `delta_exante`, pre-2026 vs 2026, Holm-corrected across the 5 models.** Negative gap =
better (lower) on pre-2026 = possible recall.

| Model | 2024 | 2025 | 2026 | pre-2026 (24–25) | gap (pre−2026) | raw p | Holm p | verdict @0.05 |
|---|---|---|---|---|---:|---:|---:|---|
| claude-haiku-4.5 | 28.336 / 4.176 (n=34) | 9.756 / 3.691 (n=18) | 8.809 / 0.0 (n=125) | 21.905 / 3.691 (n=52) | **+13.096** | 0.0001 | **0.0005** | **worse on pre-2026** |
| gpt-5.5 | 12.964 / 3.612 (n=34) | 3.331 / 3.104 (n=18) | 8.076 / 0.0 (n=124) | 9.629 / 3.104 (n=52) | **+1.553** | 0.0029 | **0.0115** | **worse on pre-2026** |
| deepseek-v3.2 | 1.35 / 0.0 (n=34) | 9.756 / 3.691 (n=18) | 4.934 / 0.0 (n=125) | 4.26 / 0.824 (n=52) | **−0.674** | 0.0038 | **0.0115** | **recall signal** (better pre-2026) |
| gemini-3.1-pro | 5.332 / 1.901 (n=34) | 3.527 / 3.146 (n=17) | 8.077 / 0.0 (n=125) | 4.73 / 2.987 (n=51) | **−3.347** | 0.0148 | **0.0296** | **recall signal** (better pre-2026) |
| claude-opus-4.8 | 2.661 / 0.0 (n=34) | 3.156 / 3.024 (n=18) | 9.211 / 0.0 (n=125) | 2.832 / 0.961 (n=52) | −6.379 | 0.3377 | 0.3377 | no significant gap |

**⚠️ KEY CHANGE FROM THE 10-RACE RESULT.** Adding Barcelona — a 2026 race where models scored
**well** (low deltas; see §8g) — pulled the 2026 distributions down enough that the
Holm-corrected MWU now flags **two models (deepseek, gemini) as significantly BETTER on pre-2026
(a weak recall signal)**, where the 10-race run found *none*. The magnitudes are small
(deepseek −0.67 s, gemini −3.35 s) but the rank-sum test is significant. gpt-5.5 also crosses
into "significantly **worse** on pre-2026." Opus shows no significant gap. **This nuances the
earlier "no model is better on pre-2026" framing — the paper must now report a small but
significant recall signal in deepseek and gemini on the dry subset.** Pooled: **883 valid scored
calls**, **95 changeable-condition calls excluded** (= 19 DPs × 5 models).

### 8f. Monaco same-track (2024 / 2025 / 2026, constant circuit) — mean `delta_exante`

**Unaffected by Barcelona — confirmed identical to the 10-race run** (Barcelona adds no Monaco
data).

| Model | 2024-monaco (n=16) | 2025-monaco (n=18) | 2026-monaco (n=18) |
|---|---:|---:|---:|
| claude-haiku-4.5 | 49.154 | 9.756 | 3.788 |
| claude-opus-4.8 | 2.766 | 3.156 | 2.8 |
| deepseek-v3.2 | 2.766 | 9.756 | 4.169 |
| gemini-3.1-pro | 5.528 | 3.527 | 4.867 |
| gpt-5.5 | 14.006 | 3.331 | 0.716 |

No clean monotone pre-2026 advantage on the same track; if anything most models are **best on
2026-Monaco** (opposite of a recall signal). The same-track view does **not** corroborate the
weak cross-race recall signal in §8e.

### 8g. Barcelona / 2026 Spanish GP — per-model row (new race #11)

Mean / median `delta_exante` on Barcelona's 18 DPs (from `scores.jsonl`). Models did **well**
here — several negative means/medians (the realized race rewarded their calls vs the green-flag
ex-ante optimum), which is what drove the H3 shift in §8e.

| Model | Mean Δexante (s) | Median | Beat team % | Agree team % | Valid |
|---|---:|---:|---:|---:|---:|
| deepseek-v3.2 | **−0.27** | −3.54 | 16.7 | 72.2 | 18/18 |
| gpt-5.5 | 2.29 | −2.21 | 11.8 | 76.5 | 17/18 (1 invalid: L038-HAM-B) |
| gemini-3.1-pro | 4.76 | −1.07 | 5.6 | 66.7 | 18/18 |
| claude-opus-4.8 | 8.58 | −2.87 | 16.7 | 66.7 | 18/18 |
| claude-haiku-4.5 | 11.71 | 0.00 | 0.0 | 66.7 | 18/18 |

Barcelona ranking mirrors the overall 2026 ranking (deepseek best, haiku worst), but the
absolute deltas are unusually low — Barcelona is the easiest 2026 race for the field so far.

### 8h. Claude Fable 5 head-to-head (exploratory, n = 3) — `outputs/fable_comparison.md`

Unchanged (cached pre-suspension smoke-v2 calls; not in the leaderboard). 3 DPs, anecdote only.

---

## 9. FIGURES

### Regenerated against the 11-race numbers — `outputs/figures/`

| File | Title | Shows |
|---|---|---|
| `leaderboard_bar.png` | "BOXBOX leaderboard — 2026 primary set (real data)" | bar of mean Δexante + Δhindsight per model **on the 2026 PRIMARY set (125)** — fixes the earlier all-seasons-vs-2026 mismatch |
| `accuracy_vs_consistency.png` | "Accuracy vs. consistency (2026 primary set)" | scatter: x = mean Δexante (2026 primary), y = flip rate %; bottom-left = ideal |
| `delta_distribution.png` | "score-delta distribution per model" | per-model Δ distribution (dry) |
| `race_heatmap.png` | "per-race performance heatmap" | model × **race** mean Δ (now incl. Barcelona column) |
| `flip_rate.png` | "consistency: how often repeated prompts flip the call" | per-model flip rate (new probe) |
| `season_gap.png` | "contamination gap: old vs new races" | per-model pre-2026 vs 2026 gap |

- **The accuracy-vs-consistency scatter and the 2026-primary leaderboard bar are now generated
  by `analysis/figures.py`** (previously the scatter was an uncommitted one-off). Both read the
  2026 primary set directly from `scores.jsonl`.

### Calibration — `outputs/calibration/` (11 per-race, now incl. `2026-barcelona.png`)

### Still missing / conceptual

- **Decision-point schematic** (figure 6 in the plan) is a conceptual diagram, never
  auto-generated — still to be drawn by hand if wanted.
- A dedicated **per-type** figure does not exist (per-type numbers are in §8d; the heatmap is
  per-race).

---

## 10. PREREGISTRATION TRAIL (v1 → v4) + Barcelona amendment

Source: `docs/PREREGISTRATION.md`, `docs/DECISIONS.md`.

- **prereg-v1** (2026-06-13, tag `prereg-v1`): original **six-model** design, methodology
  frozen before any full results (H1–H6, dataset + extraction rules, simulator/oracle, prompt
  v1, run/probe config).
- **prereg-v2** (2026-06-13) — **Claude Fable 5 removed** (six → five). On 2026-06-12 a US
  export-control directive suspended access (API 404 confirmed 2026-06-13; only the roster
  changed).
- **prereg-v3** (2026-06-13) — **headline metric on the DRY subset** (wet exclusion); the v1
  single-stint simulator cannot model a wet→dry crossover.
- **prereg-v4** (2026-06-13) — **wet detection corrected at the source** via
  `wet_running_near(t, window=5)` (leakage-safe). Silverstone stays fully excluded (18/18);
  Miami now INCLUDED; Canada keeps only L004. Dry subset (10 races) was 142 → 159, exclusions
  36 → 19.
- **Barcelona amendment** (2026-06-17) — **2026 Spanish GP (Round 7) added as race #11**, a
  post-cutoff dry race. Config fix: `event: barcelona`, race_id `2026-barcelona` (bare "Spain"
  resolves to the future Madrid round, R14, and is avoided). Re-ran the **main pass** (90 new
  Barcelona calls; the 10 prior races hit cache) and, because the swap below changed the probe
  selection, **re-ran the consistency probe** (25 new calls). **Outcomes:** dry subset 159 →
  **177**, full set 178 → **196**, 2026 primary 107 → **125 dry**. Probe selection gained
  `2026-barcelona-L038-HAM-B` (disagreement 0.5) and dropped `2026-australia-L012-LIN-C` (§7).
  **H3 shifted** (deepseek + gemini now show a weak significant recall signal; §8e). H1/H2 still
  confirmed on both sets. Only 2 invalids remain (gpt-5.5 L038-HAM-B, gemini 2025-monaco-L032).

---

## 11. REPRODUCIBILITY

### Commands (`CLAUDE.md`)
```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
pytest
python scripts/build_dataset.py          # ingest -> extract -> data/decision_points/
python scripts/run_benchmark.py --real    # main pass (needs OPENROUTER_API_KEY + ALLOW_SPEND=1)
python scripts/run_consistency_probe.py --real  # top-disagreement DPs x5 -> sole flip-rate source
python scripts/score_results.py          # scores -> outputs/leaderboard.{md,csv,json}
python scripts/hypothesis_tests.py       # H1/H2 -> docs/hypothesis_tests.md
python scripts/contamination_report.py   # H3 + Monaco -> outputs/contamination.md
python analysis/figures.py               # outputs/figures/
```
The frozen procedure is the code/config at tag `prereg-v1`; amendments are prereg-v2…v4 + the
Barcelona amendment (2026-06-17). Public timing feeds only (FastF1, OpenF1 fallback).

### Total spend (`outputs/cost_ledger.csv`)

| Component | Spend |
|---|---:|
| Benchmark before Barcelona (main + probe + smoke + v4 reruns) | $12.4986 |
| Barcelona main pass (90 new calls) | +$0.7259 |
| Barcelona probe re-run (25 new calls) | +$0.2405 |
| **Benchmark total (non-live)** | **$13.4635** |
| Live Barcelona demo (separate, NOT benchmark) | $0.6936 |
| **Grand total (ledger)** | **$14.1570** |

Quote the **benchmark** spend as **≈ $13.46**; the **$0.69 live demo is separate**. Spend cap
was $20.00 (never hit; max projected breach check passed).

### Test count
**61 tests** (`pytest --co`), all green. `scripts/hypothesis_tests.py` was added as a committed,
reproducible generator for H1/H2 (seed 1234, 10,000 bootstrap resamples) — previously the H1/H2
artifact was produced by a one-off.

---

### Open items to resolve before submission
1. ✅ Resolved — LIMITATIONS #10 (mock→real) and #11 (→ 19/177) corrected.
2. ✅ Resolved — H1/H2/H3 all computed on the 11-race set (`docs/hypothesis_tests.md`,
   `outputs/contamination.md`).
3. **Decide the single headline definition** (all-seasons dry 177 vs 2026-only 125) and use it
   consistently — they reorder models 2–5.
4. ⚠️ **Report the H3 shift honestly** — deepseek and gemini now show a small but significant
   "better on pre-2026" recall signal on the dry subset; this changes the contamination-proof
   framing from "no signal" to "weak signal in 2/5 models, not corroborated on same-track
   Monaco." (§8e/§8f.)
5. ✅ Resolved — accuracy-vs-consistency scatter + 2026-primary leaderboard bar now generated by
   `analysis/figures.py`. **Decision-point schematic** (conceptual) still to be drawn by hand.
6. ✅ Resolved — **Barcelona is now race #11** (post-cutoff, dry, 18 DPs, 0 excluded), fully
   integrated across leaderboard / H1 / H2 / H3 / figures.
