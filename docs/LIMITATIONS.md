# LIMITATIONS.md — running list for the paper

1. **No traffic interaction in the simulator (headline limitation).** Counterfactual
   rollouts simulate only the focal car; all other cars' behavior is held fixed at what
   actually happened. A counterfactual pit that would have dropped the car into traffic
   is scored as if the track were clear (optional flat rejoin penalty, default 0s).
   Undercut/overcut dynamics are therefore only partially captured.
2. **Single-further-stop strategy space.** The candidate grid considers at most one more
   pit stop from the decision lap onward. Decisions whose true optimum required two more
   stops (e.g. early-race wet-to-dry transitions) are scored against the best
   one-more-stop plan instead.
3. **Linear degradation model.** lap_time = a + b·tyre_age + c·lap_number ignores cliff
   behavior, warm-up laps, and track evolution nonlinearity. Calibration MAE quantifies
   the damage.
4. **Compound availability is assumed, not known.** Remaining tyre sets per driver are
   not in public timing data; we assume all dry compounds are available to everyone.
5. **SC/VSC laps modeled as field-median lap time.** Ignores the strategic value of
   track position concertina effects under SC.
6. **Oracle information sets.** The primary metric (`delta_exante`) now compares
   against an oracle with the models' own information set: green-flag racing assumed
   after the decision lap (the current lap's known status is kept), valued in the
   realized race. The hindsight oracle (knows all future SC/VSC) remains as secondary
   context. Residual hindsight in the ex-ante baseline: realized valuation still uses
   the actual SC timeline and field-median paces, and the ex-ante oracle carries no
   probabilistic SC model — a real strategist hedges on SC likelihood; ours assumes
   zero.
7. **Gap figures are end-of-lap interval approximations**, not live GPS gaps.
8. **Pit-loss is a per-race scalar** (median of observed stops), not lap- or
   traffic-dependent. SC pit-loss factor defaults to 0.55 when not measurable.
9. **Tyre age for used sets**: FastF1 TyreLife includes pre-race usage where known, but
   practice-used sets may carry hidden age in 2026 data sources.
10. **Mock mode validates plumbing, not model skill** — mock runs produce fake placeholder
    numbers and remain available for pipeline testing. The headline leaderboard and all
    paper numbers come from the **real paid run** (mode: real, 2026-06-13, prereg-v4); they
    are not placeholders.
11. **Wet/changeable-condition decision points are excluded from the headline metric**
    (the dry subset is the headline). The simulator runs a single stint to the flag and
    cannot model a wet→dry crossover (a stint cannot switch back to slicks), so a model
    that pits onto INTERMEDIATE/WET is rolled out on wet tyres to the end at wet pace —
    an artifact, not a strategy error (this produced the Silverstone delta outliers,
    mean ~235s on wet-tyre calls vs ~8.5s on all others). A point is tagged
    `changeable_conditions` MECHANICALLY, from conditions only (never from score/delta),
    via `wet_running_near(t, window=5)`: the field actually ran an INTER/WET or
    rain-affected lap within 5 laps of t (range `[t−5, t]`, `≤ t` so leakage-safe), OR the
    focal car is on INTER/WET entering the lap. (prereg-v4 replaced the earlier race-level
    rain flag + "any wet lap seen" latch, which over-offered INTER on the dry Miami race
    and Canada's dry phase.) Headline leaderboard/figures/contamination use
    `changeable_conditions == false`; full-set numbers are retained in a clearly-labelled
    appendix. This excludes **19 of 178 DPs** (Silverstone 18, Canada 1); the dry headline
    set is **159**. Consistent with limitation 2 (no wet→dry modeling).
