"""Consistency-probe selection: disagreement ranking, vote hygiene, determinism."""

from __future__ import annotations

from boxbox.data.schemas import CallResult, ModelDecision
from boxbox.harness.probe import select_probe_dps


def call(
    dp_id: str, model: str, action: str = "PIT", invalid: bool = False, repeat: int = 0
) -> CallResult:
    return CallResult(
        dp_id=dp_id,
        model_name=model,
        model_id=f"mock/{model}",
        prompt_version="test",
        temperature=0.0,
        repeat_index=repeat,
        decision=None if invalid else ModelDecision(action=action),  # type: ignore[arg-type]
        invalid=invalid,
    )


def test_select_prefers_highest_disagreement():
    results = [
        call("dp-unanimous", "m1", "PIT"),
        call("dp-unanimous", "m2", "PIT"),
        call("dp-unanimous", "m3", "PIT"),
        call("dp-split", "m1", "PIT"),
        call("dp-split", "m2", "STAY"),
        call("dp-split", "m3", "PIT"),
    ]
    sel = select_probe_dps(results, 1)
    assert [s.dp_id for s in sel] == ["dp-split"]
    assert sel[0].disagreement > 0
    assert sel[0].votes == {"PIT": 2, "STAY": 1}
    assert "split" in sel[0].reason


def test_select_ignores_invalid_votes_and_breaks_ties_on_dp_id():
    results = [
        call("dp1", "m1", "PIT"),
        call("dp1", "m2", "STAY"),
        call("dp2", "m1", "PIT"),
        call("dp2", "m2", "STAY"),
        call("dp2", "m3", invalid=True),  # not a vote
    ]
    sel = select_probe_dps(results, 2)
    assert [s.dp_id for s in sel] == ["dp1", "dp2"]
    assert all(s.n_models == 2 and s.disagreement == 0.5 for s in sel)


def test_select_one_vote_per_model_and_caps_at_n():
    results = []
    for i in range(30):
        results.append(call(f"dp{i:02d}", "m1", "PIT"))
        results.append(call(f"dp{i:02d}", "m1", "STAY", repeat=1))  # same model: no vote
        results.append(call(f"dp{i:02d}", "m2", "STAY"))
    sel = select_probe_dps(results, 20)
    assert len(sel) == 20
    # the repeat answer must not count: two models, one vote each
    assert all(s.n_models == 2 for s in sel)
