"""Prompt construction (section 8). PROMPT_VERSION is part of every cache key."""

from __future__ import annotations

import json

from boxbox.data.schemas import DecisionPoint

PROMPT_VERSION = "v1"

SYSTEM_PROMPT = (
    "You are the chief race strategist for the focal car's team. Decide using only "
    "the provided state. Output strict JSON, nothing else."
)

OUTPUT_SCHEMA = (
    '{"action": "PIT" | "STAY", "compound": "<one of compounds_available or null>", '
    '"confidence": 0.0-1.0, "rationale": "<max 50 words>"}'
)


def build_messages(dp: DecisionPoint) -> list[dict[str, str]]:
    """OpenAI-style message list. Only dp.state and dp.question are serialized -
    the hindsight fields (team action etc.) never reach the model."""
    state_json = json.dumps(dp.state.model_dump(), indent=1)
    user = (
        f"RACE STATE:\n{state_json}\n\n"
        f"QUESTION: {dp.question}\n\n"
        f"Answer with strict JSON only, exactly this schema:\n{OUTPUT_SCHEMA}"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]
