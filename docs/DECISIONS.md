# DECISIONS.md — assumptions, thresholds, judgment calls

Every entry: **what** was decided, **why**, one line each. Newest at the bottom.

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Mock mode all night; no paid API calls | No OPENROUTER_API_KEY and no ALLOW_SPEND=1 in env → §2 rule forbids spend; smoke test (P6) skipped. |
| 2 | Decision point at lap t uses info through end of lap t−1, plus current track status during lap t | The pit call for lap t happens before lap t completes; including lap t's own time would leak the in-lap. Track status is real-time knowledge (race control announces SC instantly). |
| 3 | Monaco 2025 chosen as the P0 known-good validation race | Brief offered Bahrain 2025 or Monaco 2025; Monaco doubles as a structural rehearsal for the Monaco 2026 replay target. |
| 4 | Race lists live in config/extraction.yaml | Brief fixes the config file set; extraction config is where the dataset definition naturally sits. |
| 5 | "Compounds available" = all three dry compounds (or inters/wets if rain) | Real remaining-set data isn't in timing feeds; assuming full availability is uniform across all models so it cannot bias the comparison. |
| 6 | Gap to car ahead/behind = session-time difference at lap completion | Standard interval approximation; accurate to ~0.5s, uniform across all decision points. |
| 7 | Lapped-car detection: gap to leader at end of lap t−1 > the leader's lap t−1 time | Leak-free (uses only laps ≤ t−1) and equivalent to "leader will catch the car within a lap"; borderline cases are rare and excluded conservatively. |
| 8 | Mock model emits ~4% deliberately malformed outputs | Exercises the invalid-output path end-to-end so the leaderboard's invalid-rate column is nonzero in mock runs (config: run.yaml mock_invalid_rate). |
| 9 | repeats=3 in run.yaml for mock runs | Makes the consistency flip-rate metric measurable tonight; real-run repeat count is Anas's call. |
| 10 | Candidate strategies = exactly one further stop at any lap from t to (total_laps − last_laps_exclusion), each available compound, plus no-stop when legal | One-more-stop covers the vast majority of real dry-race situations from mid-race; full multi-stop search is v2. Documented in LIMITATIONS.md. |
| 11 | Scoring "agreement with team" uses the action only (PIT/STAY), compound agreement reported separately | A model can be right to pit but reasonably differ on compound; conflating them hides signal. |
| 12 | SC lap times in rollout = field-median actual lap time on that lap | Everyone circulates at delta under SC; the focal car's compound barely matters. Uses hindsight SC timeline, which is fine because the simulator is explicitly a hindsight-optimal oracle. |
| 13 | Clean-lap filter does NOT require FastF1 IsAccurate | Several 2026 sessions mark entire drivers inaccurate (accuracy-check failure); the >3-MAD residual filter removes the bad laps anyway. |
| 14 | Degradation predictions clamped: tyre age capped at max clean age observed on that compound; lap time floored at the race's fastest clean lap | Linear fits extrapolate absurdly outside the data (negative deg at Monaco predicted 26s laps); both clamps are physical bounds. |
| 15 | sim(STAY) = best legal plan that does not stop this lap; team's STAY valued identically | STAY is not a complete strategy; charitable best-deferred-plan valuation, applied equally to model and team, makes agreement score as an exact tie. |
| 16 | Unseen-compound fallback: slowest field fit + 1.0s/lap | A model may pick a compound nobody ran cleanly; the sim must return something finite, and it should not look attractive. |
| 17 | Type A restricted to classified cars per spec; Type C triggers off any car's stop but the threatened focal must pass all excludes | Literal reading of section 6. |
| 18 | Laps with rainfall during their time window are excluded from fits and neutralized (field-median) in rollouts when >30% of cars affected | Slicks-on-damp laps destroyed Miami 2026 fits; rain phases are strategy-neutralized the same way SC laps are. |
| 19 | When a (driver, compound)'s clean laps span a single stint, the fuel term c is dropped from the fit | tyre_age and lap_number are collinear there; the 3-param fit is unidentifiable and produced ~0s lap predictions. |
| 20 | Replay end condition = last lap end + 120s race-time buffer; ReplaySource owns sleep() so the loop never knows time is scaled | Keeps the "loop must not know it's a replay" property intact. |
| 21 | Mock cache ids are "mock/<model-name>" | A shared "mock" id collided across models in the cache; ids must be unique per (model, dp, prompt, temp, repeat). |
| 22 | outputs/leaderboard.json is copied to site/leaderboard.json after scoring | Lets site/index.html work from file:// and GitHub Pages without exposing the gitignored outputs/ tree. |
| 23 | pyproject.toml added (not in the §4 file list) with `-e .` in requirements.txt | `python -m boxbox.live.replay` and pytest imports require the package installed; this keeps the §12 fresh-clone command sequence working verbatim. |
| 24 | Invalid model outputs are excluded from delta means and reported as their own leaderboard column | Penalizing invalids with a fake worst-case delta would distort the time-loss metric; visibility comes from the invalid-rate column. |
| 25 | verify_models.py ran tonight (free GET): all six models resolved and enabled; gemini-3.1-pro maps to google/gemini-3.1-pro-preview | The only listing match for that model; flagged here so Anas can confirm the preview id is the intended target. |
