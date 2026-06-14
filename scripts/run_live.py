"""BOXBOX live launcher - the one-command start for race day (2026 Spanish GP, Barcelona).

Three source modes (pick one):
  --live                 real authed OpenF1 stream + REAL model calls (race morning)
  --replay RACE_ID       replay a processed race through the identical loop (test anytime)
  --manual               read hand-maintained RaceData JSON each poll (feed-down fallback)

Model spend:
  * --replay always uses MOCK models (never spend on replayed data).
  * --live / --manual use REAL models, which require ALLOW_SPEND=1 + OPENROUTER_API_KEY.
    Add --mock to run those source modes with mock models (no spend) for a pre-race smoke.

Safety: in --live the launcher refuses to start unless session_key=latest is the Barcelona
RACE (so you cannot accidentally launch against Qualifying or the Madrid round). Override
for a pre-race no-spend smoke with --allow-non-race.

Examples:
  python scripts/run_live.py --replay 2026-monaco --speed 60      # test tonight (mock)
  python scripts/run_live.py --live --dashboard                   # RACE DAY
  python scripts/run_live.py --live --mock --allow-non-race       # pre-race smoke, no spend
"""

from __future__ import annotations

import argparse
import functools
import http.server
import logging
import os
import sys
import threading
from pathlib import Path

from dotenv import load_dotenv
from rich.console import Console

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
load_dotenv(REPO / ".env")

from boxbox.config import load_config  # noqa: E402
from boxbox.data.ingest import load_race  # noqa: E402
from boxbox.live.live_runner import (  # noqa: E402
    LIVE_STATE,
    LiveLoop,
    ManualSource,
    build_live_runner,
    build_mock_runner,
)
from boxbox.live.replay import ReplaySource, normalize_race_id  # noqa: E402

console = Console()

# Race-day target. "barcelona" is unambiguous; bare "spain" collides with the Madrid round.
LIVE_YEAR = 2026
LIVE_EVENT = "barcelona"
LIVE_RACE_ID = "2026-barcelona"
DASHBOARD_DIR = REPO / "site" / "live"


def die(msg: str) -> "int":
    console.print(f"[bold red]ABORT:[/bold red] {msg}")
    return 2


def assert_live_is_barcelona_race(allow_non_race: bool) -> bool:
    """Guard: session_key=latest must be the Barcelona RACE. Returns True to proceed."""
    from boxbox.data.openf1 import OpenF1Client, auth_from_env

    auth = auth_from_env()
    if auth is None:
        console.print(die("OPENF1_USERNAME/OPENF1_PASSWORD missing from .env"))
        return False
    client = OpenF1Client(auth=auth)
    try:
        latest = client.get("sessions", session_key="latest")
    finally:
        client.close()
    if not latest:
        if allow_non_race:
            console.print(
                "[yellow]latest returned no session; proceeding (--allow-non-race)[/yellow]"
            )
            return True
        console.print(die("session_key=latest returned nothing; live window not open yet"))
        return False

    s = latest[-1]
    name, stype = str(s.get("session_name", "")), str(s.get("session_type", ""))
    loc = str(s.get("location", ""))
    is_race = name.lower() == "race" or stype.lower() == "race"
    is_barcelona = "barcelona" in loc.lower()

    if is_race and is_barcelona:
        console.print(
            f"[green]Live session confirmed:[/green] {name} @ {loc} (key {s.get('session_key')})"
        )
        return True

    why = (
        f"latest session is {name!r} @ {loc!r} (key {s.get('session_key')}), "
        f"not the Barcelona Race."
    )
    if not is_race:
        why += " Live data opens 30 min before lights-out (12:30 UTC); wait until then."
    if is_race and not is_barcelona:
        why += " This looks like a different race (Madrid?) - do NOT launch against it."
    if allow_non_race:
        console.print(f"[yellow]{why} Proceeding anyway (--allow-non-race).[/yellow]")
        return True
    console.print(die(why))
    return False


def start_dashboard(port: int) -> None:
    """Serve the static dashboard + the live state JSON in a background thread."""

    class Handler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            if self.path.split("?")[0] in ("/live_state.json", "/outputs/live_state.json"):
                if LIVE_STATE.exists():
                    body = LIVE_STATE.read_bytes()
                else:
                    body = b'{"status": "waiting for first poll"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return
            return super().do_GET()

        def log_message(self, *a):  # silence per-request noise
            return

    handler = functools.partial(Handler, directory=str(DASHBOARD_DIR))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    console.print(f"[bold cyan]Dashboard:[/bold cyan] http://127.0.0.1:{port}/  (Ctrl-C to stop)")


def run_check() -> int:
    """Race-morning preflight: auth + latest-session resolution. Prints GO/NO-GO and
    exits (0 = GO, 2 = NO-GO). No loop, no model calls, no spend."""
    from boxbox.data.openf1 import OpenF1Client, auth_from_env

    console.print("[bold]=== BOXBOX race-morning check ===[/bold]")

    auth = auth_from_env()
    if auth is None:
        console.print("[red][NO-GO] auth:[/red] OPENF1_USERNAME/OPENF1_PASSWORD missing from .env")
        return _verdict(False, "set OpenF1 credentials in .env")
    try:
        auth.token()
        console.print(
            f"[green][GO]   auth:[/green] token acquired, valid ~{auth.expires_in():.0f}s"
        )
    except Exception as exc:
        console.print(f"[red][NO-GO] auth:[/red] token fetch failed: {exc}")
        return _verdict(False, "fix OpenF1 credentials/subscription in .env")

    client = OpenF1Client(auth=auth)
    try:
        latest = client.get("sessions", session_key="latest")
    except Exception as exc:
        console.print(f"[red][NO-GO] session:[/red] latest lookup failed: {exc}")
        return _verdict(False, "OpenF1 sessions endpoint error")
    finally:
        client.close()

    session_go = False
    reason = ""
    if not latest:
        console.print(
            "[yellow][WAIT] session:[/yellow] latest returned nothing - live window not open yet"
        )
        reason = "wait for the live window (opens ~30 min before lights-out, 12:30 UTC)"
    else:
        s = latest[-1]
        name = str(s.get("session_name", "")) or str(s.get("session_type", ""))
        loc = str(s.get("location", ""))
        key = s.get("session_key")
        is_race = name.lower() == "race" or str(s.get("session_type", "")).lower() == "race"
        is_barca = "barcelona" in loc.lower()
        if is_race and is_barca:
            console.print(f"[green][GO]   session:[/green] latest is the Race @ {loc} (key {key})")
            session_go = True
        elif is_barca and not is_race:
            console.print(
                f"[yellow][WAIT] session:[/yellow] latest is {name} @ {loc} (key {key}); "
                "live data opens 30 min before lights-out (12:30 UTC)"
            )
            reason = (
                "Barcelona weekend confirmed but race session not live yet - re-run after 12:30 UTC"
            )
        elif is_race and not is_barca:
            console.print(
                f"[red][NO-GO] session:[/red] latest Race is @ {loc} (key {key}), NOT Barcelona"
            )
            reason = f"latest race is {loc}, not Barcelona - do NOT launch against it"
        else:
            console.print(
                f"[yellow][WAIT] session:[/yellow] latest is {name} @ {loc} - not the Barcelona race"
            )
            reason = "the Barcelona race is not the active session yet"

    # spend advisory (not a hard gate - you may intend a --mock run)
    if os.environ.get("ALLOW_SPEND") == "1" and os.environ.get("OPENROUTER_API_KEY"):
        console.print(
            "[green][GO]   spend:[/green] ALLOW_SPEND=1 + key present - real models will run"
        )
    else:
        console.print(
            "[yellow][warn] spend:[/yellow] ALLOW_SPEND!=1 - real models will refuse; "
            "set ALLOW_SPEND=1 in .env for the scored run (or launch with --mock)"
        )

    return _verdict(session_go, reason or "clear")


def _verdict(go: bool, reason: str) -> int:
    console.print("[dim]" + "-" * 40 + "[/dim]")
    if go:
        console.print(
            "[bold green]GO[/bold green] - clear to launch:  "
            "python scripts/run_live.py --live --dashboard"
        )
        return 0
    console.print(f"[bold red]NO-GO[/bold red] - {reason}")
    return 2


def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="preflight GO/NO-GO, no loop, no spend")
    mode.add_argument("--live", action="store_true", help="real authed OpenF1 stream (race day)")
    mode.add_argument(
        "--replay", metavar="RACE_ID", help="replay a processed race, e.g. 2026-monaco"
    )
    mode.add_argument("--manual", action="store_true", help="hand-maintained JSON feed fallback")
    p.add_argument("--mock", action="store_true", help="mock models (no spend) in --live/--manual")
    p.add_argument("--speed", type=float, default=60.0, help="replay speed multiplier")
    p.add_argument(
        "--manual-file",
        default=str(REPO / "outputs" / "manual_feed.json"),
        help="RaceData JSON the operator edits in --manual mode",
    )
    p.add_argument(
        "--allow-non-race", action="store_true", help="bypass the live Race guard (smoke)"
    )
    p.add_argument("--dashboard", action="store_true", help="serve the operations dashboard")
    p.add_argument("--port", type=int, default=8011, help="dashboard port")
    args = p.parse_args()

    if args.check:
        return run_check()

    # ---- decide model mode (mock vs real) and enforce the spend gate up front --------
    use_mock = True if args.replay else args.mock
    if not use_mock:
        if os.environ.get("ALLOW_SPEND") != "1" or not os.environ.get("OPENROUTER_API_KEY"):
            return die(
                "real model calls need ALLOW_SPEND=1 and OPENROUTER_API_KEY in .env. "
                "Use --mock for a no-spend run."
            )

    live_models = load_config("models").get("live_models", [])
    runner, names = (build_mock_runner if use_mock else build_live_runner)(live_models)
    if not names:
        return die("no live models matched config/models.yaml (live_models)")
    console.print(
        f"[bold]Models:[/bold] {names}  ({'MOCK - no spend' if use_mock else 'REAL - billing on'})"
    )

    extraction_cfg = load_config("extraction")
    live_cfg = load_config("run").get("live", {})

    # ---- build the source per mode ---------------------------------------------------
    if args.replay:
        race_id = normalize_race_id(args.replay)
        race = load_race(race_id)
        source = ReplaySource(race, speed=args.speed)
        mode_label = f"replay {race_id} @{args.speed:g}x"
        console.print(
            f"[bold]Source:[/bold] REPLAY {race_id} ({race.total_laps} laps) at {args.speed:g}x"
        )
    elif args.manual:
        feed = Path(args.manual_file)
        source = ManualSource(feed, LIVE_RACE_ID)
        mode_label = "manual"
        console.print(
            f"[bold]Source:[/bold] MANUAL feed {feed} (edit this file to advance the race)"
        )
    else:  # --live
        if not assert_live_is_barcelona_race(args.allow_non_race):
            return 2
        from boxbox.live.live_runner import OpenF1LiveSource

        source = OpenF1LiveSource(
            LIVE_YEAR, LIVE_EVENT, LIVE_RACE_ID, total_laps=live_cfg.get("total_laps")
        )
        mode_label = "live"
        console.print(
            f"[bold]Source:[/bold] LIVE OpenF1 - {LIVE_RACE_ID} "
            f"(session_key {source.session.get('session_key')})"
        )

    loop = LiveLoop(source, runner, names, live_cfg, extraction_cfg, console=console)
    loop.mode_label = mode_label

    if args.dashboard:
        start_dashboard(args.port)

    try:
        loop.run()
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped by operator.[/yellow]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
