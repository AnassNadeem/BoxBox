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
10. **The mock leaderboard is fake by construction** — it validates plumbing, not model
    skill. All numbers in tonight's outputs are placeholders until real runs.
11. **Wet/changeable-condition decision points are excluded from the headline metric**
    (the dry subset is the headline). The simulator runs a single stint to the flag and
    cannot model a wet→dry crossover (a stint cannot switch back to slicks), so a model
    that pits onto INTERMEDIATE/WET is rolled out on wet tyres to the end at wet pace —
    an artifact, not a strategy error (this produced the Miami and Silverstone delta
    outliers, mean ~235s on wet-tyre calls vs ~8.5s on all others). A point is tagged
    `changeable_conditions` MECHANICALLY, from conditions only (never from score/delta):
    the session is declared wet (rain in the weather feed), OR the focal car is on
    INTER/WET entering the lap, OR any car runs an INTER/WET or rain-affected lap at or
    after the decision lap (so the rollout would cross changeable conditions). Headline
    leaderboard/figures/contamination use `changeable_conditions == false`; full-set
    numbers are retained in a clearly-labelled appendix. This excluded 36 of 178 DPs
    (Miami 18, Silverstone 18). Consistent with limitation 2 (no wet→dry modeling).
