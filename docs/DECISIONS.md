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
| 7 | Lapped-car detection: focal cum. race time through lap t−1 > leader's through lap t | Pure lap-data criterion, no extra API needed; borderline cases are rare and excluded conservatively. |
| 8 | Mock model emits ~4% deliberately malformed outputs | Exercises the invalid-output path end-to-end so the leaderboard's invalid-rate column is nonzero in mock runs (config: run.yaml mock_invalid_rate). |
| 9 | repeats=3 in run.yaml for mock runs | Makes the consistency flip-rate metric measurable tonight; real-run repeat count is Anas's call. |
| 10 | Candidate strategies = exactly one further stop at any lap from t to (total_laps − last_laps_exclusion), each available compound, plus no-stop when legal | One-more-stop covers the vast majority of real dry-race situations from mid-race; full multi-stop search is v2. Documented in LIMITATIONS.md. |
| 11 | Scoring "agreement with team" uses the action only (PIT/STAY), compound agreement reported separately | A model can be right to pit but reasonably differ on compound; conflating them hides signal. |
| 12 | SC lap times in rollout = field-median actual lap time on that lap | Everyone circulates at delta under SC; the focal car's compound barely matters. Uses hindsight SC timeline, which is fine because the simulator is explicitly a hindsight-optimal oracle. |
