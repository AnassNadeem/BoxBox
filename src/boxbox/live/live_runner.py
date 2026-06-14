"""Sunday's live loop: poll a data source, trigger decision prompts, log + draft posts.

The loop is source-agnostic: a LiveSource yields ever-growing RaceData snapshots
and owns the passage of time via sleep(). The replay source scales time without
the loop knowing it is a replay. The loop never crashes on source hiccups and
never publishes anything - social post lines are DRAFTS in outputs/live_log.md.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
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
LIVE_STATE = REPO_ROOT / "outputs" / "live_state.json"


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
        state_path: Optional[Path] = LIVE_STATE,
    ):
        self.source = source
        self.runner = runner
        self.model_names = model_names
        self.live_cfg = live_cfg
        self.extraction_cfg = extraction_cfg
        self.log_path = log_path
        self.state_path = state_path
        self.console = console or Console()
        self.seen: set[tuple[str, int]] = set()  # dedupe per (car, lap)
        self.known_stops: set[tuple[str, int]] = set()
        self.prev_status = "GREEN"
        self.age_triggered: set[str] = set()
        self.last_progress_wall = time.time()
        self.last_max_lap = 0
        self.decisions: list[dict] = []  # structured decision history for the dashboard
        self.started_wall = time.time()
        self.mode_label = "live"  # set by the launcher (replay/live/manual) for the UI
        # Only cars on these teams generate triggers; empty = every car (back-compat).
        self.tracked_teams = [str(t).lower() for t in live_cfg.get("tracked_teams", [])]
        log_path.parent.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------- team filter
    def _team_of(self, race: RaceData, driver: str) -> str:
        return (race.teams or {}).get(driver, "")

    def _tracked(self, race: RaceData, driver: str) -> bool:
        """True if the driver's team is in tracked_teams (case-insensitive substring,
        so 'Red Bull' matches 'Red Bull Racing'). Empty config tracks everyone."""
        if not self.tracked_teams:
            return True
        team = self._team_of(race, driver).lower()
        return bool(team) and any(t in team for t in self.tracked_teams)

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
        calls: list[dict] = []
        for model in self.runner.models():
            if model["name"] not in self.model_names:
                continue
            result = self.runner.call(dp, model, repeat_index=0)
            decision = result.decision
            if decision is None:
                verdict = "INVALID OUTPUT"
                draft = ""
                calls.append(
                    {
                        "model": model["name"],
                        "action": None,
                        "compound": None,
                        "confidence": None,
                        "rationale": "INVALID OUTPUT",
                    }
                )
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
                calls.append(
                    {
                        "model": model["name"],
                        "action": decision.action,
                        "compound": decision.compound,
                        "confidence": decision.confidence,
                        "rationale": decision.rationale,
                    }
                )
            line = (
                f"**Lap {lap} {driver}** [{dp_type}: {trigger}] state `{state_hash}` "
                f"- {model['name']} -> {verdict}{draft}"
            )
            self.console.print(line)
            self._log(line)

        # accumulate a structured record for the operations dashboard (most-recent-last)
        self.decisions.append(
            {
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "lap": lap,
                "driver": driver,
                "team": self._team_of(race, driver),
                "from_compound": state.focal.compound,
                "dp_type": dp_type,
                "trigger": trigger,
                "state_hash": state_hash,
                "team_action": dp.team_action,  # placeholder live; real action known post-race
                "calls": calls,
            }
        )
        del self.decisions[:-100]  # keep the last 100

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
        # Cars that may generate triggers = tracked-team cars in the field. Other cars
        # are still ingested (positions/gaps) but never produce model calls.
        tracked = [rec for rec in idx.order_at(max_lap) if self._tracked(race, rec.driver)]

        # Trigger 1: SC/VSC deployment (Type B). Detection is GLOBAL — the field status
        # is set by any car's incident — but we only fire for the tracked teams' cars.
        status = idx.field_status(max_lap)
        if status in ("SC", "VSC") and self.prev_status not in ("SC", "VSC"):
            self._log(f"**{status} deployed** (detected at lap {max_lap})")
            for rec in tracked:
                self._emit(race, rec.driver, decision_lap, "B", f"{status} deployed")
        self.prev_status = status

        # Trigger 2: rival pit detection (Type C). The pitting rival may be ANY car;
        # only a tracked-team focal car reacting to it generates a decision point.
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
                if not self._tracked(race, rec.driver):
                    continue
                if abs(rec.end_time_s - pit_rec.end_time_s) <= rival_gap:
                    self._emit(
                        race,
                        rec.driver,
                        decision_lap,
                        "C",
                        f"rival {stop.driver} pitted on lap {stop.lap}",
                    )

        # Trigger 3: tyre age crosses the window threshold (Type A proxy), tracked cars only.
        age_threshold = int(self.live_cfg.get("tyre_age_trigger", 18))
        for rec in tracked:
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

        # publish the structured snapshot the operations dashboard reads
        self._write_state(race, idx, max_lap, status)

    # ------------------------------------------------------------- dashboard state
    def _write_state(self, race: RaceData, idx: RaceIndex, lap: int, status: str) -> None:
        """Atomically write the current operations snapshot to state_path (best effort)."""
        if self.state_path is None:
            return
        try:
            order = idx.order_at(lap)[:10]
            leader_end = order[0].end_time_s if order else None
            standings = []
            for i, rec in enumerate(order, start=1):
                gap = None
                if leader_end is not None and rec.end_time_s is not None and i > 1:
                    gap = round(rec.end_time_s - leader_end, 1)
                standings.append(
                    {
                        "position": rec.position or i,
                        "driver": rec.driver,
                        "team": self._team_of(race, rec.driver),
                        "tracked": self._tracked(race, rec.driver),
                        "compound": rec.compound,
                        "tyre_age": rec.tyre_age,
                        "stint": rec.stint,
                        "gap_to_leader_s": gap,
                    }
                )
            # feed health: a lap should complete every ~90s; if the field stops
            # advancing for longer than the tolerance, the live feed has likely died.
            stale_tol = float(self.live_cfg.get("stale_data_tolerance_s", 180))
            since_lap = round(time.time() - self.last_progress_wall, 1)
            state = {
                "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "mode": self.mode_label,
                "race_id": race.race_id,
                "season": race.season,
                "track": race.track,
                "lap": lap,
                "total_laps": race.total_laps,
                "track_status": status,
                "weather": {
                    "air_temp_c": race.weather.air_temp_c,
                    "track_temp_c": race.weather.track_temp_c,
                    "rain": race.weather.rain,
                },
                "models": self.model_names,
                "standings": standings,
                "decisions": list(reversed(self.decisions[-30:])),  # most recent first
                # health signals the dashboard surfaces so a dead feed is visible
                "poll_seconds": float(self.live_cfg.get("poll_seconds", 45)),
                "seconds_since_lap_advance": since_lap,
                "stale_tolerance_s": stale_tol,
                "feed_stale": since_lap > stale_tol,
            }
            tmp = self.state_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
            os.replace(tmp, self.state_path)
        except Exception as exc:  # state is non-critical; never break the loop
            log.warning("live state write failed: %s", exc)

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


class ManualSource:
    """Fallback source for when the live feed dies mid-race.

    The operator hand-maintains a RaceData JSON file (same schema ingest produces);
    we re-read it each poll so the IDENTICAL LiveLoop keeps producing model calls from
    manually-entered state. Returns None (treated as 'no fresh data') if the file is
    missing or unparseable, so a half-written edit never crashes the loop."""

    def __init__(self, feed_path: Path, race_id: str):
        self.feed_path = feed_path
        self.race_id = race_id
        self._done = False

    def poll(self) -> Optional[RaceData]:
        try:
            if not self.feed_path.exists():
                return None
            return RaceData.model_validate_json(self.feed_path.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("manual feed read failed (%s); waiting for a valid edit", exc)
            return None

    def active(self) -> bool:
        return not self._done

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def _restrict_names(model_names: list[str], models_cfg: dict) -> list[str]:
    available = {m["name"] for m in models_cfg.get("models", [])}
    return [n for n in model_names if n in available]


def build_mock_runner(model_names: list[str]) -> tuple[Runner, list[str]]:
    """Mock-mode runner restricted to the configured live models."""
    run_cfg = load_config("run")
    models_cfg = load_config("models")
    return Runner(run_cfg, models_cfg, mock=True), _restrict_names(model_names, models_cfg)


def build_live_runner(model_names: list[str]) -> tuple[Runner, list[str]]:
    """Real-call runner restricted to the live models. Spend is still gated inside the
    Runner by ALLOW_SPEND=1 + OPENROUTER_API_KEY; the launcher checks those up front."""
    run_cfg = load_config("run")
    models_cfg = load_config("models")
    return Runner(run_cfg, models_cfg, mock=False), _restrict_names(model_names, models_cfg)
