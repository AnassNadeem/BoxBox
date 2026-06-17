# BOXBOX — Claude Fable 5 head-to-head (exploratory, n = 3)

> **Exploratory, n = 3 — not part of the main leaderboard.** Claude Fable 5 was suspended by a US export-control directive on 2026-06-12 (prereg-v2) after answering only these three decision points in the 2026-06-12 connectivity smoke test (temperature 0, single-shot). Its calls are the **cached smoke-v2 responses**, scored with the *same* simulator/oracle as the other five models; no Fable API calls were made (the model is unavailable). The other five models are from the main benchmark run (`outputs/scores.jsonl`). Three DPs, one sample each, not balanced across types or races — read as anecdote, not ranking.

Δ ex-ante = simulated time lost vs the ex-ante optimal (s; lower is better). 'Agrees w/ team' = same PIT/STAY as the real team's call (✓exact = compound also matches).

## 2026-australia-L007-COL-A

Type A · 2026-australia · lap 7/58 · driver COL. Real team call: **STAY**. Ex-ante optimal: **PIT MEDIUM** (stop lap 7).

| Model | Action | Compound | Δ ex-ante (s) | Agrees w/ team |
|---|---|---|---:|---|
| claude-opus-4.8 | STAY | — | 1.60 | ✓ exact |
| gpt-5.5 | STAY | — | 1.60 | ✓ exact |
| gemini-3.1-pro | STAY | — | 1.60 | ✓ exact |
| deepseek-v3.2 | STAY | — | 1.60 | ✓ exact |
| claude-haiku-4.5 | STAY | — | 1.60 | ✓ exact |
| claude-fable-5 † | STAY | — | 1.60 | ✓ exact |

Fable rationale: *COL is on fresh-ish hards with 50+ laps left; pitting now wastes the offset. Rivals ahead/behind on softs must stop soon, giving free track position. Extend stint, target one-stop switching to medium or soft later.*

## 2026-china-L010-ANT-B

Type B · 2026-china · lap 10/56 · driver ANT. Real team call: **PIT HARD**. Ex-ante optimal: **STAY** (optimal plan defers the stop to ~lap 55).

| Model | Action | Compound | Δ ex-ante (s) | Agrees w/ team |
|---|---|---|---:|---|
| gemini-3.1-pro | STAY | — | 0.00 | — |
| deepseek-v3.2 | STAY | — | 0.00 | — |
| claude-haiku-4.5 | STAY | — | 0.00 | — |
| claude-opus-4.8 | PIT | HARD | 23.34 | ✓ exact |
| gpt-5.5 | PIT | HARD | 23.34 | ✓ exact |
| claude-fable-5 † | PIT | HARD | 23.34 | ✓ exact |

Fable rationale: *Safety car offers a cheap stop at half the normal time loss. Boxing from the lead onto hards converts to a one-stop; cool track (22.6C) supports a 46-lap hard stint. Staying out risks losing position if rivals behind take the free stop.*

## 2026-japan-L018-ANT-C

Type C · 2026-japan · lap 18/53 · driver ANT. Real team call: **STAY**. Ex-ante optimal: **PIT HARD** (stop lap 18).

| Model | Action | Compound | Δ ex-ante (s) | Agrees w/ team |
|---|---|---|---:|---|
| gemini-3.1-pro | PIT | HARD | 0.00 | — |
| claude-fable-5 † | PIT | HARD | 0.00 | — |
| claude-opus-4.8 | STAY | — | 1.56 | ✓ exact |
| gpt-5.5 | STAY | — | 1.56 | ✓ exact |
| deepseek-v3.2 | STAY | — | 1.56 | ✓ exact |
| claude-haiku-4.5 | STAY | — | 1.56 | ✓ exact |

Fable rationale: *HAM at 1.9s is a live undercut threat on equal-age mediums; pitting first protects P3. Hard covers the remaining 35 laps in cool conditions. NOR's stop confirms the window is open; rejoining near him is acceptable versus losing position to an undercut.*

† Claude Fable 5 — cached smoke-v2 call (pre-suspension); exploratory, not in the leaderboard.
