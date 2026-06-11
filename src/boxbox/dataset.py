"""Decision-point dataset persistence under data/decision_points/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from boxbox.config import load_config
from boxbox.data.schemas import DecisionPoint

REPO_ROOT = Path(__file__).resolve().parents[2]
DP_DIR = REPO_ROOT / "data" / "decision_points"


def race_specs(groups: list[str] | None = None) -> list[dict[str, Any]]:
    """Race specs from extraction.yaml, deduped by race_id, in group order.

    Default groups: 2026 benchmark races + contamination controls (the validation
    race is a subset of contamination, so it is covered).
    """
    cfg = load_config("extraction")
    groups = groups or ["races_2026", "races_contamination"]
    seen: set[str] = set()
    specs: list[dict[str, Any]] = []
    for group in groups:
        for spec in cfg.get(group, []):
            if spec["race_id"] not in seen:
                seen.add(spec["race_id"])
                specs.append(spec)
    return specs


def save_decision_points(race_id: str, dps: list[DecisionPoint]) -> Path:
    DP_DIR.mkdir(parents=True, exist_ok=True)
    path = DP_DIR / f"{race_id}.json"
    payload = {"race_id": race_id, "decision_points": [dp.model_dump() for dp in dps]}
    path.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    return path


def load_decision_points(race_id: str) -> list[DecisionPoint]:
    path = DP_DIR / f"{race_id}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return [DecisionPoint.model_validate(d) for d in data["decision_points"]]


def load_all_decision_points() -> list[DecisionPoint]:
    dps: list[DecisionPoint] = []
    if not DP_DIR.exists():
        return dps
    for path in sorted(DP_DIR.glob("*.json")):
        if path.name == "manifest.json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        dps.extend(DecisionPoint.model_validate(d) for d in data["decision_points"])
    return dps
