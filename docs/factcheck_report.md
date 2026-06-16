# BOXBOX paper draft — fact-check & gap report

Verification of `paper/boxbox_draft.md` against the committed artifacts, done read-only on
2026-06-16. **No prose was changed in the draft.** Sources used: `outputs/leaderboard.json`,
`outputs/scores.jsonl` (890 rows), `outputs/contamination.md`, `docs/hypothesis_tests.md`,
`docs/paper_data.md`, `outputs/fable_comparison.md`, `data/decision_points/manifest.json`,
`config/models.yaml`, and `src/boxbox/` (scoring + calibration recomputed independently).

Verdict legend: **MATCH** = draft equals artifact · **MISMATCH** = draft differs ·
**INCOMPLETE** = placeholder/dash to fill · **FLAG** = correct under one reading but
inconsistent with another part of the draft, or an overstatement.

---

## PART 1 — Numeric fact-check (report only)

### Abstract

| # | Claim (location) | Claimed | Artifact | Verdict |
|---|---|---|---|---|
| 1 | "ten races we extract 178 decision points" | 178 | 178 full set | **MATCH** |
| 2 | "beating the real team call on at most a quarter of decisions" | ≤25% | all-seasons max 22.2% (Opus); **2026-only max 25.5% (Opus)** | **FLAG** — true on all-seasons; on the 2026 primary set Opus is 25.5%, just over a quarter. See Inconsistency A. |
| 3 | cheapest model "priced roughly two orders of magnitude below the flagships" | ~100× | DeepSeek $0.2288/$0.3432 vs GPT $5/$30, Opus $5/$25 → output 73–87×, input ~22×, blended ~50–60× | **MATCH (approx)** — "roughly two orders" is defensible for output tokens (~73–87×); blended is ~1.7 orders. |
| 4 | most-accurate model reverses "roughly two in five times" (DeepSeek) | ~40% | flip 38.9% | **MATCH** |
| 5 | "one flagship reverses itself on more than half" (GPT-5.5) | >50% | flip 55.6% | **MATCH** |

### §3.1 Data

| # | Claim | Claimed | Artifact | Verdict |
|---|---|---|---|---|
| 6 | ten races | 10 | 10 | **MATCH** |
| 7 | six 2026 primary | 6 | 6 (AUS/CHN/JPN/MIA/CAN/MON) | **MATCH** |
| 8 | four 2024–25 control | 4 | 4 | **MATCH** |
| 9 | 178 decision points total | 178 | 178 | **MATCH** |
| 10 | 159 remain after exclusions | 159 | 159 dry | **MATCH** |
| 11 | 107 primary / 52 control | 107 / 52 | 107 / 52 (computed from scores.jsonl) | **MATCH** |
| 12 | **Table 1** all per-race rows (laps, A/B/C, totals, excluded) | see draft | identical to manifest `dp_type_counts`/`total_laps` | **MATCH** (every cell verified) |
| 13 | 2024 Monaco yields 16 points | 16 | 16 | **MATCH** |

- Table 1 note: the draft writes "Monte Carlo" for all three Monaco rows; the manifest `track`
  field is "Monaco" for 2024/2025 and "Monte Carlo" for 2026. Cosmetic ingestion-source
  naming, **not** a numeric mismatch.

### §3.4 Models & prompting

| # | Claim | Claimed | Artifact | Verdict |
|---|---|---|---|---|
| 14 | five models evaluated | 5 | 5 in `models.yaml` | **MATCH** |
| 15 | model identities (Opus 4.8, GPT-5.5, Gemini 3.1 Pro, DeepSeek V3.2, Haiku 4.5) | — | matches `models.yaml` | **MATCH** |
| 16 | Fable 5 answered three DPs | 3 | 3 (fable_comparison.md) | **MATCH** |
| 17 | probe = 20 DPs × 5 samples | 20 / 5 | `run.yaml`: 20 select, 5 samples | **MATCH** |

### §4.1 Simulator calibration

| # | Claim | Claimed | Artifact | Verdict |
|---|---|---|---|---|
| 18 | "median absolute error of 0.09 s/lap, mean 0.22 s/lap" | 0.09 / 0.22 | **per-stint** median 0.0900, mean 0.2224 (445 stints; independently recomputed via `calibration_records`) | **MATCH** |
| 19 | "single worst case is one such stint" (thin first stint) | — | max per-stint MAE 8.257 (Miami BOT MEDIUM, n=4) | **MATCH** |

- The 0.09/0.22 pair is the **per-stint** aggregation. The **per-race** aggregation is
  mean 0.222 / median 0.191 (also verified from the manifest). The draft's pairing is
  internally consistent (both per-stint); just don't mix it with the per-race median (0.191).

### §4.2 Table 2 — per-model performance on the 2026 primary set (107 DP)

| # | Cell | Claimed (draft) | Artifact (2026-only dry, 107 DP) | Verdict |
|---|---|---|---|---|
| 20 | Mean Δ (all 5) | 5.81 / 8.32 / 8.64 / 9.00 / 9.23 | 5.809 / 8.321 / 8.635 / 8.996 / 9.232 | **MATCH** |
| 21 | 95% CIs (all 5) | see draft | identical to H1 Set A | **MATCH** |
| 22 | Median Δ | dashes (only DeepSeek 0.0) | **all 0.0** | **INCOMPLETE** → filled in Part 2 |
| 23 | Beat-team % | 18 / 17 / 20 / 18 / 22 | **19.6 / 18.7 / 22.4 / 20.6 / 25.5** | **MISMATCH** — draft used all-seasons rates (the `[DECISION]` note admits this) |
| 24 | Agree-team % | 73 / 64 / 60 / 59 / 59 | **69.2 / 63.6 / 54.2 / 55.1 / 49.1** | **MISMATCH** — all-seasons rates |
| 25 | Invalid % | 0 / 0 / 1 / 0 / 1 | **0 / 0 / 0.0 / 0 / 0.9** | **MISMATCH** — Gemini's lone invalid is in *pre-2026*, so Gemini = 0.0% on the 2026 set; Opus = 0.9% (not 1%) |
| 26 | "means range 5.8 → 9.2 s" | 5.8–9.2 | 5.809–9.232 | **MATCH** |
| 27 | full dry set (159): DeepSeek lowest, flagships don't lead | — | DeepSeek 5.303 #1; Opus #2 | **MATCH** |
| 28 | Opus "notably better on pre-2026" | — | Opus 2024 = 2.661 vs 2026 = 9.232 | **MATCH** |

*(Mapping for rows 23–25, draft order DeepSeek/Haiku/Gemini/GPT/Opus.)*

### §4.3 Comparison with human strategists

| # | Claim | Claimed | Artifact | Verdict |
|---|---|---|---|---|
| 29 | "No model beats the human pit wall more than a quarter of the time" | ≤25% | 2026-only Opus 25.5% (>¼); all-seasons 22.2% | **FLAG** — see Inconsistency A |
| 30 | "beat-team rate ranges from 17 to 22 percent" | 17–22% | **all-seasons** 17.0–22.2%; **2026-only 18.7–25.5%** | **MISMATCH vs Table 2's set** — 17–22% is the all-seasons range, but §4.3 sits right after the 107-DP Table 2. See Inconsistency A |
| 31 | binomial "p below 0.000001" for every model | <1e-6 | 2026-only largest p = 4.328e-07 (Opus) < 1e-6; all-seasons all < 1e-12 | **MATCH** |

### §4.4 Consistency

| # | Claim | Claimed | Artifact | Verdict |
|---|---|---|---|---|
| 32 | Haiku 0%, Opus small, GPT >half, DeepSeek ~2/5 | 0 / ~5.6 / >50 / ~40 | flip 0.0 / 5.6 / 55.6 / 38.9 | **MATCH** |
| 33 | "Opus … comes closest … low flip rate with a competitive mean delta" | — | Opus flip 5.6% (2nd-lowest) ✓; mean Δ **9.232 = highest of 5 on the 2026 set** | **FLAG** — "competitive mean delta" holds on the all-seasons set (Opus #2 = 7.126) but **not** on the 2026 set used for Table 2/Figure 3, where Opus is last. See Inconsistency A |
| 34 | "GPT-5.5 … both less accurate and the least consistent" | — | GPT mean 8.996 (4th/5), flip 55.6% (highest) | **MATCH** |

### §4.5 Contamination — Table 3

| # | Row | Claimed (pre / 2026 / gap / verdict) | Artifact (contamination.md) | Verdict |
|---|---|---|---|---|
| 35 | DeepSeek | 4.26 / 5.81 / −1.55 / no sig | 4.26 / 5.809 / −1.549 / Holm 0.0669 | **MATCH** |
| 36 | GPT-5.5 | 9.63 / 9.00 / +0.63 / no sig | 9.629 / 8.996 / +0.633 / Holm 0.0669 | **MATCH** |
| 37 | Gemini | 4.73 / 8.64 / −3.91 / no sig | 4.73 / 8.635 / −3.905 / Holm 0.1185 | **MATCH** |
| 38 | Opus | 2.83 / 9.23 / −6.40 / no sig | 2.832 / 9.232 / −6.4 / Holm 0.613 | **MATCH** |
| 39 | Haiku | 21.91 / 8.32 / +13.58 / worse pre-2026 | 21.905 / 8.321 / +13.584 / Holm 0.0008 | **MATCH** |
| 40 | "only significant difference … opposite direction" (Haiku worse on old) | — | Haiku Holm p 0.0008, +gap | **MATCH** |
| 41 | Opus negative gap "does not reach significance after correction" | — | Opus Holm p 0.613 | **MATCH** |
| 42 | Monaco within-circuit: "most models record their best Monaco performance in 2026" | most | **only 2 of 5** strictly best in 2026 (Haiku, GPT) | **FLAG / overstatement** — see Inconsistency B |

### §4.6 Fable 5 (n=3)

| # | Claim | Artifact (fable_comparison.md) | Verdict |
|---|---|---|---|
| 43 | "three decision points" | 3 | **MATCH** |
| 44 | "matched the field on one" | DP1 AUS-L007: all 6 STAY, Δ 1.60 | **MATCH** |
| 45 | "same suboptimal SC stop as two flagships on another" | DP2 CHN-L010: Fable PIT HARD Δ 23.34 = Opus + GPT-5.5 | **MATCH** |
| 46 | "reached the ex-ante optimum on the third alongside one other model" | DP3 JPN-L018: Fable PIT HARD Δ 0.00 = Gemini | **MATCH** |

### §5 / Appendix / Reproducibility

| # | Claim | Claimed | Artifact | Verdict |
|---|---|---|---|---|
| 47 | "losing to the real pit wall on roughly four decisions in five" | ~80% | beat ≈17–25% → lose ≈75–83% | **MATCH** |
| 48 | "total … cost of approximately twelve United States dollars" / "~$12.50 benchmark" | ~$12.50 | $12.4986 benchmark total | **MATCH** |
| 49 | Appendix E `[DECISION]` cites 52 tests at benchmark commit | 52 | paper_data §11: 52 at benchmark commit, 61 now | **MATCH** (note in draft is a placeholder, not body text) |

**Part 1 bottom line:** every *confirmed* number in the draft matches its artifact. The only
hard **MISMATCH**es are the three Table 2 rate columns (rows 23–25), which the draft's own
`[DECISION]` flags as all-seasons placeholders — corrected in Part 2. Everything else is
MATCH except four **FLAG**s that all stem from one root cause (Inconsistency A, below).

---

## PART 2 — Table 2, computed exactly from `scores.jsonl` (2026-only dry, 107 DP)

Read-only, no spend. Methodology replicates `src/boxbox/score/leaderboard.py` exactly:
valid = `not invalid and delta_exante_s is not None`; beat/agree % over **valid** calls;
invalid % over **all** calls; median over valid `delta_exante_s`. Filter: `season == 2026 and
changeable_conditions == false` → 107 DP. Ordered by ascending mean Δ.

| Model | Mean Δ (s) | 95% CI | Median Δ (s) | Beat team | Agree team | Invalid | n valid |
|---|---:|---|---:|---:|---:|---:|---:|
| DeepSeek V3.2 | 5.81 | [2.11, 10.72] | **0.0** | **19.6%** | **69.2%** | **0.0%** | 107 |
| Claude Haiku 4.5 | 8.32 | [4.94, 12.06] | **0.0** | **18.7%** | **63.6%** | **0.0%** | 107 |
| Gemini 3.1 Pro | 8.64 | [5.42, 12.34] | **0.0** | **22.4%** | **54.2%** | **0.0%** | 107 |
| GPT-5.5 | 9.00 | [5.80, 12.66] | **0.0** | **20.6%** | **55.1%** | **0.0%** | 107 |
| Claude Opus 4.8 | 9.23 | [5.97, 12.86] | **0.0** | **25.5%** | **49.1%** | **0.9%** | 106 |

Exact fractions (for prose/footnotes): beat-team k/n — Opus 27/106, Gemini 24/107,
GPT 22/107, DeepSeek 21/107, Haiku 20/107. Opus has the single invalid call on the 2026 set
(1/107 = 0.9%); all other models are 0% invalid in 2026. Mean Δ and CIs are unchanged from
the draft (they were already 2026-only, confirmed against H1 Set A).

**What changes vs the draft's Table 2:** all five medians are 0.0 (fills the dashes); the
beat/agree/invalid columns shift to the values above (the draft's were all-seasons). Note the
2026-only beat-team range becomes **18.7%–25.5%** (not 17–22%), and agree-team drops markedly
for Gemini/GPT/Opus (the 2026 races are harder to agree with the team on than the 2024–25
ones).

---

## PART 3 — Figures

### (a) Figure 3 — accuracy-vs-consistency scatter — GENERATED ✅
- **Path:** `outputs/figures/accuracy_vs_consistency.png`
- x = mean ex-ante Δ on the 2026 primary set (DeepSeek 5.81 → Opus 9.23); y = flip rate
  (Haiku 0% → GPT 55.6%); 5 labelled points; lower-left "accurate & consistent" region shaded.
  Renders: DeepSeek far left (most accurate, high flip), Haiku at the floor (most consistent),
  Opus low-flip/high-Δ, GPT top-right (worst on both), Gemini mid. No model sits in the ideal
  region — matches the §4.4 narrative.
- Reproducibility note: generated by a standalone matplotlib script (F1 palette matching
  `analysis/figures.py`), **not** folded into `analysis/figures.py` per the "commit only the
  figure + 2 docs" constraint. Say the word and I'll add a `fig_accuracy_vs_consistency()`
  function so it regenerates with `python analysis/figures.py`.

### (b) Pre-existing figures to embed — CONFIRMED ✅
- **Leaderboard bar:** `outputs/figures/leaderboard_bar.png` (exists; "BOXBOX leaderboard (real
  data)", mean Δexante per model, ex-ante vs hindsight bars). ⚠️ It plots the **all-seasons
  159-DP** means (DeepSeek 5.3, Opus 7.1, Gemini 7.4, GPT 9.2, Haiku 12.8), **not** the 2026
  primary set. If the paper's headline is the 107-DP set, this figure ranks Opus #2 where
  Table 2 ranks it #5 — embed with a caption that says "all-seasons dry set" or regenerate
  for 2026-only.
- **Calibration scatter:** `outputs/calibration/{race}.png` — all 10 present
  (2024-bahrain, 2024-monaco, 2025-monaco, 2025-silverstone, 2026-australia, 2026-canada,
  2026-china, 2026-japan, 2026-miami, 2026-monaco), each predicted-vs-actual stint time.
  Figure 2 in the draft refers to "calibration"; there is **no single combined** calibration
  scatter — it's one PNG per race. Pick a representative race or make a combined panel.

### Not done (per instructions)
- Figure 1 decision-point schematic — intentionally left to you ("I'll handle that
  conceptually"). No per-type figure was generated (not requested).

---

## PART 5 — Gap report (report only)

### `[DECISION]` markers left open in the draft
1. **Author line** (top) — name/affiliation/email placeholder. Not verifiable from the repo.
2. **§2 Related work** — six `[CITE]` slots. → filled in `docs/citations_found.md`.
3. **Table 2 `[DECISION]`** — per-model median + 2026-only rate columns. → filled in Part 2.
4. **Appendix `[DECISION]`** — appendices A–E to assemble (prompt, prereg trail, full-set
   leaderboard, per-type table, reproducibility). All source numbers exist in
   `paper_data.md`; this is assembly, not new analysis.
5. **Reproducibility statement / Appendix E** — "52 tests" and "~$12.50" both confirmed
   (Part 1 rows 48–49); just needs to move from `[DECISION]` into final text.

### Internal inconsistencies (decide, don't auto-fix)

**Inconsistency A — the headline-set ambiguity (root cause of FLAGs 2, 29, 30, 33).**
Table 2 is the **2026-only** 107-DP set (its means/CIs are 2026-only), but several prose
claims around it quote **all-seasons** 159-DP numbers:
- "at most a quarter" (abstract) and "ranges from 17 to 22 percent" (§4.3) are all-seasons;
  on the 2026 set the beat range is **18.7–25.5%** and Opus exceeds a quarter (25.5%).
- "Opus … competitive mean delta" (§4.4) is true all-seasons (Opus #2) but false on the
  2026 set (Opus #5, highest Δ) — and Figure 3 uses the 2026 set, so the figure shows Opus
  as the *least* accurate of the five, which sits awkwardly with "competitive."
- `paper_data.md` §8c and the open-items list both flag this exact "two headlines" problem.
  **Recommendation:** pick one headline set and make the abstract, Table 2, §4.3 range, and
  §4.4 Opus characterisation all consistent with it. If 2026-only stays the headline, update
  "at most a quarter" → "about a quarter / up to 26%", "17 to 22 percent" → "19 to 26 percent",
  and soften "competitive mean delta" for Opus.

**Inconsistency B — Monaco "most models best in 2026" (FLAG 42).**
Draft §4.5: "most models record their best Monaco performance in 2026." Actual per-model best
Monaco season (mean Δexante): Haiku → 2026 (3.788) ✓; GPT → 2026 (0.716) ✓; Opus → 2024
(2.766, vs 2026 2.8 — essentially tied); DeepSeek → 2024 (2.766); Gemini → 2025 (3.527).
So **2 of 5** are strictly best in 2026, not "most." The defensible claim is the weaker one
the artifact actually supports: *no model shows a pre-2026 advantage at Monaco / no recall
signal.* Recommend rewording to that.

### Claims with no backing repo artifact (external facts, not errors)
- **"open-weight model"** (DeepSeek, abstract/§4.2/§5) — a property of the model, not in any
  repo artifact. True in general, but unverifiable here; make sure you're comfortable
  asserting it.
- **"post-date the training cutoff of every model under test"** (§3.1 and throughout) — the
  contamination framing's premise. Not directly checkable from artifacts (depends on each
  vendor's cutoff); the §4.5 analysis supports it indirectly but does not prove the cutoffs.
- **Fable 5 export-control directive / HTTP 404** (§3.6) — backed by
  `outputs/fable_unavailable_check.md` and the prereg-v2 note in `paper_data.md` §10, but the
  underlying "government directive" is a project-recorded event, not an independent source.

### Figures referenced but not embedded
- **Figure 1** (decision-point schematic) — does not exist; you're handling it.
- **Figure 2** (calibration) — exists only as 10 per-race PNGs, no combined scatter (see Part 3b).
- **Figure 3** (accuracy-vs-consistency) — now generated (Part 3a).
- **Leaderboard bar** is referenced for the appendix and shows all-seasons means — caption
  carefully (Part 3b).

### Minor
- Table 1 "Monte Carlo" vs manifest "Monaco" for 2024/25 — cosmetic only.
- The draft's $ figure says "approximately twelve dollars" in the reproducibility statement
  and "~$12.50 benchmark" in the appendix `[DECISION]`; both round $12.4986 — consistent, just
  keep one phrasing.

---

*Nothing in `paper/boxbox_draft.md` was modified. Deliverables committed: this report,
`docs/citations_found.md`, and `outputs/figures/accuracy_vs_consistency.png`.*
