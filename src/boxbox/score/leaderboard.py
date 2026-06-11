"""Leaderboard aggregation: per-model metrics -> markdown, CSV, and JSON outputs."""

from __future__ import annotations

import csv
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from boxbox.data.schemas import Score

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUTS_DIR = REPO_ROOT / "outputs"


def _pct(numer: int, denom: int) -> float | None:
    return round(100.0 * numer / denom, 1) if denom else None


def aggregate(scores: list[Score], mode: str = "mock") -> dict[str, Any]:
    by_model: dict[str, list[Score]] = {}
    for s in scores:
        by_model.setdefault(s.model_name, []).append(s)

    rows: list[dict[str, Any]] = []
    for model, ss in sorted(by_model.items()):
        valid = [s for s in ss if not s.invalid and s.delta_exante_s is not None]
        deltas = [s.delta_exante_s for s in valid]
        deltas_hind = [s.delta_hindsight_s for s in valid if s.delta_hindsight_s is not None]

        # consistency flip rate: same dp answered differently across repeats
        by_dp: dict[str, set[str]] = {}
        seen_once: dict[str, int] = {}
        for s in valid:
            by_dp.setdefault(s.dp_id, set()).add(s.action or "")
            seen_once[s.dp_id] = seen_once.get(s.dp_id, 0) + 1
        multi = [dp for dp, n in seen_once.items() if n >= 2]
        flipped = [dp for dp in multi if len(by_dp[dp]) > 1]

        per_race: dict[str, float] = {}
        per_season: dict[str, float] = {}
        for key_fn, target in (
            (lambda s: s.race_id, per_race),
            (lambda s: str(s.season), per_season),
        ):
            groups: dict[str, list[float]] = {}
            for s in valid:
                groups.setdefault(key_fn(s), []).append(s.delta_exante_s)  # type: ignore[arg-type]
            for k, v in groups.items():
                target[k] = round(statistics.mean(v), 3)

        rows.append(
            {
                "model": model,
                "n_calls": len(ss),
                "n_valid": len(valid),
                # PRIMARY metric: delta vs the ex-ante (no-future-SC) oracle
                "mean_delta_exante_s": round(statistics.mean(deltas), 3) if deltas else None,
                "median_delta_exante_s": round(statistics.median(deltas), 3) if deltas else None,
                # secondary context: delta vs the hindsight oracle
                "mean_delta_hindsight_s": (
                    round(statistics.mean(deltas_hind), 3) if deltas_hind else None
                ),
                "median_delta_hindsight_s": (
                    round(statistics.median(deltas_hind), 3) if deltas_hind else None
                ),
                "beat_team_pct": _pct(sum(1 for s in valid if s.beat_team), len(valid)),
                "agree_team_pct": _pct(sum(1 for s in valid if s.agree_team_action), len(valid)),
                "invalid_pct": _pct(sum(1 for s in ss if s.invalid), len(ss)),
                "flip_rate_pct": _pct(len(flipped), len(multi)),
                "per_race_mean_delta_exante_s": per_race,
                "per_season_mean_delta_exante_s": per_season,
            }
        )

    rows.sort(key=lambda r: (r["mean_delta_exante_s"] is None, r["mean_delta_exante_s"]))
    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": mode,
        "n_decision_points": len({s.dp_id for s in scores}),
        "races": sorted({s.race_id for s in scores}),
        "models": rows,
    }


def to_markdown(board: dict[str, Any]) -> str:
    lines = [
        "# BOXBOX leaderboard",
        "",
        f"Generated {board['generated_utc']} | mode: **{board['mode']}** | "
        f"{board['n_decision_points']} decision points | races: {', '.join(board['races'])}",
        "",
    ]
    if board["mode"] == "mock":
        lines += ["> **Mock results.** Numbers validate the pipeline, not model skill.", ""]
    lines += [
        "| # | Model | Mean delta vs ex-ante optimal (s) | Median (s) | "
        "Mean delta vs hindsight (s) | Beat team % | Agree team % | Invalid % | "
        "Flip rate % | Calls |",
        "|---|-------|----------------------------------:|-----------:|"
        "----------------------------:|------------:|-------------:|----------:|"
        "------------:|------:|",
    ]
    for i, r in enumerate(board["models"], start=1):
        lines.append(
            f"| {i} | {r['model']} | {r['mean_delta_exante_s']} | "
            f"{r['median_delta_exante_s']} | {r['mean_delta_hindsight_s']} | "
            f"{r['beat_team_pct']} | {r['agree_team_pct']} | {r['invalid_pct']} | "
            f"{r['flip_rate_pct']} | {r['n_calls']} |"
        )
    lines.append("")
    return "\n".join(lines)


def write_outputs(board: dict[str, Any], out_dir: Path = OUTPUTS_DIR) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    md = out_dir / "leaderboard.md"
    md.write_text(to_markdown(board), encoding="utf-8")

    js = out_dir / "leaderboard.json"
    js.write_text(json.dumps(board, indent=1), encoding="utf-8")

    cs = out_dir / "leaderboard.csv"
    flat_cols = [
        "model",
        "n_calls",
        "n_valid",
        "mean_delta_exante_s",
        "median_delta_exante_s",
        "mean_delta_hindsight_s",
        "median_delta_hindsight_s",
        "beat_team_pct",
        "agree_team_pct",
        "invalid_pct",
        "flip_rate_pct",
    ]
    with cs.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=flat_cols, extrasaction="ignore")
        writer.writeheader()
        for r in board["models"]:
            writer.writerow(r)
    return [md, cs, js]
