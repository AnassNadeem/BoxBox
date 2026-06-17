# BOXBOX leaderboard

Generated 2026-06-16T20:28:21+00:00 | mode: **real** | **headline = dry subset**: 177 decision points (of 196 total; 19 changeable-condition DPs excluded) | races: 2024-bahrain, 2024-monaco, 2025-monaco, 2026-australia, 2026-barcelona, 2026-canada, 2026-china, 2026-japan, 2026-miami, 2026-monaco

Flip rate from a 18-DP consistency probe (dry subset, resampled at the probe temperature); other columns from the main pass.

## Headline (dry subset — changeable-condition DPs excluded)

| # | Model | Mean delta vs ex-ante optimal (s) | Median (s) | Mean delta vs hindsight (s) | Beat team % | Agree team % | Invalid % | Flip rate % | Calls |
|---|-------|----------------------------------:|-----------:|----------------------------:|------------:|-------------:|----------:|------------:|------:|
| 1 | deepseek-v3.2 | 4.736 | 0.0 | 5.562 | 18.1 | 72.9 | 0.0 | 38.9 | 177 |
| 2 | gemini-3.1-pro | 7.107 | 0.0 | 7.938 | 18.2 | 60.8 | 0.6 | 22.2 | 177 |
| 3 | claude-opus-4.8 | 7.337 | 0.0 | 8.163 | 21.5 | 59.3 | 0.0 | 5.6 | 177 |
| 4 | gpt-5.5 | 8.535 | 0.481 | 9.341 | 17.6 | 60.8 | 0.6 | 50.0 | 177 |
| 5 | claude-haiku-4.5 | 12.656 | 0.0 | 13.482 | 15.3 | 64.4 | 0.0 | 0.0 | 177 |

## Excluded changeable-condition decision points (per race)

| Race | Excluded | Total |
|---|---:|---:|
| 2025-silverstone | 18 | 18 |
| 2026-canada | 1 | 18 |

**19** DPs excluded from the headline. The v1 simulator runs a single stint to the flag and cannot model a wet->dry crossover, so wet/changeable-condition decision points are out of scope for the headline metric (criterion in docs/PREREGISTRATION.md; consistent with the prereg's no-wet-modeling scope).

## Appendix: full set (INCLUDES changeable-condition DPs — not the headline)

> These numbers include wet/changeable decision points the v1 simulator cannot model (a wet-tyre pit is run to the flag at wet pace), which inflates the means. Shown for completeness only.

| # | Model | Mean delta vs ex-ante optimal (s) | Median (s) | Mean delta vs hindsight (s) | Beat team % | Agree team % | Invalid % | Flip rate % | Calls |
|---|-------|----------------------------------:|-----------:|----------------------------:|------------:|-------------:|----------:|------------:|------:|
| 1 | gpt-5.5 | 18.245 | 1.607 | 18.972 | 16.4 | 61.0 | 0.5 | 50.0 | 196 |
| 2 | gemini-3.1-pro | 19.436 | 0.941 | 20.185 | 16.9 | 60.5 | 0.5 | 25.0 | 196 |
| 3 | claude-opus-4.8 | 19.694 | 0.363 | 20.439 | 19.9 | 59.2 | 0.0 | 5.0 | 196 |
| 4 | deepseek-v3.2 | 21.824 | 0.0 | 22.569 | 16.8 | 70.4 | 0.0 | 40.0 | 196 |
| 5 | claude-haiku-4.5 | 29.181 | 0.875 | 29.926 | 14.3 | 62.8 | 0.0 | 0.0 | 196 |
