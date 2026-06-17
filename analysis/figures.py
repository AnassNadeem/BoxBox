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

# Pretty display names for per-model figures.
PRETTY = {
    "gpt-5.5": "GPT-5.5",
    "deepseek-v3.2": "DeepSeek V3.2",
    "gemini-3.1-pro": "Gemini 3.1 Pro",
    "claude-opus-4.8": "Claude Opus 4.8",
    "claude-haiku-4.5": "Claude Haiku 4.5",
    "claude-fable-5": "Claude Fable 5",
}

plt.rcParams.update({"figure.dpi": 120, "axes.grid": True, "grid.alpha": 0.25})


def load_inputs() -> tuple[dict, list[dict]]:
    board = json.loads((OUTPUTS / "leaderboard.json").read_text(encoding="utf-8"))
    scores = [
        json.loads(line)
        for line in (OUTPUTS / "scores.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return board, scores


def _primary_2026(scores: list[dict]) -> dict[str, dict[str, float]]:
    """Per-model mean delta_exante / delta_hindsight on the 2026 PRIMARY set
    (post-cutoff races, dry subset). This is the headline evaluation set."""
    ex: dict[str, list[float]] = {}
    hi: dict[str, list[float]] = {}
    for s in scores:
        if s["invalid"] or s.get("changeable_conditions") or s["season"] != 2026:
            continue
        if s.get("delta_exante_s") is not None:
            ex.setdefault(s["model_name"], []).append(s["delta_exante_s"])
        if s.get("delta_hindsight_s") is not None:
            hi.setdefault(s["model_name"], []).append(s["delta_hindsight_s"])
    return {
        m: {
            "mean_exante": float(np.mean(ex[m])),
            "mean_hindsight": float(np.mean(hi[m])) if hi.get(m) else np.nan,
        }
        for m in ex
    }


def fig_leaderboard_bar(scores: list[dict], board: dict) -> Path:
    # 2026 PRIMARY set (post-cutoff dry races) — the contamination-proof headline.
    prim = _primary_2026(scores)
    rows = sorted(prim.items(), key=lambda kv: kv[1]["mean_exante"], reverse=True)  # best at top
    names = [PRETTY.get(m, m) for m, _ in rows]
    exante = [v["mean_exante"] for _, v in rows]
    hindsight = [v["mean_hindsight"] for _, v in rows]
    y = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(8, 4.6))
    bars = ax.barh(y + 0.2, exante, height=0.4, color=ACCENT, label="vs ex-ante optimal (primary)")
    ax.barh(y - 0.2, hindsight, height=0.4, color="#888", label="vs hindsight optimal")
    ax.bar_label(bars, fmt="%.1f", padding=3, fontsize=9)
    ax.set_yticks(y, names)
    ax.set_xlabel("mean delta (s) - lower is better")
    ax.set_title(f"BOXBOX leaderboard — 2026 primary set ({board['mode']} data)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    path = FIG_DIR / "leaderboard_bar.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_accuracy_vs_consistency(scores: list[dict], board: dict) -> Path:
    """Scatter: accuracy (mean ex-ante delta on the 2026 primary set, x) vs consistency
    (flip rate %, y). Both lower = better; the bottom-left is the ideal region."""
    prim = _primary_2026(scores)
    flip = {m["model"]: m["flip_rate_pct"] for m in board["models"]}
    fig, ax = plt.subplots(figsize=(9, 6))
    xs, ys = [], []
    for model, v in prim.items():
        x = v["mean_exante"]
        y = flip.get(model)
        if y is None:
            continue
        xs.append(x)
        ys.append(y)
        ax.scatter(x, y, s=180, color=ACCENT, edgecolor=DARK, linewidth=1.4, zorder=3)
        ax.annotate(
            PRETTY.get(model, model),
            (x, y),
            xytext=(12, 0),
            textcoords="offset points",
            va="center",
            fontsize=11,
            fontweight="bold",
        )
    # ideal region (accurate & consistent)
    x0 = min(xs) - 0.5
    ax.axhspan(-2, 15, xmin=0, xmax=0.35, color="#2e7d32", alpha=0.08, zorder=0)
    ax.text(
        x0,
        12,
        "accurate & consistent\n(ideal region)",
        fontsize=9,
        color="#2e7d32",
        style="italic",
        va="top",
    )
    ax.set_xlabel("mean ex-ante delta, s  (lower = more accurate)")
    ax.set_ylabel("flip rate, %  (lower = more consistent)")
    ax.set_title("Accuracy vs. consistency (2026 primary set)")
    fig.tight_layout()
    path = FIG_DIR / "accuracy_vs_consistency.png"
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


def _calibration_records_all() -> list[dict]:
    """Per-stint simulator-vs-actual records pooled across all 11 races.

    Read-only: ingest_race reads data/processed/*.json (no network, no spend); the
    degradation fits and calibration_records are deterministic. Mirrors the per-race
    logic in scripts/build_dataset.py so the combined figure matches the per-race ones.
    """
    from boxbox.config import load_config
    from boxbox.data.ingest import ingest_race
    from boxbox.dataset import race_specs
    from boxbox.sim.degradation import calibration_records
    from boxbox.sim.race_sim import make_simulator

    sim_cfg = load_config("run").get("simulator", {})
    records: list[dict] = []
    for spec in race_specs(None):
        race = ingest_race(spec["race_id"], int(spec["year"]), str(spec["event"]))
        _, deg, _, _, _ = make_simulator(race, sim_cfg)
        records += calibration_records(race, deg)
    return records


def fig_calibration_combined() -> Path:
    """Paper Figure 2: simulator calibration pooled over every stint in all 11 races.

    Left: predicted vs observed mean lap time per stint (one point per stint) with a
    y=x reference. Right: histogram of per-lap absolute error, with the per-stint
    median (0.09 s) and mean (0.22 s) MAE marked. Axes are in seconds-per-lap so the
    scatter, the histogram, and the annotated MAE are all in the same units."""
    records = _calibration_records_all()
    actual = np.array([r["actual_s"] / r["n_laps"] for r in records])
    predicted = np.array([r["predicted_s"] / r["n_laps"] for r in records])
    abs_err = np.abs(predicted - actual)  # per-lap absolute error, one per stint
    median_mae = float(np.median(abs_err))
    mean_mae = float(np.mean(abs_err))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    ax1.scatter(actual, predicted, s=20, alpha=0.55, color=ACCENT, edgecolor="none", zorder=3)
    lo = float(min(actual.min(), predicted.min()))
    hi = float(max(actual.max(), predicted.max()))
    pad = 0.03 * (hi - lo)
    ax1.plot([lo - pad, hi + pad], [lo - pad, hi + pad], "k--", lw=1.2, zorder=2, label="y = x")
    ax1.set_xlim(lo - pad, hi + pad)
    ax1.set_ylim(lo - pad, hi + pad)
    ax1.set_aspect("equal", adjustable="box")
    ax1.set_xlabel("observed mean lap time per stint (s)")
    ax1.set_ylabel("simulated mean lap time per stint (s)")
    ax1.set_title(f"Stint calibration — all 11 races ({len(records)} stints)")
    ax1.legend(loc="upper left", fontsize=9)

    ax2.hist(abs_err, bins=40, color=DARK, edgecolor="white", linewidth=0.4)
    ax2.axvline(median_mae, color=ACCENT, lw=2, label=f"median MAE = {median_mae:.2f} s/lap")
    ax2.axvline(mean_mae, color="#2e7d32", lw=2, ls="--", label=f"mean MAE = {mean_mae:.2f} s/lap")
    ax2.set_xlabel("per-lap absolute error (s/lap)")
    ax2.set_ylabel("stints")
    ax2.set_title("Per-stint calibration error")
    ax2.legend(fontsize=9)

    fig.tight_layout()
    path = FIG_DIR / "calibration_combined.png"
    fig.savefig(path)
    plt.close(fig)
    return path


def _season_gap_stats(scores: list[dict]) -> dict[str, dict]:
    """Per-model pre-2026 vs 2026 mean delta_exante on the DRY subset, plus the H3
    test (two-sided Mann-Whitney U, Holm-corrected across models). Recomputed here
    from scores.jsonl so the figure is identical to outputs/contamination.md (§8e)
    rather than the unweighted per-season averages stored on the leaderboard."""
    from scipy.stats import mannwhitneyu

    valid = [
        s
        for s in scores
        if not s["invalid"]
        and s.get("delta_exante_s") is not None
        and not s.get("changeable_conditions")
    ]
    models = sorted({s["model_name"] for s in valid})

    def deltas(m: str, pred) -> list[float]:
        return [s["delta_exante_s"] for s in valid if s["model_name"] == m and pred(s)]

    stats: dict[str, dict] = {}
    pvals: dict[str, float] = {}
    for m in models:
        pre = deltas(m, lambda s: s["season"] < 2026)
        new = deltas(m, lambda s: s["season"] == 2026)
        if not pre or not new:
            continue
        stats[m] = {
            "pre": float(np.mean(pre)),
            "new": float(np.mean(new)),
            "gap": float(np.mean(pre) - np.mean(new)),
            "n_pre": len(pre),
            "n_new": len(new),
        }
        if len(pre) >= 3 and len(new) >= 3:
            _, p = mannwhitneyu(pre, new, alternative="two-sided")
            pvals[m] = float(p)

    # Holm-Bonferroni across models (identical to scripts/contamination_report.py).
    items = sorted(pvals.items(), key=lambda kv: kv[1])
    k = len(items)
    running = 0.0
    for i, (m, p) in enumerate(items):
        adj = max(min(1.0, (k - i) * p), running)
        running = adj
        stats[m]["holm_p"] = adj
        stats[m]["sig"] = adj < 0.05
    return stats


def fig_season_gap(scores: list[dict]) -> Path | None:
    """Contamination-check chart: per-model mean delta on pre-2026 vs 2026 races, on the
    DRY subset, with Holm-significant gaps marked. The finding is a WEAK, MIXED signal —
    the figure must not imply a clean null OR a strong recall effect, so each model is
    labelled by the *direction* of its significant gap, not just a bare asterisk."""
    stats = _season_gap_stats(scores)
    if not stats:
        return None
    # Order by 2026 mean (best first) for a leaderboard-like reading.
    names = sorted(stats, key=lambda m: stats[m]["new"])
    pre = [stats[m]["pre"] for m in names]
    new = [stats[m]["new"] for m in names]
    x = np.arange(len(names))

    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.bar(
        x - 0.2,
        pre,
        width=0.4,
        label="2024-25 pre-cutoff (possibly in training data)",
        color="#888",
    )
    ax.bar(x + 0.2, new, width=0.4, label="2026 post-cutoff (contamination-proof)", color=ACCENT)

    ymax = max(max(pre), max(new))
    for i, m in enumerate(names):
        st = stats[m]
        top = max(st["pre"], st["new"])
        if not st.get("sig"):
            tag, color = "n.s.", "#555"
        elif st["gap"] < 0:
            # significantly LOWER (better) on pre-2026 — the recall direction
            tag, color = "★ better on pre-2026\n(recall signal)", "#b00020"
        else:
            # significant but WORSE on pre-2026 — opposite of recall
            tag, color = "* worse on pre-2026\n(not recall)", "#1565c0"
        ax.annotate(
            tag,
            (i, top),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8,
            fontweight="bold",
            color=color,
        )
        ax.annotate(
            f"gap {st['gap']:+.2f}s",
            (i, top),
            xytext=(0, 34),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=7.5,
            color=color,
        )

    ax.set_xticks(x, [PRETTY.get(m, m) for m in names], rotation=15, ha="right")
    ax.set_ylabel("mean delta vs ex-ante optimal (s)  —  lower = better")
    ax.set_ylim(top=ymax * 1.5)
    ax.set_title("Contamination check: pre-2026 vs 2026 (dry subset, Holm-corrected)")
    ax.legend(loc="upper right", fontsize=8)
    ax.text(
        0.0,
        -0.22,
        "Weak, mixed signal: a true recall effect would mean LOWER 2026 bars (★). Only DeepSeek and "
        "Gemini show that, and only weakly\n(gaps −0.67s / −3.35s). GPT-5.5 and Haiku are significantly "
        "WORSE on pre-2026 (opposite of recall); Opus shows no significant gap.\nThe same-track Monaco "
        "comparison is flat. ★/* = significant after Holm @0.05; n.s. = not significant.",
        transform=ax.transAxes,
        fontsize=7.5,
        va="top",
        color="#333",
    )
    fig.tight_layout()
    path = FIG_DIR / "season_gap.png"
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def main() -> int:
    if not (OUTPUTS / "leaderboard.json").exists() or not (OUTPUTS / "scores.jsonl").exists():
        print("Missing outputs/leaderboard.json or outputs/scores.jsonl - run the pipeline first.")
        return 2
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    board, scores = load_inputs()
    paths = [
        fig_leaderboard_bar(scores, board),
        fig_accuracy_vs_consistency(scores, board),
        fig_delta_distribution(scores),
        fig_race_heatmap(board),
        fig_flip_rate(board),
        fig_calibration_combined(),
    ]
    season = fig_season_gap(scores)
    if season:
        paths.append(season)
    for p in paths:
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
