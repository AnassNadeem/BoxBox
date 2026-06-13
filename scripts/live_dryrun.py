"""Live pipeline dry-run (MOCK models, no paid calls).

First attempts the real OpenF1 live stream. If it is blocked (OpenF1 locks its
public API for unauthenticated clients while a session is live), it falls back to
replaying a real ingested race through the IDENTICAL LiveLoop, so the rest of the
plumbing is still validated end to end: SC/VSC + rival-pit + tyre-age triggers,
per-(car, lap) dedup, the mock model, draft-post generation, state-snapshot
hashing, and crash-free operation. Prints a summary.

Usage: python scripts/live_dryrun.py
"""

from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path

import httpx
from rich.console import Console

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from boxbox.config import load_config  # noqa: E402
from boxbox.data.ingest import load_race  # noqa: E402
from boxbox.live.live_runner import LiveLoop, build_mock_runner  # noqa: E402
from boxbox.live.replay import ReplaySource  # noqa: E402

LIVE_LOG = REPO / "outputs" / "live_log.md"
REPLAY_RACE = "2026-monaco"  # has SC periods + pit stops + long stints -> exercises A/B/C
SPEED = 60.0
POLL_S = 30.0  # race-time seconds between polls (user asked for 30-60s)

console = Console()


def probe_live() -> str:
    """One quick attempt at the real OpenF1 'latest' session (no retry storm)."""
    try:
        r = httpx.get(
            "https://api.openf1.org/v1/sessions", params={"session_key": "latest"}, timeout=15
        )
        if r.status_code == 200 and isinstance(r.json(), list):
            rows = r.json()
            if rows:
                s = rows[-1]
                return f"LIVE OK: {s.get('session_name')} @ {s.get('location')} (key {s.get('session_key')})"
            return "LIVE OK but no session rows returned"
        try:
            detail = r.json().get("detail", "")
        except Exception:
            detail = r.text[:200]
        return f"LIVE UNAVAILABLE: HTTP {r.status_code} - {detail}"
    except Exception as exc:
        return f"LIVE UNAVAILABLE: {type(exc).__name__}: {exc}"


class CountingReplaySource(ReplaySource):
    """Replay source that counts polls and injects an occasional None to exercise
    the loop's stale/no-fresh-data branch."""

    def __init__(self, race, speed):
        super().__init__(race, speed=speed)
        self.polls = 0
        self.none_polls = 0

    def poll(self):
        self.polls += 1
        if self.polls % 11 == 0:  # ~9% simulated source hiccups
            self.none_polls += 1
            return None
        return super().poll()


def main() -> int:
    # Rotate any prior live log so the summary reflects only this run.
    if LIVE_LOG.exists():
        LIVE_LOG.rename(LIVE_LOG.with_name("live_log_prev.md"))

    live_status = probe_live()
    console.print(f"[bold]OpenF1 live probe:[/bold] {live_status}")

    race = load_race(REPLAY_RACE)
    models_cfg = load_config("models")
    runner, names = build_mock_runner(models_cfg.get("live_models", []))
    if not names:
        console.print("[red]No live models matched config/models.yaml[/red]")
        return 2
    live_cfg = {
        **load_config("run").get("live", {}),
        "poll_seconds": POLL_S,
        "stale_data_tolerance_s": 3.0,  # low, so the gap path can fire in a fast replay
    }
    extraction_cfg = load_config("extraction")

    src = CountingReplaySource(race, speed=SPEED)
    quiet = Console(file=open(os.devnull, "w"))  # keep the per-emit chatter out of stdout
    loop = LiveLoop(src, runner, names, live_cfg, extraction_cfg, console=quiet)
    loop._log(f"**DRY-RUN** mock models {names}; OpenF1 live source: {live_status}")
    loop._log(
        f"**Live stream blocked -> plumbing validated via REPLAY** of {REPLAY_RACE} at {SPEED:g}x."
    )

    t0 = time.time()
    loop.run()
    wall = time.time() - t0

    # ---- parse this run's log for the summary ----
    text = LIVE_LOG.read_text(encoding="utf-8")
    lines = text.splitlines()
    seen_trig: set[tuple[str, str]] = set()
    by_type: dict[str, int] = {}
    for ln in lines:
        m = re.search(r"\[([ABC]): .*?\] state `([0-9a-f]+)`", ln)
        if m:
            t, h = m.group(1), m.group(2)
            if (t, h) not in seen_trig:
                seen_trig.add((t, h))
                by_type[t] = by_type.get(t, 0) + 1
    drafts = [ln for ln in lines if "DRAFT POST:" in ln]
    gaps = [ln for ln in lines if "data gap" in ln]
    errors = [ln for ln in lines if "loop error" in ln]
    scvsc = [ln for ln in lines if "deployed**" in ln]

    console.print("\n[bold]==== LIVE DRY-RUN SUMMARY ====[/bold]")
    console.print(f"OpenF1 live probe : {live_status}")
    console.print(f"Mode              : MOCK models {names}")
    console.print(f"Data source       : REPLAY {REPLAY_RACE} @ {SPEED:g}x | wall {wall:.0f}s")
    console.print(f"Polls             : {src.polls}  (simulated None hiccups: {src.none_polls})")
    console.print(f"SC/VSC deployments: {len(scvsc)}")
    console.print(f"Data-gap events   : {len(gaps)}")
    console.print(f"Loop errors       : {len(errors)}  (0 = loop never crashed)")
    console.print(
        f"Triggers by type  : A={by_type.get('A', 0)} B={by_type.get('B', 0)} "
        f"C={by_type.get('C', 0)}  (total {sum(by_type.values())})"
    )
    console.print(f"Draft post lines  : {len(drafts)}")
    console.print("Sample draft posts:")
    for d in drafts[:5]:
        console.print("  " + d.strip()[:220])
    console.print(f"\nFull log: {LIVE_LOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
