"""Disk cache for model responses (mock or real). A second identical run costs $0.

Key: sha256(model_id | PROMPT_VERSION | dp_id | temperature | repeat_index).
Each entry is a CallResult JSON file under outputs/cache/.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

from boxbox.data.schemas import CallResult

REPO_ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = REPO_ROOT / "outputs" / "cache"


def cache_key(
    model_id: str, prompt_version: str, dp_id: str, temperature: float, repeat_index: int
) -> str:
    blob = f"{model_id}|{prompt_version}|{dp_id}|{temperature:g}|{repeat_index}"
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class ResponseCache:
    def __init__(self, cache_dir: Path = CACHE_DIR):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, key: str) -> Optional[CallResult]:
        path = self._path(key)
        if not path.exists():
            return None
        try:
            result = CallResult.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            return None  # corrupt entry: treat as a miss, it will be rewritten
        result.cached = True
        return result

    def put(self, key: str, result: CallResult) -> None:
        self._path(key).write_text(result.model_dump_json(), encoding="utf-8")
