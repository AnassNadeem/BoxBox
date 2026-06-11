"""Parser robustness: valid, fenced, truncated, garbage - classified, never raising."""

from __future__ import annotations

import pytest

from boxbox.harness.parse import parse_decision

VALID = '{"action": "PIT", "compound": "HARD", "confidence": 0.8, "rationale": "undercut"}'


def test_valid_json():
    decision, reason = parse_decision(VALID)
    assert reason is None
    assert decision is not None
    assert decision.action == "PIT" and decision.compound == "HARD"


def test_json_in_markdown_fences():
    decision, _ = parse_decision(f"Here is my answer:\n```json\n{VALID}\n```\nthanks")
    assert decision is not None and decision.action == "PIT"


def test_json_with_surrounding_prose():
    decision, _ = parse_decision(f"I think we should box. {VALID} Final answer.")
    assert decision is not None and decision.action == "PIT"


def test_truncated_json_is_invalid():
    decision, reason = parse_decision('{"action": "PIT", "compound": "MED')
    assert decision is None and reason


def test_garbage_is_invalid():
    decision, reason = parse_decision("As an AI strategist I would consider pitting soon.")
    assert decision is None and reason


def test_empty_is_invalid():
    decision, reason = parse_decision("")
    assert decision is None and reason


def test_wrong_action_value_is_invalid():
    decision, _ = parse_decision('{"action": "BOX", "compound": null, "confidence": 0.5}')
    assert decision is None


def test_normalization_lowercase_and_null_strings():
    decision, _ = parse_decision(
        '{"action": "stay", "compound": "none", "confidence": 1.4, "rationale": ""}'
    )
    assert decision is not None
    assert decision.action == "STAY"
    assert decision.compound is None
    assert decision.confidence == 1.0  # clamped


@pytest.mark.parametrize(
    "payload",
    [
        "null",
        "[1, 2, 3]",
        '{"compound": "SOFT"}',  # missing required action
        '{"action": "PIT", "compound": "BLUE"}',  # not a real compound
    ],
)
def test_other_invalids_never_raise(payload):
    decision, reason = parse_decision(payload)
    assert decision is None and reason
