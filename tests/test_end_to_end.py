"""End-to-end mock pipeline on the synthetic race: extract -> run -> score -> leaderboard."""

from __future__ import annotations

import json

from boxbox.extract.decision_points import extract_decision_points
from boxbox.harness.cache import ResponseCache
from boxbox.harness.runner import CostLedger, Runner
from boxbox.score.leaderboard import aggregate, to_markdown, write_outputs
from boxbox.score.scoring import score_all

PIT_LOSS = 20.0


def test_end_to_end_mock(tmp_path, race, extraction_cfg, run_cfg):
    dps = extract_decision_points(race, PIT_LOSS, extraction_cfg)
    assert dps

    models_cfg = {"models": [{"name": "mock-a"}, {"name": "mock-b"}]}
    runner = Runner(
        run_cfg,
        models_cfg,
        mock=True,
        cache=ResponseCache(tmp_path / "cache"),
        ledger=CostLedger(tmp_path / "ledger.csv"),
    )
    results = runner.run_all(dps, repeats=3)
    assert len(results) == len(dps) * 2 * 3
    assert runner.ledger.total_usd == 0.0  # mock never spends

    scores = score_all(dps, results, {race.race_id: race})
    assert len(scores) == len(results)
    valid = [s for s in scores if not s.invalid]
    assert valid
    for s in valid:
        assert s.delta_vs_optimal_s is not None and s.delta_vs_optimal_s >= -1e-6
        assert s.optimal_action in ("PIT", "STAY")

    board = aggregate(scores, mode="mock")
    assert {m["model"] for m in board["models"]} == {"mock-a", "mock-b"}
    for row in board["models"]:
        assert row["mean_delta_s"] is not None
        assert row["invalid_pct"] is not None
        assert row["flip_rate_pct"] is not None  # repeats=3 makes flips measurable

    md = to_markdown(board)
    assert "BOXBOX leaderboard" in md and "mock-a" in md

    paths = write_outputs(board, out_dir=tmp_path / "out")
    for p in paths:
        assert p.exists() and p.stat().st_size > 0
    loaded = json.loads((tmp_path / "out" / "leaderboard.json").read_text(encoding="utf-8"))
    assert loaded["mode"] == "mock"
