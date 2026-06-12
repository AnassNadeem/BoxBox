"""Model runner: OpenRouter calls with retries + cost ledger, and a deterministic
mock mode (the default tonight). Every response is cached to disk immediately;
a second identical run makes zero API calls and costs $0.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from boxbox.data.schemas import CallResult, DecisionPoint
from boxbox.harness.cache import ResponseCache, cache_key
from boxbox.harness.parse import parse_decision
from boxbox.harness.prompts import PROMPT_VERSION, build_messages

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUTS_DIR = REPO_ROOT / "outputs"
LEDGER_PATH = OUTPUTS_DIR / "cost_ledger.csv"


class SpendCapExceeded(RuntimeError):
    pass


# Models that rejected response_format=json_object this session; we stop asking.
_JSON_MODE_UNSUPPORTED: set[str] = set()


def create_chat_completion(
    client: Any,
    model_id: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    extra_body: Optional[dict] = None,
) -> Any:
    """One chat completion, requesting JSON mode where the provider supports it.
    If the provider rejects response_format=json_object, retry once without it and
    remember the model so later calls skip straight to plain mode."""
    kwargs: dict[str, Any] = dict(
        model=model_id, messages=messages, temperature=temperature, max_tokens=max_tokens
    )
    if extra_body:
        kwargs["extra_body"] = extra_body
    if model_id not in _JSON_MODE_UNSUPPORTED:
        try:
            return client.chat.completions.create(response_format={"type": "json_object"}, **kwargs)
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            msg = str(exc).lower()
            rejected_json_mode = (
                status is not None
                and 400 <= status < 500
                and status != 429
                and ("response_format" in msg or "json_object" in msg or "structured output" in msg)
            )
            if not rejected_json_mode:
                raise
            _JSON_MODE_UNSUPPORTED.add(model_id)
            log.warning(
                "%s rejected response_format=json_object; falling back without it", model_id
            )
    return client.chat.completions.create(**kwargs)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class CostLedger:
    """Append-only CSV ledger of every call's reported token usage and cost."""

    COLUMNS = [
        "timestamp_utc",
        "model_name",
        "model_id",
        "dp_id",
        "repeat_index",
        "prompt_tokens",
        "completion_tokens",
        "cost_usd",
        "cumulative_usd",
        "cached",
    ]

    def __init__(self, path: Path = LEDGER_PATH, spend_cap_usd: float = 1.0):
        self.path = path
        self.spend_cap_usd = spend_cap_usd
        self.total_usd = 0.0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():  # resume: trust the persisted cumulative total
            try:
                rows = list(csv.DictReader(self.path.open(encoding="utf-8")))
                if rows:
                    self.total_usd = float(rows[-1]["cumulative_usd"])
            except (KeyError, ValueError, OSError):
                log.warning("Unreadable cost ledger at %s; starting total at 0", self.path)
        else:
            with self.path.open("w", newline="", encoding="utf-8") as fh:
                csv.writer(fh).writerow(self.COLUMNS)

    @staticmethod
    def compute_cost(
        prompt_tokens: int,
        completion_tokens: int,
        price_in_per_mtok: Optional[float],
        price_out_per_mtok: Optional[float],
    ) -> float:
        cost_in = prompt_tokens / 1e6 * (price_in_per_mtok or 0.0)
        cost_out = completion_tokens / 1e6 * (price_out_per_mtok or 0.0)
        return cost_in + cost_out

    def record(self, result: CallResult) -> None:
        self.total_usd += result.cost_usd
        with self.path.open("a", newline="", encoding="utf-8") as fh:
            csv.writer(fh).writerow(
                [
                    result.timestamp_utc,
                    result.model_name,
                    result.model_id,
                    result.dp_id,
                    result.repeat_index,
                    result.prompt_tokens,
                    result.completion_tokens,
                    f"{result.cost_usd:.6f}",
                    f"{self.total_usd:.6f}",
                    result.cached,
                ]
            )

    def check_cap(self, projected_next_usd: float = 0.0) -> None:
        if self.total_usd + projected_next_usd > self.spend_cap_usd:
            raise SpendCapExceeded(
                f"projected spend ${self.total_usd + projected_next_usd:.4f} exceeds "
                f"cap ${self.spend_cap_usd:.2f} - aborting all paid calls"
            )


# ----------------------------------------------------------------------------- mock

_MOCK_RATIONALES = [
    "Undercut window is open and the gap behind covers the stop.",
    "Tyre delta to the cars around us does not justify losing track position.",
    "Degradation trend on the current set is stable; extend the stint.",
    "Cheap stop under this track status; box and cover the rival.",
    "Target the overcut: rivals on fresh rubber are in traffic.",
]


def mock_response(dp: DecisionPoint, model_name: str, repeat_index: int, run_cfg: dict) -> str:
    """Deterministic fake model output, seeded by (dp_id, model, repeat)."""
    seed = int(
        hashlib.sha256(f"{dp.dp_id}|{model_name}|{repeat_index}".encode()).hexdigest()[:12], 16
    )
    rng = random.Random(seed)
    invalid_rate = float(run_cfg.get("mock_invalid_rate", 0.04))
    pit_rate = float(run_cfg.get("mock_pit_rate", 0.30))

    roll = rng.random()
    if roll < invalid_rate / 2:
        return "Sorry, as a race strategist I think we should consider boxing soon."
    if roll < invalid_rate:
        return '{"action": "PIT", "compound": "MED'  # truncated JSON

    action = "PIT" if rng.random() < pit_rate else "STAY"
    compound = rng.choice(dp.state.focal.compounds_available) if action == "PIT" else None
    payload = json.dumps(
        {
            "action": action,
            "compound": compound,
            "confidence": round(rng.uniform(0.55, 0.97), 2),
            "rationale": rng.choice(_MOCK_RATIONALES),
        }
    )
    if rng.random() < 0.2:  # exercise the fence-stripping path
        return f"```json\n{payload}\n```"
    return payload


# ---------------------------------------------------------------------------- runner


class Runner:
    def __init__(
        self,
        run_cfg: dict,
        models_cfg: dict,
        mock: bool = True,
        cache: Optional[ResponseCache] = None,
        ledger: Optional[CostLedger] = None,
    ):
        self.run_cfg = run_cfg
        self.models_cfg = models_cfg
        self.mock = mock
        self.cache = cache if cache is not None else ResponseCache()
        self.ledger = (
            ledger
            if ledger is not None
            else CostLedger(spend_cap_usd=float(run_cfg.get("spend_cap_usd", 1.0)))
        )
        self.temperature = float(run_cfg.get("temperature", 0.0))
        self.max_tokens = int(run_cfg.get("max_tokens", 350))
        self.api_calls = 0  # actual model invocations (cache misses), incl. mock
        self._client: Any = None

    # -- model roster ------------------------------------------------------------
    def models(self) -> list[dict]:
        roster = self.models_cfg.get("models", [])
        if self.mock:
            return roster  # mock runs every listed model; enabled gates real spend only
        usable = [m for m in roster if m.get("enabled")]
        if not usable:
            raise RuntimeError(
                "No enabled models in config/models.yaml - run scripts/verify_models.py"
            )
        return usable

    # -- single call -------------------------------------------------------------
    def call(self, dp: DecisionPoint, model: dict, repeat_index: int) -> CallResult:
        model_name = model["name"]
        # mock ids stay distinct per model so cache keys never collide across models
        model_id = f"mock/{model_name}" if self.mock else model["openrouter_id"]
        key = cache_key(model_id, PROMPT_VERSION, dp.dp_id, self.temperature, repeat_index)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        if self.mock:
            result = self._call_mock(dp, model_name, repeat_index)
        else:
            result = self._call_real(dp, model, repeat_index)
        self.cache.put(key, result)
        self.ledger.record(result)
        return result

    def _call_mock(self, dp: DecisionPoint, model_name: str, repeat_index: int) -> CallResult:
        self.api_calls += 1
        raw = mock_response(dp, model_name, repeat_index, self.run_cfg)
        decision, reason = parse_decision(raw)
        prompt_chars = sum(len(m["content"]) for m in build_messages(dp))
        return CallResult(
            dp_id=dp.dp_id,
            model_name=model_name,
            model_id=f"mock/{model_name}",
            prompt_version=PROMPT_VERSION,
            temperature=self.temperature,
            repeat_index=repeat_index,
            raw_response=raw,
            decision=decision,
            invalid=decision is None,
            error=reason,
            prompt_tokens=prompt_chars // 4,  # fake but plausible
            completion_tokens=len(raw) // 4,
            cost_usd=0.0,
            timestamp_utc=_utcnow(),
        )

    def _call_real(self, dp: DecisionPoint, model: dict, repeat_index: int) -> CallResult:
        if os.environ.get("ALLOW_SPEND") != "1" or not os.environ.get("OPENROUTER_API_KEY"):
            raise RuntimeError(
                "Real calls require OPENROUTER_API_KEY and ALLOW_SPEND=1 in the environment"
            )
        self.ledger.check_cap()
        client = self._get_client()
        messages = build_messages(dp)
        model_id = model["openrouter_id"]

        raw, usage, error = "", None, None
        decision = None
        for attempt in range(4):  # backoff on 429/5xx; one extra parse retry below
            try:
                self.api_calls += 1
                resp = create_chat_completion(
                    client, model_id, messages, self.temperature, self.max_tokens
                )
                raw = resp.choices[0].message.content or ""
                usage = resp.usage
                decision, error = parse_decision(raw)
                if decision is None and attempt == 0:
                    continue  # the single parse-failure retry
                break
            except Exception as exc:
                error = str(exc)
                status = getattr(exc, "status_code", None)
                if status is not None and status not in (429,) and status < 500:
                    break  # non-retryable client error
                time.sleep(2.0**attempt)

        prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        cost = CostLedger.compute_cost(
            prompt_tokens,
            completion_tokens,
            model.get("pricing_in_per_mtok"),
            model.get("pricing_out_per_mtok"),
        )
        return CallResult(
            dp_id=dp.dp_id,
            model_name=model["name"],
            model_id=model_id,
            prompt_version=PROMPT_VERSION,
            temperature=self.temperature,
            repeat_index=repeat_index,
            raw_response=raw,
            decision=decision,
            invalid=decision is None,
            error=error,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
            timestamp_utc=_utcnow(),
        )

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=os.environ["OPENROUTER_API_KEY"],
            )
        return self._client

    # -- batch -------------------------------------------------------------------
    def run_all(self, dps: list[DecisionPoint], repeats: Optional[int] = None) -> list[CallResult]:
        n_rep = repeats if repeats is not None else int(self.run_cfg.get("repeats", 1))
        results: list[CallResult] = []
        for model in self.models():
            for dp in dps:
                for rep in range(n_rep):
                    results.append(self.call(dp, model, rep))
        return results
