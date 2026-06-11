"""YAML config loading. All thresholds live in config/*.yaml - never hardcoded."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"


def load_config(name: str) -> dict[str, Any]:
    """Load config/<name>.yaml as a dict."""
    path = CONFIG_DIR / f"{name}.yaml"
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data or {}
