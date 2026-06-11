"""Consistency-probe selection: the decision points models disagree on most.

The main pass is single-shot at temperature 0, so it carries no information
about answer stability. A separate probe reruns the most contentious decision
points (highest cross-model action disagreement in the main pass) with several
samples at the provider-default temperature. The flip rate is computed
exclusively from probe results, never from the main pass.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass

from boxbox.data.schemas import CallResult


@dataclass
class ProbeSelection:
    dp_id: str
    votes: dict[str, int]  # action -> number of models that chose it
    n_models: int  # models with a valid main-pass answer on this DP
    disagreement: float  # 1 - top_vote/total; 0 = unanimous
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


def select_probe_dps(results: list[CallResult], n: int) -> list[ProbeSelection]:
    """Top-n decision points by cross-model action disagreement in the main pass.

    One vote per model per DP (the lowest repeat_index valid answer, in case the
    main pass ever runs with repeats > 1). Ties break on more voters, then dp_id,
    so the selection is deterministic.
    """
    first_valid: dict[tuple[str, str], CallResult] = {}
    for r in results:
        if r.invalid or r.decision is None:
            continue
        key = (r.dp_id, r.model_name)
        if key not in first_valid or r.repeat_index < first_valid[key].repeat_index:
            first_valid[key] = r

    votes_by_dp: dict[str, Counter] = {}
    for (dp_id, _model), r in first_valid.items():
        votes_by_dp.setdefault(dp_id, Counter())[r.decision.action] += 1

    selections: list[ProbeSelection] = []
    for dp_id, votes in votes_by_dp.items():
        total = sum(votes.values())
        disagreement = 1.0 - max(votes.values()) / total if total else 0.0
        split = ", ".join(f"{a}={c}" for a, c in sorted(votes.items()))
        selections.append(
            ProbeSelection(
                dp_id=dp_id,
                votes=dict(sorted(votes.items())),
                n_models=total,
                disagreement=round(disagreement, 3),
                reason=f"main-pass actions split {split} across {total} models",
            )
        )
    selections.sort(key=lambda s: (-s.disagreement, -s.n_models, s.dp_id))
    return selections[:n]
