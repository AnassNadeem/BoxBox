# BOXBOX: Benchmarking Frontier Language Models on Formula 1 Race Strategy

*Draft skeleton — results pending real model runs.*

## Abstract

(stub) We introduce BOXBOX, a benchmark that tests whether frontier large language
models can make competent Formula 1 race-strategy decisions under the information
constraints of a real pit wall. From the timing data of six 2026 Grands Prix — all of
which post-date the training cutoffs of every evaluated model — we mechanically
reconstruct 108 frozen decision points (pit now or stay out; which tyre compound)
balanced across pit-window, safety-car, and undercut-threat situations, and pose
them to N models under identical prompts. Calls are scored against two oracles
computed by a per-race simulator calibrated on each race's own lap data (median
calibration error ≈ 0.09 s/lap): an ex-ante optimum restricted to the models' own
information set (no future safety-car knowledge; the primary metric) and a
hindsight optimum (secondary). We report (i) mean time lost versus the ex-ante
optimum, (ii) how often models beat the real teams' decisions, (iii)
output-validity rates and an answer-consistency probe on the most contentious
decision points, and (iv) a contamination analysis comparing performance on 2026
races against 2024–25 races that plausibly appear in training corpora. (Headline
numbers TBD.)

## 1. Introduction (outline)

- Strategy calls in F1 are high-stakes, time-pressured decisions over structured,
  partially observable state — a natural probe of LLM decision-making, distinct from
  knowledge recall.
- Contamination is the central methodological problem for LLM benchmarks; sports
  events after a model's cutoff provide naturally uncontaminated, verifiable test sets.
- Contributions: (1) a mechanically extracted, leakage-tested decision-point dataset
  from 2026 races; (2) a transparent simulator-based scoring oracle with published
  calibration; (3) a multi-model evaluation incl. consistency and contamination-gap
  analyses; (4) an open pipeline that re-runs on any future race weekend, including live.

## 2. Related work (outline)

- LLM agentic/decision benchmarks; forecasting benchmarks; game-playing evaluations.
- Data contamination studies and post-cutoff evaluation designs.
- Motorsport strategy optimization literature (dynamic programming / Monte Carlo
  pit-stop models).

## 3. Method

### 3.1 Decision-point extraction

We ingest official timing data for each race via FastF1 (OpenF1 as a fallback path)
and normalize it to a per-lap record schema. Decision points are extracted by three
mechanical rules, never by hand: **(A) pit-stop neighborhoods** — for every real pit
stop by a classified car, the laps {s−2, s−1, s} around the stop lap s; **(B)
safety-car moments** — the first lap of every Safety Car or Virtual Safety Car period,
for each car running in the top ten; **(C) undercut threats** — when a directly
adjacent rival (within ±1 race position and within 3.5 s) pits, the following lap for
the threatened car. Overlapping triggers for the same (car, lap) are deduplicated with
priority B > C > A. Each race is capped at 18 points under a per-type quota of six;
a type with fewer than six candidates donates its unused slots to the remaining types
in priority order B > C > A, and within a type the closest battles are kept first.
The first three and last two laps, lapped cars, and cars within three laps of
retirement are excluded (the latter prevents leaking an upcoming retirement).

A decision point at lap *t* freezes exactly the information available entering lap
*t*: every field derives from completed laps ≤ *t−1*, plus the track status current
during lap *t* (real-time race-control knowledge). The state contains the track,
lap counts, weather, track status, an estimated pit loss for the circuit, the focal
car's position, compound, tyre age, compounds used/available, last three lap times,
and gaps to (and tyre state of) the cars ahead and behind, plus a top-ten summary
table. A structural leakage test asserts that deleting all laps > *t* from the input
changes no field of any emitted state; determinism and count-bound tests accompany it.

### 3.2 Scoring oracle (simulator)

For each race we fit per-(driver, compound) lap-time models
`lap_time = a + b·tyre_age + c·lap_number` on clean laps (green flag, dry, no in/out
laps, >3-MAD residual outliers removed), with a fallback chain driver → team-mate →
field-pooled fit when data is thin. Where tyre age and lap number are collinear
(single-stint data) the fuel term is dropped. Predictions are clamped to physical
bounds (observed age range; race-fastest lap floor). Pit loss is the median of
(in-lap + out-lap − 2 × clean median) over the race's real stops; an SC-era pit-loss
factor is measured from the race's own SC stops where possible (default 0.55).

Given a decision point and a candidate action we roll out only the focal car's
remaining laps, holding all other cars and the SC/VSC timeline fixed at what actually
happened; SC/VSC and rain-neutralized laps are charged at the field-median time of
that lap. The candidate space is: pit at the end of any lap from *t* to the
penultimate lap onto any available compound, or make no further stop, subject to the
two-compound rule in dry races.

Two oracles are computed over this candidate space, sharing the same fitted
lap-time models. The **hindsight oracle** picks the plan minimizing realized time
(it knows the future SC/VSC timeline). The **ex-ante oracle** picks the plan
minimizing time under a green-flag assumption for every lap after *t* — the same
information set the models decide under (the current lap's track status is
real-time knowledge and is kept). Both oracles' plans are then valued in the race
as it actually unfolded, so the two baselines share one currency and the ex-ante
optimum's realized time can never beat the hindsight optimum (asserted by tests).
Our primary metric is `delta_exante = sim(model) − sim(exante_optimal)`; we report
`delta_hindsight = sim(model) − sim(hindsight_optimal)` as secondary context,
along with `beat_team = sim(model) < sim(team)`.

**Q-value framing.** Formally, each immediate action is scored as its Q-value: the
best achievable total remaining race time conditional on taking that action at lap
*t*, minimizing over all continuations in the candidate strategy space. For PIT
onto compound *c*, this is the realized time of the best plan that stops at the end
of lap *t* onto *c* (including, where the two-compound rule makes *c* illegal as a
final stint, the cheapest legalizing later stop); for STAY, it is the realized time
of the best legal plan that does not stop at lap *t*. The hindsight optimum is thus
the minimum over action Q-values, and an action's hindsight delta is zero exactly
when it is consistent with an optimal plan. This charitable valuation scores the
decision itself rather than any fixed continuation, and is applied identically to
model answers and to the real team's call — so agreement with the team scores as
an exact tie.

Calibration: across the ten ingested races the simulator reproduces real stint times
with mean MAE ≈ 0.22 s/lap (median 0.09); per-race figures are published with the
pipeline. The oracle's hindsight knowledge of future SC periods is a disclosed,
deliberate design choice: deltas measure distance from hindsight-perfect, uniformly
across models.

### 3.3 Evaluation harness

Every model receives the identical prompt: a system instruction ("You are the chief
race strategist for the focal car's team... output strict JSON, nothing else"), the
serialized state, the question, and the output schema
`{"action": "PIT"|"STAY", "compound": ..., "confidence": ..., "rationale": ...}`.
Calls run through OpenRouter at temperature 0, max 350 tokens, JSON response format
where supported, with one retry on parse failure; unparseable answers are recorded as
invalid (a leaderboard column, not an exclusion). Each (model, decision point,
repeat) is disk-cached by content hash; repeated runs are free and reproducible. The
main pass is single-shot per (model, decision point). Answer consistency is measured
by a separate probe: the twenty decision points with the highest cross-model action
disagreement in the main pass (selection logged with reasons) are rerun for all
models with five samples each at the provider-default temperature, and the "flip
rate" is computed exclusively from these probe samples. Token usage is read from API
responses and priced into a cost ledger with a hard spend cap. A deterministic mock
model exercises the full pipeline without spend.

### 3.4 Contamination analysis

The identical pipeline runs on four 2024–25 races (Bahrain 2024, Monaco 2024, Monaco
2025, Silverstone 2025). Every decision point is season-tagged; we compare each
model's delta distribution on pre-cutoff races (plausibly in training data, with
extensively documented strategies) against 2026 races. A significantly better score
on old races is evidence of recall rather than reasoning.

## 4. Results (placeholders)

### Table 1: Main leaderboard
| Model | Mean Δ ex-ante (s) | Median Δ ex-ante | Mean Δ hindsight (s) | Beat team % | Agree team % | Invalid % | Flip % (probe) |
|---|---|---|---|---|---|---|---|
| TBD | | | | | | | |

### Table 2: Contamination gap
| Model | Δ 2024–25 (s) | Δ 2026 (s) | Gap | p-value |
|---|---|---|---|---|
| TBD | | | | |

### Table 3: Performance by decision type (A/B/C)
| Model | Pit windows (A) | SC moments (B) | Undercut threats (C) |
|---|---|---|---|
| TBD | | | |

- Figure 1: leaderboard bar chart. Figure 2: delta distributions. Figure 3: per-race
  heatmap. Figure 4: flip rate. Figure 5: contamination gap. (Templates rendered from
  mock data in `outputs/figures/`.)

## 5. Limitations

Imported from `docs/LIMITATIONS.md` (kept authoritative there): no traffic
interaction in counterfactual rollouts (headline); single-further-stop strategy
space; linear degradation; assumed compound availability; SC laps as field-median
time; residual hindsight in the ex-ante baseline (realized valuation, no
probabilistic SC model); interval-approximated gaps; scalar per-race pit loss;
tyre-age provenance for used sets; mock numbers are placeholders.

## 6. Ethics and reproducibility

- No proprietary data: public timing feeds only. No betting use intended.
- Full pipeline, configs, prompts, and cache keys are versioned; every reported
  number is regenerable from `scripts/` entry points.
