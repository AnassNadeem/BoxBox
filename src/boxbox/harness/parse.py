"""Strict JSON answer parsing. Never raises; invalid output is a recorded metric."""

from __future__ import annotations

import json
import re
from typing import Optional

from pydantic import ValidationError

from boxbox.data.schemas import ModelDecision

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def _candidate_payloads(text: str) -> list[str]:
    """Plausible JSON substrings, most specific first."""
    candidates: list[str] = []
    for m in _FENCE_RE.finditer(text):
        candidates.append(m.group(1).strip())
    # first balanced {...} block in the raw text
    start = text.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start : i + 1])
                    break
    candidates.append(text.strip())
    return candidates


def parse_decision(text: str) -> tuple[Optional[ModelDecision], Optional[str]]:
    """(decision, None) on success; (None, reason) on failure. Never raises."""
    if not text or not text.strip():
        return None, "empty response"
    last_reason = "no JSON object found"
    for payload in _candidate_payloads(text):
        if not payload:
            continue
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            last_reason = f"json decode error: {exc}"
            continue
        if not isinstance(data, dict):
            last_reason = "top-level JSON is not an object"
            continue
        # normalize sloppy-but-unambiguous outputs before strict validation
        if isinstance(data.get("action"), str):
            data["action"] = data["action"].strip().upper()
        comp = data.get("compound")
        if isinstance(comp, str):
            comp = comp.strip().upper()
            data["compound"] = None if comp in ("", "NULL", "NONE") else comp
        if isinstance(data.get("confidence"), (int, float)):
            data["confidence"] = min(1.0, max(0.0, float(data["confidence"])))
        try:
            decision = ModelDecision.model_validate(data)
        except ValidationError as exc:
            last_reason = f"schema validation failed: {exc.errors()[0].get('msg', 'invalid')}"
            continue
        if isinstance(decision.rationale, str) and len(decision.rationale.split()) > 80:
            decision.rationale = " ".join(decision.rationale.split()[:80]) + "..."
        return decision, None
    return None, last_reason
