"""Leaderboard aggregation: per-model metrics -> markdown, CSV, and JSON outputs.

HEADLINE metric is computed on the DRY subset (changeable_conditions == False). The
v1 simulator runs a single stint to the flag and cannot model a wet->dry crossover, so
changeable-condition decision points are out of scope for the headline (see
docs/PREREGISTRATION.md / docs/LIMITATIONS.md). The full-set numbers are kept as a
clearly-labelled appendix.
"""

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


def _model_rows(scores: list[Score], probe_scores: list[Score]) -> list[dict[str, Any]]:
    """Per-model aggregate rows over the given score subset. Flip rate comes only from
    the probe subset (resampled at the probe temperature)."""
    by_model: dict[str, list[Score]] = {}
    for s in scores:
        by_model.setdefault(s.model_name, []).append(s)

    probe_by_model: dict[str, list[Score]] = {}
    for s in probe_scores:
        if not s.invalid and s.action is not None:
            probe_by_model.setdefault(s.model_name, []).append(s)

    rows: list[dict[str, Any]] = []
    for model, ss in sorted(by_model.items()):
        valid = [s for s in ss if not s.invalid and s.delta_exante_s is not None]
        deltas = [s.delta_exante_s for s in valid]
        deltas_hind = [s.delta_hindsight_s for s in valid if s.delta_hindsight_s is not None]

        by_dp: dict[str, set[str]] = {}
        seen_once: dict[str, int] = {}
        for s in probe_by_model.get(model, []):
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
                "mean_delta_exante_s": round(statistics.mean(deltas), 3) if deltas else None,
                "median_delta_exante_s": round(statistics.median(deltas), 3) if deltas else None,
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
    return rows


def _exclusion_stats(scores: list[Score]) -> tuple[dict[str, dict[str, int]], int, int]:
    """(per-race {excluded, total} DP counts, total excluded DPs, total DPs)."""
    all_dps: dict[str, set[str]] = {}
    chg_dps: dict[str, set[str]] = {}
    for s in scores:
        all_dps.setdefault(s.race_id, set()).add(s.dp_id)
        if s.changeable_conditions:
            chg_dps.setdefault(s.race_id, set()).add(s.dp_id)
    by_race = {
        race: {"excluded": len(chg_dps.get(race, set())), "total": len(dps)}
        for race, dps in sorted(all_dps.items())
    }
    total_dps = sum(len(d) for d in all_dps.values())
    excluded = sum(len(d) for d in chg_dps.values())
    return by_race, excluded, total_dps


def aggregate(
    scores: list[Score],
    mode: str = "mock",
    probe_scores: list[Score] | None = None,
) -> dict[str, Any]:
    probe_scores = probe_scores or []
    dry = [s for s in scores if not s.changeable_conditions]
    dry_probe = [s for s in probe_scores if not s.changeable_conditions]

    by_race, n_excluded, n_total = _exclusion_stats(scores)
    headline = _model_rows(dry, dry_probe)  # DRY subset = headline
    appendix = _model_rows(scores, probe_scores)  # full set = appendix

    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": mode,
        "headline_subset": "dry (changeable_conditions == false)",
        "n_decision_points": len({s.dp_id for s in dry}),  # dry/headline DP count
        "n_decision_points_full": len({s.dp_id for s in scores}),
        "n_excluded_changeable_dps": n_excluded,
        "excluded_by_race": by_race,
        "n_probe_decision_points": len({s.dp_id for s in dry_probe}),
        "races": sorted({s.race_id for s in dry}),
        "models": headline,
        "appendix_full_set": appendix,
    }


def _table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| # | Model | Mean delta vs ex-ante optimal (s) | Median (s) | "
        "Mean delta vs hindsight (s) | Beat team % | Agree team % | Invalid % | "
        "Flip rate % | Calls |",
        "|---|-------|----------------------------------:|-----------:|"
        "----------------------------:|------------:|-------------:|----------:|"
        "------------:|------:|",
    ]
    for i, r in enumerate(rows, start=1):
        lines.append(
            f"| {i} | {r['model']} | {r['mean_delta_exante_s']} | "
            f"{r['median_delta_exante_s']} | {r['mean_delta_hindsight_s']} | "
            f"{r['beat_team_pct']} | {r['agree_team_pct']} | {r['invalid_pct']} | "
            f"{r['flip_rate_pct']} | {r['n_calls']} |"
        )
    return lines


def to_markdown(board: dict[str, Any]) -> str:
    lines = [
        "# BOXBOX leaderboard",
        "",
        f"Generated {board['generated_utc']} | mode: **{board['mode']}** | "
        f"**headline = dry subset**: {board['n_decision_points']} decision points "
        f"(of {board['n_decision_points_full']} total; "
        f"{board['n_excluded_changeable_dps']} changeable-condition DPs excluded) | "
        f"races: {', '.join(board['races'])}",
        "",
    ]
    if board["mode"] == "mock":
        lines += ["> **Mock results.** Numbers validate the pipeline, not model skill.", ""]
    if board.get("n_probe_decision_points"):
        lines += [
            f"Flip rate from a {board['n_probe_decision_points']}-DP consistency probe "
            "(dry subset, resampled at the probe temperature); other columns from the main pass.",
            "",
        ]
    lines += ["## Headline (dry subset — changeable-condition DPs excluded)", ""]
    lines += _table(board["models"])
    lines += [""]

    # exclusion breakdown
    lines += ["## Excluded changeable-condition decision points (per race)", ""]
    lines += ["| Race | Excluded | Total |", "|---|---:|---:|"]
    for race, c in board["excluded_by_race"].items():
        if c["excluded"]:
            lines.append(f"| {race} | {c['excluded']} | {c['total']} |")
    lines += [
        "",
        f"**{board['n_excluded_changeable_dps']}** DPs excluded from the headline. The v1 "
        "simulator runs a single stint to the flag and cannot model a wet->dry crossover, so "
        "wet/changeable-condition decision points are out of scope for the headline metric "
        "(criterion in docs/PREREGISTRATION.md; consistent with the prereg's no-wet-modeling scope).",
        "",
    ]

    # appendix: full set
    lines += [
        "## Appendix: full set (INCLUDES changeable-condition DPs — not the headline)",
        "",
        "> These numbers include wet/changeable decision points the v1 simulator cannot model "
        "(a wet-tyre pit is run to the flag at wet pace), which inflates the means. Shown for "
        "completeness only.",
        "",
    ]
    lines += _table(board["appendix_full_set"])
    lines += [""]
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
        for r in board["models"]:  # headline (dry) rows
            writer.writerow(r)
    return [md, cs, js]
