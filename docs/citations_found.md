# BOXBOX — Citations found for §2 Related Work

Real, verifiable references for the six `[CITE]` placeholders in `paper/boxbox_draft.md`
§2. Every entry below was confirmed against a primary source (arXiv abstract page, journal
DOI page, dblp, or publisher page) on 2026-06-16. **Nothing here is invented** — where a
detail could not be confirmed it is marked. Verify each yourself before submission via the
URL/DOI given.

> How to read this: each `[CITE: …]` slot from the draft lists one or more confirmed
> references. Author lists, years, venues, and DOIs are quoted from the source pages.

---

## Slot (i) — `[CITE: data contamination in LLM benchmarks]`

**1. Deng, C., Zhao, Y., Tang, X., Gerstein, M., & Cohan, A. (2024). Investigating Data
Contamination in Modern Benchmarks for Large Language Models.**
- Venue: NAACL 2024 (Proceedings of the 2024 Conference of the North American Chapter of the
  Association for Computational Linguistics).
- arXiv: 2311.09783 (submitted Nov 2023). URL: https://arxiv.org/abs/2311.09783
- ACL Anthology: https://aclanthology.org/2024.naacl-long.482/
- Supports: benchmark questions/answers leaking into training data inflate measured
  performance; proposes retrieval-based + TS-Guessing contamination probes.
- Verified: title, 5 authors, venue, arXiv id all confirmed from the arXiv abstract page.

**2. Xu, C., Guan, S., Greene, D., & Kechadi, M-T. (2024). Benchmark Data Contamination of
Large Language Models: A Survey.**
- arXiv: 2406.04244 (submitted Jun 2024). URL: https://arxiv.org/abs/2406.04244
- Supports: survey framing of "Benchmark Data Contamination (BDC)" as a systemic threat to
  static benchmarks. Good as the survey-level cite alongside Deng et al.
- Verified: title, 4 authors, year confirmed from the arXiv abstract page.
- Note: this is an arXiv preprint survey; if you prefer a peer-reviewed survey, an
  alternative is the EMNLP 2025 "Benchmarking Large Language Models Under Data Contamination:
  A Survey from Static to Dynamic Evaluation" (aclanthology.org/2025.emnlp-main.511/,
  arXiv 2502.17521) — title/venue seen in search results but **not** independently fetched,
  so confirm before use.

---

## Slot (ii) — `[CITE: contamination-resistant or temporal evaluation]`

**3. White, C., Dooley, S., Roberts, M., Pal, A., Feuer, B., Jain, S., Shwartz-Ziv, R.,
Jain, N., Saifullah, K., Dey, S., Agrawal, S., Sandha, S. S., Naidu, S., Hegde, C.,
LeCun, Y., Goldstein, T., Neiswanger, W., & Goldblum, M. (2024). LiveBench: A Challenging,
Contamination-Limited LLM Benchmark.**
- arXiv: 2406.19314 (submitted Jun 2024). URL: https://arxiv.org/abs/2406.19314
- Project: https://livebench.ai
- Supports: the central design logic of BOXBOX — using frequently-updated, recently-released
  source material (post-dating training) to build a contamination-resistant test set with
  objective ground-truth scoring.
- Verified: title (note: arXiv now reads "Contamination-**Limited**", not "-Free" as in some
  secondary listings), full 18-author list, year confirmed from the arXiv abstract page.
- Note: this is the closest direct analogue to BOXBOX's "post-cutoff season" framing. If you
  want a second, the LLM-forecasting/temporal-leakage literature (e.g. "Test of Time:
  Rethinking Temporal Signal of Benchmark Contamination", arXiv 2509.00072) appeared in
  search but was **not** independently fetched — confirm before citing.

---

## Slot (iii) — `[CITE: LLM agents / decision-making]`

**4. Klissarov, M., Hjelm, D., Toshev, A., & Mazoure, B. (2024). On the Modeling
Capabilities of Large Language Models for Sequential Decision Making.**
- arXiv: 2410.05656 (submitted Oct 2024). URL: https://arxiv.org/abs/2410.05656
- Supports: evaluating LLMs as sequential decision-makers (generating actions / reward
  models across interactive domains) rather than single-shot QA — directly matches the
  draft's "sequential decision-making and planning under uncertainty" sentence.
- Verified: title, 4 authors, year confirmed from the arXiv abstract page. No peer-reviewed
  venue stated on the abstract page (arXiv preprint).

---

## Slot (iv) — `[CITE: agent benchmarks]`

**5. Liu, X., Yu, H., Zhang, H., Xu, Y., Lei, X., Lai, H., Gu, Y., Ding, H., Men, K.,
Yang, K., Zhang, S., Deng, X., Zeng, A., Du, Z., Zhang, C., Shen, S., Zhang, T., Su, Y.,
Sun, H., Huang, M., Dong, Y., & Tang, J. (2024). AgentBench: Evaluating LLMs as Agents.**
- Venue: ICLR 2024 (poster). https://iclr.cc/virtual/2024/poster/17388
- arXiv: 2308.03688 (submitted 2023). URL: https://arxiv.org/abs/2308.03688
- Supports: the "growing literature evaluates models as agents that must choose actions over
  time" claim, and the contrast that "much of this work scores task completion" (AgentBench's
  8 environments score task success), whereas BOXBOX scores per-decision quality vs an optimum.
- Verified: title, full 22-author list, ICLR'24 venue, arXiv id confirmed from arXiv +
  ICLR pages.

---

## Slot (v) — `[CITE: F1 strategy / pit-stop optimisation]`

**6. Bekker, J., & Lotz, W. (2009). Planning Formula One race strategies using
discrete-event simulation.**
- Venue: Journal of the Operational Research Society, **60**(7), 952–961.
- DOI: 10.1057/palgrave.jors.2602626
- URL: https://link.springer.com/article/10.1057/palgrave.jors.2602626
- Supports: foundational computational/OR approach to F1 pit-stop strategy via simulation.
- Verified: authors, title, journal, vol 60, issue 7, pp. 952–961, year, DOI confirmed
  via dblp (dblp.uni-trier.de/rec/journals/jors/BekkerL09.html).

**7. Heilmeier, A., Thomaser, A., Graf, M., & Betz, J. (2020). Virtual Strategy Engineer:
Using Artificial Neural Networks for Making Race Strategy Decisions in Circuit Motorsport.**
- Venue: Applied Sciences, **10**(21), 7805.
- DOI: 10.3390/app10217805
- URL: https://www.mdpi.com/2076-3417/10/21/7805
- Supports: data-driven (ANN) pit-stop/compound decision-making in F1 — the "optimisation /
  decision" end of the strategy literature the draft draws modelling ideas from.
- Verified: authors, title, Applied Sciences vol 10 issue 21 art. 7805, DOI, year confirmed
  via MDPI + search.

---

## Slot (vi) — `[CITE: race simulation]`

**8. Heilmeier, A., Graf, M., & Lienkamp, M. (2018). A Race Simulation for Strategy Decisions
in Circuit Motorsports.**
- Venue: 2018 21st International Conference on Intelligent Transportation Systems (IEEE ITSC),
  pp. 2986–2993.
- DOI: 10.1109/ITSC.2018.8570012
- URL: https://ieeexplore.ieee.org/document/8570012/
- Open code (same group): https://github.com/TUMFTM/race-simulation
- Supports: the lap-wise race-simulation methodology (tyre degradation, fuel-mass loss, pit
  stops) that BOXBOX's transparent simulator is a simplified analogue of.
- Verified: authors, title, ITSC 2018 venue, pp. 2986–2993, DOI confirmed via IEEE/ACM DL
  + search.

---

## Coverage summary

| Draft `[CITE]` slot | Confirmed reference(s) |
|---|---|
| (i) data contamination in LLM benchmarks | Deng et al. 2024 (NAACL); Xu et al. 2024 (survey) |
| (ii) contamination-resistant / temporal eval | White et al. 2024 (LiveBench) |
| (iii) LLM agents / decision-making | Klissarov et al. 2024 |
| (iv) agent benchmarks | Liu et al. 2024 (AgentBench, ICLR'24) |
| (v) F1 strategy / pit-stop optimisation | Bekker & Lotz 2009 (JORS); Heilmeier et al. 2020 (VSE) |
| (vi) race simulation | Heilmeier et al. 2018 (ITSC) |

All six slots have at least one independently-verified reference. The two items explicitly
flagged "not independently fetched" (the EMNLP-2025 contamination survey and the Test-of-Time
temporal paper) are **optional extras** — confirm them yourself before use; do not cite as-is.
