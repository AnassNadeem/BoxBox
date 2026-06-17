# BOXBOX contamination analysis

Primary metric **delta_exante** (s; lower = better). 2026 races post-date every
model's training cutoff; 2024-25 races plausibly appear in training data. A model
scoring **better (lower) on pre-2026** is evidence of recall, not reasoning (prereg H3).

Source: `outputs/scores.jsonl` (main pass). **Headline = DRY subset**: 883 valid scored calls; 95 changeable-condition calls excluded (wet/drying races the v1 simulator cannot model). Stats: Mann-Whitney U, two-sided, Holm-corrected across models.

## Per-season delta_exante  (mean / median, n)

| Model | 2024 | 2025 | 2026 | pre-2026 (24-25) | gap (pre − 2026) |
|---|---|---|---|---|---|
| claude-haiku-4.5 | 28.336 / 4.176 (n=34) | 9.756 / 3.691 (n=18) | 8.809 / 0.0 (n=125) | 21.905 / 3.691 (n=52) | 13.096 |
| claude-opus-4.8 | 2.661 / 0.0 (n=34) | 3.156 / 3.024 (n=18) | 9.211 / 0.0 (n=125) | 2.832 / 0.961 (n=52) | -6.379 |
| deepseek-v3.2 | 1.35 / 0.0 (n=34) | 9.756 / 3.691 (n=18) | 4.934 / 0.0 (n=125) | 4.26 / 0.824 (n=52) | -0.674 |
| gemini-3.1-pro | 5.332 / 1.901 (n=34) | 3.527 / 3.146 (n=17) | 8.077 / 0.0 (n=125) | 4.73 / 2.987 (n=51) | -3.347 |
| gpt-5.5 | 12.964 / 3.612 (n=34) | 3.331 / 3.104 (n=18) | 8.076 / 0.0 (n=124) | 9.629 / 3.104 (n=52) | 1.553 |

## H3 test — pre-2026 vs 2026  (Mann-Whitney U, two-sided)

Negative gap = better (lower delta) on pre-2026 races = possible recall signal.

| Model | gap (pre − 2026, s) | raw p | Holm p | verdict @0.05 |
|---|---|---|---|---|
| claude-haiku-4.5 | 13.096 | 0.0001 | 0.0005 | worse on pre-2026 |
| gpt-5.5 | 1.553 | 0.0029 | 0.0115 | worse on pre-2026 |
| deepseek-v3.2 | -0.674 | 0.0038 | 0.0115 | **recall signal** (better on pre-2026) |
| gemini-3.1-pro | -3.347 | 0.0148 | 0.0296 | **recall signal** (better on pre-2026) |
| claude-opus-4.8 | -6.379 | 0.3377 | 0.3377 | no significant gap |

**Does the earlier 'worse on pre-2026' signal survive on the dry subset?** Recall signal (significantly better on pre-2026) in: deepseek-v3.2, gemini-3.1-pro.

## Monaco same-track  (2024 / 2025 / 2026 GP — constant circuit)

Mean delta_exante on the Monaco Grand Prix across three seasons. The track is held
constant, so a pre-2026 advantage here is a particularly clean contamination signal.

| Model | 2024-monaco | 2025-monaco | 2026-monaco |
|---|---|---|---|
| claude-haiku-4.5 | 49.154 (n=16) | 9.756 (n=18) | 3.788 (n=18) |
| claude-opus-4.8 | 2.766 (n=16) | 3.156 (n=18) | 2.8 (n=18) |
| deepseek-v3.2 | 2.766 (n=16) | 9.756 (n=18) | 4.169 (n=18) |
| gemini-3.1-pro | 5.528 (n=16) | 3.527 (n=17) | 4.867 (n=18) |
| gpt-5.5 | 14.006 (n=16) | 3.331 (n=18) | 0.716 (n=18) |

Models: 5 | valid scored calls: 883
