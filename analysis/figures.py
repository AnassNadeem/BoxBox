"""Paper figures from benchmark results -> outputs/figures/.

Reads outputs/scores.jsonl and outputs/leaderboard.json (mock or real).
Usage: python analysis/figures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUTS = REPO_ROOT / "outputs"
FIG_DIR = OUTPUTS / "figures"

ACCENT = "#e10600"
DARK = "#15151e"

plt.rcParams.update({"figure.dpi": 120, "axes.grid": True, "grid.alpha": 0.25})


def load_inputs() -> tuple[dict, list[dict]]:
    board = json.loads((OUTPUTS / "leaderboard.json").read_text(encoding="utf-8"))
    scores = [
        json.loads(line)
        for line in (OUTPUTS / "scores.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return board, scores


def fig_leaderboard_bar(board: dict) -> Path:
    rows = [m for m in board["models"] if m["mean_delta_exante_s"] is not None]
    rows.sort(key=lambda m: m["mean_delta_exante_s"], reverse=True)  # best at top of barh
    names = [m["model"] for m in rows]
    exante = [m["mean_delta_exante_s"] for m in rows]
    hindsight = [m.get("mean_delta_hindsight_s") or np.nan for m in rows]
    y = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(8, 4.6))
    bars = ax.barh(y + 0.2, exante, height=0.4, color=ACCENT, label="vs ex-ante optimal (primary)")
    ax.barh(y - 0.2, hindsight, height=0.4, color="#888", label="vs hindsight optimal")
    ax.bar_label(bars, fmt="%.1f", padding=3, fontsize=9)
    ax.set_yticks(y, names)
    ax.set_xlabel("mean delta (s) - lower is better")
    ax.set_title(f"BOXBOX leaderboard ({board['mode']} data)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    path = FIG_DIR / "leaderboard_bar.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_delta_distribution(scores: list[dict]) -> Path:
    # Headline = dry subset: exclude changeable-condition DPs (out of v1-sim scope).
    by_model: dict[str, list[float]] = {}
    for s in scores:
        if s["invalid"] or s["delta_exante_s"] is None or s.get("changeable_conditions"):
            continue
        by_model.setdefault(s["model_name"], []).append(s["delta_exante_s"])
    models = sorted(by_model)
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    data = [by_model[m] for m in models]
    bp = ax.boxplot(data, tick_labels=models, showfliers=False, patch_artist=True)
    for patch in bp["boxes"]:
        patch.set_facecolor(DARK)
        patch.set_edgecolor(ACCENT)
    for med in bp["medians"]:
        med.set_color(ACCENT)
    ax.set_ylabel("delta vs ex-ante optimal (s)")
    ax.set_title("score-delta distribution per model")
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    fig.tight_layout()
    path = FIG_DIR / "delta_distribution.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_race_heatmap(board: dict) -> Path:
    models = [m for m in board["models"] if m.get("per_race_mean_delta_exante_s")]
    races = sorted({r for m in models for r in m["per_race_mean_delta_exante_s"]})
    grid = np.array(
        [[m["per_race_mean_delta_exante_s"].get(r, np.nan) for r in races] for m in models]
    )
    fig, ax = plt.subplots(figsize=(max(7.0, 1.0 * len(races)), 0.6 * len(models) + 2))
    im = ax.imshow(grid, aspect="auto", cmap="RdYlGn_r")
    ax.set_xticks(range(len(races)), races, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(len(models)), [m["model"] for m in models], fontsize=9)
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            if not np.isnan(grid[i, j]):
                ax.text(j, i, f"{grid[i, j]:.0f}", ha="center", va="center", fontsize=7)
    fig.colorbar(im, label="mean delta vs ex-ante optimal (s)")
    ax.set_title("per-race performance heatmap")
    ax.grid(False)
    fig.tight_layout()
    path = FIG_DIR / "race_heatmap.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_flip_rate(board: dict) -> Path:
    rows = [m for m in board["models"] if m["flip_rate_pct"] is not None]
    rows.sort(key=lambda m: m["flip_rate_pct"])
    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar(
        [m["model"] for m in rows], [m["flip_rate_pct"] for m in rows], color=DARK, edgecolor=ACCENT
    )
    ax.bar_label(bars, fmt="%.0f%%", padding=2, fontsize=9)
    ax.set_ylabel("flip rate % (repeats disagree)")
    ax.set_title("consistency: how often repeated prompts flip the call")
    plt.setp(ax.get_xticklabels(), rotation=20, ha="right")
    fig.tight_layout()
    path = FIG_DIR / "flip_rate.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_season_gap(board: dict) -> Path | None:
    """Contamination-gap chart: mean delta on pre-2026 vs 2026 races per model."""
    models = [m for m in board["models"] if m.get("per_season_mean_delta_exante_s")]
    seasons = sorted({s for m in models for s in m["per_season_mean_delta_exante_s"]})
    old = [s for s in seasons if s < "2026"]
    if not old or "2026" not in seasons:
        return None
    names = [m["model"] for m in models]
    pre = [
        np.mean(
            [
                m["per_season_mean_delta_exante_s"][s]
                for s in old
                if s in m["per_season_mean_delta_exante_s"]
            ]
        )
        for m in models
    ]
    new = [m["per_season_mean_delta_exante_s"].get("2026", np.nan) for m in models]
    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    ax.bar(x - 0.2, pre, width=0.4, label="2024-25 (possibly in training data)", color="#888")
    ax.bar(x + 0.2, new, width=0.4, label="2026 (contamination-proof)", color=ACCENT)
    ax.set_xticks(x, names, rotation=20, ha="right")
    ax.set_ylabel("mean delta vs ex-ante optimal (s)")
    ax.set_title("contamination gap: old vs new races")
    ax.legend()
    fig.tight_layout()
    path = FIG_DIR / "season_gap.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def main() -> int:
    if not (OUTPUTS / "leaderboard.json").exists() or not (OUTPUTS / "scores.jsonl").exists():
        print("Missing outputs/leaderboard.json or outputs/scores.jsonl - run the pipeline first.")
        return 2
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    board, scores = load_inputs()
    paths = [
        fig_leaderboard_bar(board),
        fig_delta_distribution(scores),
        fig_race_heatmap(board),
        fig_flip_rate(board),
    ]
    season = fig_season_gap(board)
    if season:
        paths.append(season)
    for p in paths:
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
