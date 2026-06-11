"""End-to-end mock pipeline on the synthetic race:
extract -> main pass -> probe -> score -> leaderboard."""

from __future__ import annotations

import json

from boxbox.extract.decision_points import extract_decision_points
from boxbox.harness.cache import ResponseCache
from boxbox.harness.probe import select_probe_dps
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
    results = runner.run_all(dps)  # main pass: run.yaml repeats=1, temperature 0
    assert len(results) == len(dps) * 2
    assert runner.ledger.total_usd == 0.0  # mock never spends

    scores = score_all(dps, results, {race.race_id: race})
    assert len(scores) == len(results)
    valid = [s for s in scores if not s.invalid]
    assert valid
    for s in valid:
        assert s.delta_hindsight_s is not None and s.delta_hindsight_s >= -1e-6
        assert s.delta_exante_s is not None
        # both deltas share the realized-world currency, so the ex-ante delta
        # is never larger than the hindsight delta (its baseline is never faster)
        assert s.delta_exante_s <= s.delta_hindsight_s + 1e-6
        assert s.optimal_action in ("PIT", "STAY")
        assert s.exante_action in ("PIT", "STAY")

    # without a probe, the flip rate must be unavailable - never from the main pass
    board_no_probe = aggregate(scores, mode="mock")
    assert all(row["flip_rate_pct"] is None for row in board_no_probe["models"])

    # consistency probe: most contentious DPs, all models x 5 samples, default temp
    probe_cfg = run_cfg["consistency_probe"]
    selections = select_probe_dps(results, int(probe_cfg["n_decision_points"]))
    assert selections
    wanted = {sel.dp_id for sel in selections}
    probe_dps = [dp for dp in dps if dp.dp_id in wanted]
    probe_runner = Runner(
        {**run_cfg, "temperature": probe_cfg["temperature"], "repeats": probe_cfg["samples"]},
        models_cfg,
        mock=True,
        cache=ResponseCache(tmp_path / "cache"),
        ledger=CostLedger(tmp_path / "ledger.csv"),
    )
    probe_results = probe_runner.run_all(probe_dps)
    assert len(probe_results) == len(probe_dps) * 2 * int(probe_cfg["samples"])
    probe_scores = score_all(probe_dps, probe_results, {race.race_id: race})

    board = aggregate(scores, mode="mock", probe_scores=probe_scores)
    assert {m["model"] for m in board["models"]} == {"mock-a", "mock-b"}
    assert board["n_probe_decision_points"] == len(probe_dps)
    for row in board["models"]:
        assert row["mean_delta_exante_s"] is not None
        assert row["mean_delta_hindsight_s"] is not None
        assert row["invalid_pct"] is not None
        assert row["flip_rate_pct"] is not None  # 5 probe samples make flips measurable

    md = to_markdown(board)
    assert "BOXBOX leaderboard" in md and "mock-a" in md

    paths = write_outputs(board, out_dir=tmp_path / "out")
    for p in paths:
        assert p.exists() and p.stat().st_size > 0
    loaded = json.loads((tmp_path / "out" / "leaderboard.json").read_text(encoding="utf-8"))
    assert loaded["mode"] == "mock"
