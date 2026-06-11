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
6. **Hindsight SC timeline.** The optimal strategy knows when future SC periods occur
   (it is a hindsight oracle by design); models do not. delta_seconds therefore measures
   distance from *hindsight*-optimal, not from the best *ex-ante* decision. This is
   disclosed prominently; agreement-with-team and beat-team metrics partially compensate.
7. **Gap figures are end-of-lap interval approximations**, not live GPS gaps.
8. **Pit-loss is a per-race scalar** (median of observed stops), not lap- or
   traffic-dependent. SC pit-loss factor defaults to 0.55 when not measurable.
9. **Tyre age for used sets**: FastF1 TyreLife includes pre-race usage where known, but
   practice-used sets may carry hidden age in 2026 data sources.
10. **The mock leaderboard is fake by construction** — it validates plumbing, not model
    skill. All numbers in tonight's outputs are placeholders until real runs.
