"""Replay a historic race through the live loop at Nx speed.

The loop cannot tell it is a replay: ReplaySource serves ever-growing RaceData
snapshots truncated to a scaled race clock and owns sleep(), which it shortens
by the speed factor.

Usage: python -m boxbox.live.replay --race monaco-2026 --speed 60 --mock
"""

from __future__ import annotations

import argparse
import logging
import time
from typing import Optional

from rich.console import Console

from boxbox.config import load_config
from boxbox.data.ingest import load_race
from boxbox.data.schemas import RaceData
from boxbox.live.live_runner import LiveLoop, build_mock_runner

log = logging.getLogger(__name__)


class ReplaySource:
    """LiveSource over a processed historic race, time-scaled."""

    def __init__(self, race: RaceData, speed: float = 60.0):
        self._race = race
        self._speed = max(speed, 0.01)
        self._t0 = time.monotonic()
        end_times = [r.end_time_s for r in race.laps if r.end_time_s is not None]
        start_times = [r.start_time_s for r in race.laps if r.start_time_s is not None]
        self._clock_offset = min(start_times) if start_times else 0.0
        self._end_clock = (max(end_times) if end_times else 0.0) + 120.0

    def _race_clock(self) -> float:
        return self._clock_offset + (time.monotonic() - self._t0) * self._speed

    def poll(self) -> Optional[RaceData]:
        clock = self._race_clock()
        visible = [r for r in self._race.laps if r.end_time_s is not None and r.end_time_s <= clock]
        visible_keys = {(r.driver, r.lap_number) for r in visible}
        stops = [s for s in self._race.pit_stops if (s.driver, s.lap) in visible_keys]
        return self._race.model_copy(update={"laps": visible, "pit_stops": stops})

    def active(self) -> bool:
        return self._race_clock() <= self._end_clock

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds / self._speed)


def normalize_race_id(raw: str) -> str:
    """Accept both '2026-monaco' and 'monaco-2026'."""
    parts = raw.split("-")
    if len(parts) == 2 and parts[1].isdigit():
        return f"{parts[1]}-{parts[0]}"
    return raw


def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--race", required=True, help="race id, e.g. monaco-2026")
    parser.add_argument("--speed", type=float, default=60.0)
    parser.add_argument(
        "--mock",
        action="store_true",
        default=True,
        help="mock model calls (the only mode wired tonight)",
    )
    args = parser.parse_args()

    race_id = normalize_race_id(args.race)
    race = load_race(race_id)
    console = Console()
    console.print(
        f"[bold]Replaying {race_id}[/bold] at {args.speed:g}x "
        f"({race.total_laps} laps, {len(race.laps)} lap records)"
    )

    models_cfg = load_config("models")
    live_models = models_cfg.get("live_models", [])
    runner, names = build_mock_runner(live_models)
    if not names:
        console.print("[red]No live models matched config/models.yaml[/red]")
        return 2

    live_cfg = load_config("run").get("live", {})
    extraction_cfg = load_config("extraction")
    loop = LiveLoop(
        source=ReplaySource(race, speed=args.speed),
        runner=runner,
        model_names=names,
        live_cfg=live_cfg,
        extraction_cfg=extraction_cfg,
        console=console,
    )
    loop.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
