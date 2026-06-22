# BOXBOX

**Can frontier LLMs call an F1 race?**

BOXBOX is a contamination-resistant benchmark that tests whether large language models can make Formula 1 pit-stop strategy decisions. We reconstruct *decision points* from real 2026 races — *pit now or stay out? which compound?* — feed the identical frozen race state to five frontier models, and score every call against an ex-ante optimal strategy computed by a calibrated race simulator.

Because every completed 2026 race postdates all models' training data, the 2026 test set is **designed to resist contamination by construction**. A direct test against a 2024/2025 control set finds a weak, inconsistent signal rather than a clean null — see Section 4.5 of the paper. Contamination resistance is a matter of degree, not a guarantee.

[![Contamination Check](https://github.com/AnassNadeem/BoxBox/raw/main/outputs/figures/season_gap.png)](outputs/figures/season_gap.png)

A sixth model, Claude Fable 5, was in the original design but became unavailable due to a US export-control directive before the main run. It answered 3 decision points during connectivity testing; these are reported as an exploratory observation in the paper (Section 4.6), not on the leaderboard.

---

## Results — primary 2026 set (125 dry decision points · 7 races · 5 models)

[![Leaderboard bar chart](https://github.com/AnassNadeem/BoxBox/raw/main/outputs/figures/leaderboard_bar.png)](outputs/figures/leaderboard_bar.png)

| # | Model | Mean Δ (s) ↓ | 95% CI | Beat team % | Flip rate % |
|---|---|---|---|---|---|
| 1 | DeepSeek V3.2 | **4.93** | [1.55, 9.26] | 19.2% | 38.9% |
| 2 | GPT-5.5 | 8.08 | [5.16, 11.36] | 19.4% | 50.0% |
| 2 | Gemini 3.1 Pro | 8.08 | [4.95, 11.50] | 20.0% | 22.2% |
| 4 | Claude Haiku 4.5 | 8.81 | [5.53, 12.43] | 16.0% | 0.0% |
| 5 | Claude Opus 4.8 | 9.21 | [5.87, 12.87] | 24.0% | 5.6% |

*Lower mean Δ is better. Confidence intervals from 10,000-sample bootstrap. Confidence intervals for positions 2–5 overlap substantially — the middle four models are broadly indistinguishable.*

**Three headline findings:**

- **All models lose to the human pit wall.** Beat-team rate is 16–24% across the board (binomial p < 1e-8 for each). Caveat: real teams had telemetry, tyre sensors, and radio the models did not — this is a text agent vs a fully-resourced team.
- **Price does not predict quality.** DeepSeek V3.2 (open-weight, ~100x cheaper than the flagships) achieves the lowest mean error. The confidence intervals overlap, so the honest claim is: paying more bought no measurable improvement.
- **Accuracy ≠ consistency.** The most accurate model reverses its own call ~40% of the time on identical repeated inputs. GPT-5.5 flips on half. Claude Haiku never flips but is least accurate. These are distinct, weakly-correlated properties that must be measured separately.

[![Accuracy vs Consistency](https://github.com/AnassNadeem/BoxBox/raw/main/outputs/figures/accuracy_vs_consistency.png)](outputs/figures/accuracy_vs_consistency.png)

### Robustness check — full set (177 dry decision points · all 11 races)

| # | Model | Mean Δ (s) ↓ | Beat team % | Flip rate % |
|---|---|---|---|---|
| 1 | DeepSeek V3.2 | **4.74** | 18.1% | 38.9% |
| 2 | Gemini 3.1 Pro | 7.11 | 18.2% | 22.2% |
| 3 | Claude Opus 4.8 | 7.34 | 21.5% | 5.6% |
| 4 | GPT-5.5 | 8.54 | 17.6% | 50.0% |
| 5 | Claude Haiku 4.5 | 12.66 | 15.3% | 0.0% |

*The reordering between sets is consistent with overlapping confidence intervals — positions 2–5 should not be treated as a strict ranking.*

---

## Races

| Set | Races | Dry decision points |
|---|---|---|
| **2026 primary (post-cutoff)** | Australia, China, Japan, Miami, Canada, Monaco, Barcelona-Catalunya | 125 |
| **2024/25 control** | Bahrain 2024, Monaco 2024, Monaco 2025, Silverstone 2025 | 52 (+ 18 excluded wet) |
| **Total** | 11 races | 177 dry / 196 total |

---

## Quick start

```bash
pip install -r requirements.txt
pytest                                    # 61 tests, all green
python scripts/build_dataset.py           # ingest → extract → data/decision_points/
python scripts/run_benchmark.py --mock    # mock mode: $0, fully deterministic
python scripts/score_results.py           # scores → outputs/leaderboard.{md,csv,json}
```

Real model runs require `.env` with `OPENROUTER_API_KEY` and `ALLOW_SPEND=1` (see `.env.example`).

```bash
python scripts/run_benchmark.py           # live run (~$13 for 5 models × 177 DPs)
python scripts/run_consistency_probe.py   # 5 reruns on top-disagreement DPs
python analysis/figures.py                # regenerate all paper figures
```

---

## How it works

| Step | Component | What it does |
|---|---|---|
| 1 | **Ingest** `boxbox.data` | FastF1 (OpenF1 fallback) → normalised `RaceData` |
| 2 | **Extract** `boxbox.extract` | Rule-based Type A/B/C decision points. State at lap *t* contains zero information from after lap *t*. Leakage tested by automated assertion. |
| 3 | **Simulate** `boxbox.sim` | Per-car tyre-degradation fits + pit-loss estimates → ex-ante optimum (no future SC knowledge) |
| 4 | **Harness** `boxbox.harness` | Identical prompts to every model via OpenRouter, strict JSON answers, SHA-256 disk cache, cost ledger, mock mode |
| 5 | **Score** `boxbox.score` | `Δ_exante = sim(model action) − sim(ex-ante optimal)` → beat-team rate, flip rate, invalid rate → leaderboard |

---

## Pre-registration

Before running any model on the full dataset, the design, hypotheses, and analysis plan were written down and committed to this repository with a timestamp, so the results could not shape the analysis after the fact.

The full procedure is in `docs/PREREGISTRATION.md`; amendments are in `docs/DECISIONS.md`. The trail is anchored to git tags — each is a distinct, separately timestamped commit verifiable by hash:

```bash
git show prereg-v1 --no-patch --format="%H %ai %s"
git show prereg-v4 --no-patch --format="%H %ai %s"
```

---

## Outputs

| File | Description |
|---|---|
| `outputs/leaderboard.json` | Leaderboard (primary source of truth) |
| `outputs/scores.jsonl` | Per-call scored results |
| `outputs/hypothesis_tests.md` | H1/H2/H3 statistical test results |
| `outputs/contamination.md` | Per-model contamination analysis |
| `outputs/cost_ledger.csv` | Per-call token and cost tracking |
| `outputs/figures/` | All paper figures (PNG) |

---

## Paper

Full manuscript: [`paper/boxbox_final_complete.md`](paper/boxbox_final_complete.md)

---

## Cost

Total model-inference spend: **~$13.46** across the main pass, consistency probe, and re-runs. Preregistered spend cap of $20 was never reached.

---

## Author

**Muhammad Anas Nadeem**  
Department of Computer Science, Brunel University London  
[anass.nadeem42@gmail.com](mailto:anass.nadeem42@gmail.com) · [LinkedIn](https://www.linkedin.com/in/anass-nadeem/)
