"""Harness tests: cache zero-cost reruns, mock determinism, cost-ledger math + cap."""

from __future__ import annotations

import pytest

from boxbox.data.schemas import CallResult
from boxbox.extract.decision_points import extract_decision_points
from boxbox.harness.cache import ResponseCache
from boxbox.harness.runner import CostLedger, Runner, SpendCapExceeded

PIT_LOSS = 20.0


@pytest.fixture()
def dps(race, extraction_cfg):
    return extract_decision_points(race, PIT_LOSS, extraction_cfg)[:5]


def make_runner(tmp_path, run_cfg, n_models: int = 2) -> Runner:
    models_cfg = {
        "models": [{"name": f"mock-model-{i}", "openrouter_id": "mock"} for i in range(n_models)]
    }
    return Runner(
        run_cfg,
        models_cfg,
        mock=True,
        cache=ResponseCache(tmp_path / "cache"),
        ledger=CostLedger(tmp_path / "ledger.csv", spend_cap_usd=1.0),
    )


def test_second_run_hits_cache_with_zero_new_calls(tmp_path, run_cfg, dps):
    runner = make_runner(tmp_path, run_cfg)
    first = runner.run_all(dps, repeats=2)
    assert runner.api_calls == len(first)

    runner2 = make_runner(tmp_path, run_cfg)
    second = runner2.run_all(dps, repeats=2)
    assert runner2.api_calls == 0, "second identical run must make zero new calls"
    assert len(second) == len(first)
    assert all(r.cached for r in second)
    assert runner2.ledger.total_usd == 0.0


def test_mock_is_deterministic(tmp_path, run_cfg, dps):
    r1 = make_runner(tmp_path / "a", run_cfg).run_all(dps, repeats=1)
    r2 = make_runner(tmp_path / "b", run_cfg).run_all(dps, repeats=1)
    assert [x.raw_response for x in r1] == [x.raw_response for x in r2]


def test_mock_produces_some_invalids_and_pits(tmp_path, run_cfg, dps, race, extraction_cfg):
    all_dps = extract_decision_points(race, PIT_LOSS, extraction_cfg)
    runner = make_runner(tmp_path, run_cfg, n_models=4)
    results = runner.run_all(all_dps, repeats=3)
    actions = [r.decision.action for r in results if r.decision is not None]
    assert "PIT" in actions and "STAY" in actions
    assert any(r.invalid for r in results), "mock should exercise the invalid path"
    invalid_rate = sum(r.invalid for r in results) / len(results)
    assert invalid_rate < 0.15


def test_cost_math():
    assert CostLedger.compute_cost(1_000_000, 0, 3.0, 15.0) == pytest.approx(3.0)
    assert CostLedger.compute_cost(500_000, 200_000, 3.0, 15.0) == pytest.approx(1.5 + 3.0)
    assert CostLedger.compute_cost(1000, 1000, None, None) == 0.0


def test_ledger_accumulates_and_cap_aborts(tmp_path):
    ledger = CostLedger(tmp_path / "ledger.csv", spend_cap_usd=1.0)

    def fake_result(cost: float) -> CallResult:
        return CallResult(
            dp_id="dp",
            model_name="m",
            model_id="x",
            prompt_version="v1",
            temperature=0.0,
            repeat_index=0,
            cost_usd=cost,
            timestamp_utc="t",
        )

    ledger.record(fake_result(0.4))
    ledger.record(fake_result(0.5))
    assert ledger.total_usd == pytest.approx(0.9)
    ledger.check_cap(0.05)  # 0.95 < 1.00: fine
    with pytest.raises(SpendCapExceeded):
        ledger.check_cap(0.2)  # 1.1 > 1.00: abort

    # a fresh ledger instance resumes the persisted cumulative total
    resumed = CostLedger(tmp_path / "ledger.csv", spend_cap_usd=1.0)
    assert resumed.total_usd == pytest.approx(0.9)
