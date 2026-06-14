"""Sunday's live loop: poll a data source, trigger decision prompts, log + draft posts.

The loop is source-agnostic: a LiveSource yields ever-growing RaceData snapshots
and owns the passage of time via sleep(). The replay source scales time without
the loop knowing it is a replay. The loop never crashes on source hiccups and
never publishes anything - social post lines are DRAFTS in outputs/live_log.md.
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Protocol

from rich.console import Console

from boxbox.config import load_config
from boxbox.data.schemas import DecisionPoint, RaceData
from boxbox.extract.decision_points import RaceIndex, build_state
from boxbox.harness.runner import Runner
from boxbox.sim.degradation import estimate_pit_loss

log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
LIVE_LOG = REPO_ROOT / "outputs" / "live_log.md"


class LiveSource(Protocol):
    """A live timing source. poll() returns the freshest cumulative RaceData
    snapshot (laps completed so far), or None on a transient failure.
    active() is False once the session is over. sleep() owns time."""

    def poll(self) -> Optional[RaceData]: ...
    def active(self) -> bool: ...
    def sleep(self, seconds: float) -> None: ...


class OpenF1LiveSource:
    """Real OpenF1 polling source (full refetch per poll: simple and robust)."""

    def __init__(self, year: int, event: str, race_id: str):
        from boxbox.data.openf1 import OpenF1Client, auth_from_env, find_race_session

        self.year = year
        self.event = event
        self.race_id = race_id
        # One authed client (and therefore one auto-refreshing bearer token) is reused
        # across every poll, so we don't refetch a token each cycle.
        self.auth = auth_from_env()
        self.client = OpenF1Client(auth=self.auth)
        self.session = find_race_session(self.client, year, event, live=True)
        self._last_data_wall = time.time()
        self._done = False

    def poll(self) -> Optional[RaceData]:
        from boxbox.data.openf1 import ingest_openf1

        try:
            race = ingest_openf1(self.race_id, self.year, self.event, client=self.client, live=True)
            self._last_data_wall = time.time()
            return race
        except Exception as exc:
            log.warning("OpenF1 poll failed (%s); continuing with stale state", exc)
            return None

    def active(self) -> bool:
        return not self._done

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class LiveLoop:
    def __init__(
        self,
        source: LiveSource,
        runner: Runner,
        model_names: list[str],
        live_cfg: dict,
        extraction_cfg: dict,
        log_path: Path = LIVE_LOG,
        console: Optional[Console] = None,
    ):
        self.source = source
        self.runner = runner
        self.model_names = model_names
        self.live_cfg = live_cfg
        self.extraction_cfg = extraction_cfg
        self.log_path = log_path
        self.console = console or Console()
        self.seen: set[tuple[str, int]] = set()  # dedupe per (car, lap)
        self.known_stops: set[tuple[str, int]] = set()
        self.prev_status = "GREEN"
        self.age_triggered: set[str] = set()
        self.last_progress_wall = time.time()
        self.last_max_lap = 0
        log_path.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ helpers
    def _log(self, line: str) -> None:
        stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(f"- `{stamp}` {line}\n")

    def _emit(self, race: RaceData, driver: str, lap: int, dp_type: str, trigger: str) -> None:
        if (driver, lap) in self.seen:
            return
        self.seen.add((driver, lap))
        pit_loss, _, _ = estimate_pit_loss(race)
        state = build_state(race, driver, lap, pit_loss, self.extraction_cfg)
        if state is None:
            return
        dp = DecisionPoint(
            dp_id=f"live-{race.race_id}-L{lap:03d}-{driver}-{dp_type}",
            race_id=race.race_id,
            season=race.season,
            lap=lap,
            driver=driver,
            dp_type=dp_type,  # type: ignore[arg-type]
            question=(
                f"It is lap {lap} of {race.total_laps}. Decide for {driver}: pit at the "
                f"end of this lap, or stay out? If pitting, choose the new compound."
            ),
            state=state,
            team_action="STAY",  # unknown in real time; scoring happens post-race
            trigger=trigger,
        )
        state_hash = hashlib.sha256(state.model_dump_json().encode()).hexdigest()[:8]
        for model in self.runner.models():
            if model["name"] not in self.model_names:
                continue
            result = self.runner.call(dp, model, repeat_index=0)
            decision = result.decision
            if decision is None:
                verdict = "INVALID OUTPUT"
                draft = ""
            else:
                verdict = (
                    f"**{'BOX, ' + (decision.compound or '?') if decision.action == 'PIT' else 'STAY OUT'}** "
                    f"(conf {decision.confidence:.2f})"
                )
                call_text = (
                    f"BOX for {driver}, {state.focal.compound.lower()} -> "
                    f"{(decision.compound or '?').lower()}"
                    if decision.action == "PIT"
                    else f"stay out, {driver} holds track position"
                )
                draft = (
                    f' - DRAFT POST: "Lap {lap} - {model["name"]} says {call_text}. '
                    f'Rationale: {decision.rationale}"'
                )
            line = (
                f"**Lap {lap} {driver}** [{dp_type}: {trigger}] state `{state_hash}` "
                f"- {model['name']} -> {verdict}{draft}"
            )
            self.console.print(line)
            self._log(line)

    # --------------------------------------------------------------------- tick
    def tick(self, race: RaceData) -> None:
        idx = RaceIndex(race)
        if not idx.by_lap:
            return
        max_lap = max(idx.by_lap.keys())
        if max_lap > self.last_max_lap:
            self.last_max_lap = max_lap
            self.last_progress_wall = time.time()
        decision_lap = max_lap + 1
        if decision_lap > race.total_laps:
            return
        top_n = int(self.extraction_cfg.get("type_b", {}).get("top_n_positions", 10))
        leaders = idx.order_at(max_lap)[:top_n]

        # Trigger 1: SC/VSC deployment (Type B)
        status = idx.field_status(max_lap)
        if status in ("SC", "VSC") and self.prev_status not in ("SC", "VSC"):
            self._log(f"**{status} deployed** (detected at lap {max_lap})")
            for rec in leaders:
                self._emit(race, rec.driver, decision_lap, "B", f"{status} deployed")
        self.prev_status = status

        # Trigger 2: rival pit detection (Type C)
        rival_gap = float(self.extraction_cfg.get("type_c", {}).get("rival_gap_s", 3.5))
        for stop in race.pit_stops:
            key = (stop.driver, stop.lap)
            if key in self.known_stops:
                continue
            self.known_stops.add(key)
            pit_rec = idx.rec(stop.driver, stop.lap - 1)
            if pit_rec is None or pit_rec.end_time_s is None:
                continue
            for rec in idx.by_lap.get(stop.lap - 1, []):
                if rec.driver == stop.driver or rec.end_time_s is None:
                    continue
                if abs(rec.end_time_s - pit_rec.end_time_s) <= rival_gap:
                    self._emit(
                        race,
                        rec.driver,
                        decision_lap,
                        "C",
                        f"rival {stop.driver} pitted on lap {stop.lap}",
                    )

        # Trigger 3: tyre age crosses the window threshold (Type A proxy)
        age_threshold = int(self.live_cfg.get("tyre_age_trigger", 18))
        for rec in leaders:
            if rec.tyre_age is not None and rec.tyre_age >= age_threshold:
                marker = f"{rec.driver}:{rec.stint}"
                if marker not in self.age_triggered:
                    self.age_triggered.add(marker)
                    self._emit(
                        race,
                        rec.driver,
                        decision_lap,
                        "A",
                        f"tyre age {rec.tyre_age} >= window threshold",
                    )

    def run(self) -> None:
        poll_s = float(self.live_cfg.get("poll_seconds", 45))
        stale_tol = float(self.live_cfg.get("stale_data_tolerance_s", 180))
        self._log(f"**Live loop started** (poll every {poll_s:.0f}s)")
        race: Optional[RaceData] = None
        while self.source.active():
            try:
                fresh = self.source.poll()
                if fresh is not None:
                    race = fresh
                elif time.time() - self.last_progress_wall > stale_tol:
                    self._log(
                        f"**data gap**: no fresh data for over {stale_tol:.0f}s; still polling"
                    )
                    self.last_progress_wall = time.time()  # avoid log spam
                if race is not None:
                    self.tick(race)
            except Exception as exc:  # never crash the loop
                log.exception("tick failed: %s", exc)
                self._log(f"**loop error swallowed**: {exc}")
            self.source.sleep(poll_s)
        self._log("**Live loop finished**")
        self.console.print(f"[green]Live loop finished.[/green] Log: {self.log_path}")


def build_mock_runner(model_names: list[str]) -> tuple[Runner, list[str]]:
    """Mock-mode runner restricted to the configured live models."""
    run_cfg = load_config("run")
    models_cfg = load_config("models")
    available = {m["name"] for m in models_cfg.get("models", [])}
    names = [n for n in model_names if n in available]
    return Runner(run_cfg, models_cfg, mock=True), names
