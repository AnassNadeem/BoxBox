# BOXBOX — Pre-registered hypothesis tests H1 & H2

Computes the two pre-registered confirmatory/secondary tests that were not previously
emitted as artifacts (only H3 / contamination existed). **Read-only, no spend, no model
calls** — derived from `outputs/scores.jsonl` (the real prereg-v4 run dated
2026-06-13T22:00:36Z).

- **H1 (primary — models are sub-optimal):** per model, reject "ex-ante-optimal on average"
  if the 95% bootstrap CI of mean `delta_exante` **excludes 0** (prereg §2). Lower
  `delta_exante` = better; a CI strictly above 0 means the model loses time vs the ex-ante
  optimum on average.
- **H2 (secondary — human pit wall is a strong baseline):** per model, two-sided binomial
  test of the `beat_team` count against chance p = 0.5 (prereg §2). H2 predicts the
  beat-team share is **< 50%**.

**Method (fixed for reproducibility):** percentile bootstrap, **10,000 resamples** over
decision points (resample each model's valid calls with replacement, take the mean,
report the 2.5/97.5 percentiles), **`numpy` default_rng seed = 1234**. Binomial:
`scipy.stats.binomtest(k, n, 0.5, alternative="two-sided")`. Valid call = not invalid and
`delta_exante_s` is not None; `beat_team` = `sim_model < sim_team − 1e-9`. Both sets are the
**dry subset** (`changeable_conditions == false`). scipy 1.17.1 / numpy 2.4.6.

Two evaluation sets are reported so the headline can be chosen:
- **2026-only dry** = the prereg's PRIMARY set (post-cutoff races only), **107 DPs**.
- **All-seasons dry** = the leaderboard's headline subset (9 dry races), **159 DPs**.

---

## H1 — 95% bootstrap CI of mean `delta_exante` (s)

### Set A: 2026-only dry (107 DPs)

| Model | Mean Δexante (s) | 95% CI | Excludes 0? | n valid |
|---|---:|---|:--:|---:|
| deepseek-v3.2 | 5.809 | [2.111, 10.723] | **YES** | 107 |
| claude-haiku-4.5 | 8.321 | [4.939, 12.060] | **YES** | 107 |
| gemini-3.1-pro | 8.635 | [5.417, 12.343] | **YES** | 107 |
| gpt-5.5 | 8.996 | [5.795, 12.659] | **YES** | 107 |
| claude-opus-4.8 | 9.232 | [5.969, 12.860] | **YES** | 106 |

### Set B: all-seasons dry (159 DPs)

| Model | Mean Δexante (s) | 95% CI | Excludes 0? | n valid |
|---|---:|---|:--:|---:|
| deepseek-v3.2 | 5.303 | [2.485, 8.905] | **YES** | 159 |
| claude-opus-4.8 | 7.126 | [4.846, 9.641] | **YES** | 158 |
| gemini-3.1-pro | 7.375 | [5.096, 9.938] | **YES** | 158 |
| gpt-5.5 | 9.203 | [6.491, 12.202] | **YES** | 159 |
| claude-haiku-4.5 | 12.764 | [9.077, 16.787] | **YES** | 159 |

**H1 verdict: confirmed for all 5 models on both sets.** Every 95% CI lies strictly above
0, so each model loses a statistically clear amount of time relative to the ex-ante optimum
— no model is ex-ante-optimal on average.

> Note on H1's "separable" sub-clause: the prereg also states the models should be
> separable on this metric. These per-model CIs **overlap substantially** (e.g. on the
> 2026 set all five CIs overlap in roughly [6, 10] s), so the models are **not cleanly
> separated by non-overlapping 95% CIs**. That is an informal read, not a formal pairwise
> separability test (which the prereg did not specify a procedure for); deepseek is the
> point-estimate best on both sets but its CI overlaps the others'.

---

## H2 — two-sided binomial test of `beat_team` vs chance (p = 0.5)

### Set A: 2026-only dry (107 DPs)

| Model | Beat team % | k / n | p (two-sided) | Sig @0.05? | Direction |
|---|---:|---:|---:|:--:|---|
| claude-opus-4.8 | 25.5 | 27 / 106 | 4.328e-07 | **YES** | below 50% |
| gemini-3.1-pro | 22.4 | 24 / 107 | 8.578e-09 | **YES** | below 50% |
| gpt-5.5 | 20.6 | 22 / 107 | 6.375e-10 | **YES** | below 50% |
| deepseek-v3.2 | 19.6 | 21 / 107 | 1.601e-10 | **YES** | below 50% |
| claude-haiku-4.5 | 18.7 | 20 / 107 | 3.796e-11 | **YES** | below 50% |

### Set B: all-seasons dry (159 DPs)

| Model | Beat team % | k / n | p (two-sided) | Sig @0.05? | Direction |
|---|---:|---:|---:|:--:|---|
| claude-opus-4.8 | 22.2 | 35 / 158 | 1.120e-12 | **YES** | below 50% |
| gemini-3.1-pro | 19.6 | 31 / 158 | 5.383e-15 | **YES** | below 50% |
| deepseek-v3.2 | 18.2 | 29 / 159 | 1.806e-16 | **YES** | below 50% |
| gpt-5.5 | 18.2 | 29 / 159 | 1.806e-16 | **YES** | below 50% |
| claude-haiku-4.5 | 17.0 | 27 / 159 | 8.287e-18 | **YES** | below 50% |

**H2 verdict: confirmed for all 5 models on both sets.** Every model beats the real team on
**well under half** of valid calls (17–26%), and the two-sided binomial rejects p = 0.5 at
α = 0.05 for all models (all p < 1e-6). The human pit wall is a strong baseline: no model
beats it more often than it loses to it.

---

## Summary

| Hypothesis | 2026-only dry (107) | All-seasons dry (159) |
|---|---|---|
| **H1** (CI of mean Δexante excludes 0) | 5/5 exclude 0 — all sub-optimal | 5/5 exclude 0 — all sub-optimal |
| **H2** (beat_team ≠ 50%, two-sided) | 5/5 significant, all < 50% | 5/5 significant, all < 50% |

Both pre-registered tests are confirmed on both candidate headline sets. Point estimates,
n, and the per-call `beat_team`/`delta_exante` fields match `outputs/leaderboard.json` and
`docs/paper_data.md` §8. Regenerate with the seed/method above against `outputs/scores.jsonl`.
