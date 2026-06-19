# BOXBOX — Pre-registered hypothesis tests H1 & H2

Read-only, no spend, no model calls — derived from `outputs/scores.jsonl` (the real prereg-v4 run, refreshed with Barcelona / 2026 Spanish GP, Round 7).

- **H1 (primary — models are sub-optimal):** per model, reject "ex-ante-optimal on average" if the 95% bootstrap CI of mean `delta_exante` **excludes 0** (prereg §2). Lower `delta_exante` = better; a CI strictly above 0 means the model loses time vs the ex-ante optimum on average.
- **H2 (secondary — human pit wall is a strong baseline):** per model, two-sided binomial test of the `beat_team` count against chance p = 0.5 (prereg §2). H2 predicts the beat-team share is **< 50%**.

**Method (fixed for reproducibility):** percentile bootstrap, **10,000 resamples** over decision points (resample each model's valid calls with replacement, take the mean, report the 2.5/97.5 percentiles), **`numpy` default_rng seed = 1234**. Binomial: `scipy.stats.binomtest(k, n, 0.5, alternative="two-sided")`. Valid call = not invalid and `delta_exante_s` is not None; `beat_team` = `sim_model < sim_team`. Both sets are the **dry subset** (`changeable_conditions == false`).

Two evaluation sets are reported so the headline can be chosen:
- **2026-only dry** = the prereg's PRIMARY set (post-cutoff races only), **125 DPs**.
- **All-seasons dry** = the leaderboard's headline subset, **177 DPs**.

---

## H1 — 95% bootstrap CI of mean `delta_exante` (s)

### Set A: 2026-only dry (125 DPs)

| Model | Mean Δexante (s) | 95% CI | Excludes 0? | n valid |
|---|---:|---|:--:|---:|
| deepseek-v3.2 | 4.934 | [1.550, 9.257] | **YES** | 125 |
| gpt-5.5 | 8.076 | [5.163, 11.357] | **YES** | 124 |
| gemini-3.1-pro | 8.077 | [4.955, 11.496] | **YES** | 125 |
| claude-haiku-4.5 | 8.809 | [5.532, 12.432] | **YES** | 125 |
| claude-opus-4.8 | 9.211 | [5.865, 12.868] | **YES** | 125 |

### Set B: all-seasons dry (177 DPs)

| Model | Mean Δexante (s) | 95% CI | Excludes 0? | n valid |
|---|---:|---|:--:|---:|
| deepseek-v3.2 | 4.736 | [2.100, 8.045] | **YES** | 177 |
| gemini-3.1-pro | 7.107 | [4.874, 9.635] | **YES** | 176 |
| claude-opus-4.8 | 7.337 | [4.943, 9.979] | **YES** | 177 |
| gpt-5.5 | 8.535 | [6.022, 11.337] | **YES** | 176 |
| claude-haiku-4.5 | 12.656 | [8.993, 16.448] | **YES** | 177 |

**H1 verdict:** confirmed for all 5 models on both sets — every 95% CI lies strictly above 0, so each model loses a statistically clear amount of time relative to the ex-ante optimum; no model is ex-ante-optimal on average.

---

## H2 — two-sided binomial test of `beat_team` vs chance (p = 0.5)

### Set A: 2026-only dry (125 DPs)

| Model | Beat team % | k / n | p (two-sided) | Sig @0.05? | Direction |
|---|---:|---:|---:|:--:|---|
| claude-haiku-4.5 | 16.0 | 20 / 125 | 4.134e-15 | **YES** | below 50% |
| deepseek-v3.2 | 19.2 | 24 / 125 | 1.970e-12 | **YES** | below 50% |
| gpt-5.5 | 19.4 | 24 / 124 | 3.193e-12 | **YES** | below 50% |
| gemini-3.1-pro | 20.0 | 25 / 125 | 8.085e-12 | **YES** | below 50% |
| claude-opus-4.8 | 24.0 | 30 / 125 | 4.660e-09 | **YES** | below 50% |

### Set B: all-seasons dry (177 DPs)

| Model | Beat team % | k / n | p (two-sided) | Sig @0.05? | Direction |
|---|---:|---:|---:|:--:|---|
| claude-haiku-4.5 | 15.3 | 27 / 177 | 7.144e-22 | **YES** | below 50% |
| gpt-5.5 | 17.6 | 31 / 176 | 7.906e-19 | **YES** | below 50% |
| deepseek-v3.2 | 18.1 | 32 / 177 | 2.205e-18 | **YES** | below 50% |
| gemini-3.1-pro | 18.2 | 32 / 176 | 3.620e-18 | **YES** | below 50% |
| claude-opus-4.8 | 21.5 | 38 / 177 | 9.937e-15 | **YES** | below 50% |

**H2 verdict:** confirmed for all 5 models on both sets — every model beats the real team on well under half of valid calls, and the two-sided binomial rejects p = 0.5 at α = 0.05 for all models. The human pit wall is a strong baseline.

---

## Summary

| Hypothesis | 2026-only dry (125) | All-seasons dry (177) |
|---|---|---|
| **H1** (CI of mean Δexante excludes 0) | 5/5 exclude 0 | 5/5 exclude 0 |
| **H2** (beat_team ≠ 50%, two-sided) | 5/5 sig & <50% | 5/5 sig & <50% |
