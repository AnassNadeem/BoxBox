"""Resolve our model roster against OpenRouter's live model list (free GET, no key).

Updates config/models.yaml in place: exact openrouter_id, listed pricing per MTok,
enabled+verified flags. Models not found stay enabled: false with a note - no
guessed substitutes.

Usage: python scripts/verify_models.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import yaml
from rich.console import Console
from rich.table import Table

REPO_ROOT = Path(__file__).resolve().parents[1]
MODELS_YAML = REPO_ROOT / "config" / "models.yaml"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


def _variants(name: str) -> list[str]:
    """Plausible id fragments for a config model name like 'claude-opus-4.8'."""
    base = name.lower()
    return list(dict.fromkeys([base, base.replace(".", "-"), base.replace(".", "")]))


def _match(name: str, listing: list[dict]) -> dict | None:
    """Best listing entry for a model name: exact slug tail match, else contains."""
    candidates: list[tuple[int, dict]] = []
    for entry in listing:
        mid = str(entry.get("id", "")).lower()
        slug_tail = mid.split("/")[-1]
        for variant in _variants(name):
            if slug_tail == variant:
                candidates.append((0, entry))
            elif slug_tail.startswith(variant):
                candidates.append((1, entry))
            elif variant in mid:
                candidates.append((2, entry))
    if not candidates:
        return None
    candidates.sort(key=lambda c: (c[0], len(str(c[1].get("id", "")))))
    return candidates[0][1]


def main() -> int:
    console = Console()
    try:
        resp = httpx.get(OPENROUTER_MODELS_URL, timeout=30)
        resp.raise_for_status()
        listing = resp.json().get("data", [])
    except Exception as exc:
        console.print(f"[red]Failed to fetch OpenRouter model list: {exc}[/red]")
        return 1
    console.print(f"OpenRouter lists {len(listing)} models")

    config = yaml.safe_load(MODELS_YAML.read_text(encoding="utf-8"))
    table = Table(title="Model resolution")
    for col in ("name", "resolved id", "$/MTok in", "$/MTok out", "status"):
        table.add_column(col)

    for model in config["models"]:
        entry = _match(model["name"], listing)
        if entry is None:
            model["enabled"] = False
            model["verified"] = False
            model["note"] = "NOT FOUND on OpenRouter - left disabled, no substitute guessed"
            table.add_row(model["name"], "-", "-", "-", "[red]not found[/red]")
            continue
        pricing = entry.get("pricing", {})
        # OpenRouter prices are USD per single token (strings) -> per MTok
        price_in = float(pricing.get("prompt", 0) or 0) * 1e6
        price_out = float(pricing.get("completion", 0) or 0) * 1e6
        model["openrouter_id"] = entry["id"]
        model["pricing_in_per_mtok"] = round(price_in, 4)
        model["pricing_out_per_mtok"] = round(price_out, 4)
        model["enabled"] = True
        model["verified"] = True
        model["note"] = f"verified against /models ({entry.get('name', '')})"
        table.add_row(
            model["name"],
            entry["id"],
            f"{price_in:.2f}",
            f"{price_out:.2f}",
            "[green]verified[/green]",
        )

    MODELS_YAML.write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    console.print(table)
    console.print(f"Updated {MODELS_YAML}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
