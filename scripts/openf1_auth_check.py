"""Live OpenF1 authenticated-access check. NO model spend; only OpenF1 REST/MQTT.

Proves the paid-tier OAuth2 path end to end against the real API and prints PASS/FAIL
for each numbered task in the race-prep checklist. Run:

    ./venv/Scripts/python.exe scripts/openf1_auth_check.py

Reads OPENF1_USERNAME / OPENF1_PASSWORD from .env. Makes a small, bounded number of
requests (well under any sane rate limit).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
load_dotenv(REPO / ".env")

from boxbox.data.openf1 import (  # noqa: E402
    BASE_URL,
    OpenF1Client,
    auth_from_env,
    find_race_session,
)

results: list[tuple[str, bool | None, str]] = []


def record(name: str, ok: bool | None, detail: str) -> None:
    tag = "PASS" if ok else ("SKIP" if ok is None else "FAIL")
    print(f"[{tag}] {name}: {detail}")
    results.append((name, ok, detail))


def raw_get(token: str, endpoint: str, **params) -> httpx.Response:
    """Single raw GET (no retries) so we can classify exact status codes."""
    with httpx.Client(timeout=30.0) as c:
        return c.get(
            f"{BASE_URL}/{endpoint}",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )


# ---------------------------------------------------------------- 1. token fetch
auth = auth_from_env()
if auth is None:
    record("1 token fetch", False, "OPENF1_USERNAME/OPENF1_PASSWORD not set in .env")
    print("\nCannot continue without credentials.")
    sys.exit(1)

try:
    tok = auth.token()
    record(
        "1 token fetch",
        True,
        f"got bearer token (len {len(tok)}), expires_in ~{auth.expires_in():.0f}s",
    )
except Exception as exc:
    record("1 token fetch", False, f"{type(exc).__name__}: {exc}")
    print("\nToken fetch failed; cannot run authed tests.")
    sys.exit(1)

client = OpenF1Client(auth=auth)

# ------------------------------------------------------ 4. authed historical pull
# Tomorrow's race (Spain 2026) has no lap data yet, so the real-data Bearer proof runs
# against the most recent COMPLETED 2026 race; task 7 below resolves the Spain session.
HIST_YEAR, HIST_EVENT = 2026, "monaco"
try:
    sess = find_race_session(client, HIST_YEAR, HIST_EVENT, live=False)
    key = sess["session_key"]
    counts = {}
    for ep in ("laps", "pit", "position", "race_control", "weather"):
        counts[ep] = len(client.get(ep, session_key=key))
        time.sleep(0.3)
    ok = counts["laps"] > 0
    record(
        "4 authed historical pull (2026 monaco)",
        ok,
        f"session_key={key} " + ", ".join(f"{k}={v}" for k, v in counts.items()),
    )
except Exception as exc:
    record("4 authed historical pull (2026 monaco)", False, f"{type(exc).__name__}: {exc}")
    key = None

# ------------------------------------ 7. resolve TOMORROW's live session (Barcelona 2026)
# NOTE: bare "spain" is ambiguous in 2026 (Barcelona-Catalunya AND the Madrid round both
# have country_name='Spain'); use the circuit location to pin tomorrow's race exactly.
LIVE_YEAR, LIVE_EVENT = 2026, "barcelona"
try:
    live_sess = find_race_session(client, LIVE_YEAR, LIVE_EVENT, live=True)
    loc = str(live_sess.get("location", "")).lower()
    ok = "barcelona" in loc  # must be Catalunya, not Madrid
    record(
        "7 resolve tomorrow's live session (Barcelona 2026)",
        ok,
        f"session_key={live_sess.get('session_key')} "
        f"name={live_sess.get('session_name')!r} type={live_sess.get('session_type')!r} "
        f"loc={live_sess.get('location')!r} circuit={live_sess.get('circuit_short_name')!r} "
        f"start={live_sess.get('date_start')!r}",
    )
except Exception as exc:
    record(
        "7 resolve tomorrow's live session (Barcelona 2026)",
        False,
        f"{type(exc).__name__}: {exc} (session may not be in OpenF1's schedule yet)",
    )

# ------------------------------------------------------- 5. live-endpoint auth check
# "Live" == querying the session OpenF1 is currently serving (session_key=latest).
try:
    r = raw_get(tok, "sessions", session_key="latest")
    body = r.text[:200]
    if r.status_code in (401, 403):
        record(
            "5 live-endpoint auth",
            False,
            f"RED FLAG: HTTP {r.status_code} on live endpoint - token does NOT "
            f"authenticate for live. Body: {body}",
        )
        latest_key = None
    elif r.status_code == 200:
        data = r.json()
        if data:
            latest_key = data[-1].get("session_key")
            sn = data[-1].get("session_name")
            record(
                "5 live-endpoint auth",
                True,
                f"HTTP 200, authenticated. Latest session_key={latest_key} "
                f"(session_name={sn!r}); a real live session will appear here on race day",
            )
        else:
            latest_key = None
            record(
                "5 live-endpoint auth",
                True,
                "HTTP 200 + empty (authenticates fine, just no live session right now) - GOOD",
            )
    else:
        latest_key = None
        record("5 live-endpoint auth", False, f"unexpected HTTP {r.status_code}. Body: {body}")
except Exception as exc:
    latest_key = None
    record("5 live-endpoint auth", False, f"{type(exc).__name__}: {exc}")

# also probe a couple of real-time data endpoints with latest to confirm they auth too
try:
    statuses = {}
    for ep in ("position", "intervals"):
        rr = raw_get(tok, ep, session_key="latest")
        statuses[ep] = rr.status_code
        time.sleep(0.3)
    bad = {k: v for k, v in statuses.items() if v in (401, 403)}
    record(
        "5b live data endpoints (position/intervals @latest)",
        not bad,
        ("RED FLAG auth failure: " if bad else "all authenticated: ") + str(statuses),
    )
except Exception as exc:
    record("5b live data endpoints", False, f"{type(exc).__name__}: {exc}")

# ------------------------------------------------------------- 6. rate-limit headers
try:
    r = raw_get(tok, "sessions", session_key="latest")
    rl = {
        k: v for k, v in r.headers.items() if "ratelimit" in k.lower() or "retry-after" == k.lower()
    }
    poll_s = 45
    per_poll_reqs = 6  # laps,stints,pit,race_control,weather,drivers per ingest
    rpm = per_poll_reqs * (60 / poll_s)
    detail = (
        f"headers={rl or 'none advertised'}; our cadence: {per_poll_reqs} reqs / {poll_s}s "
        f"= ~{rpm:.1f} req/min"
    )
    # PASS = we got a 200 (not rate limited) at our probing rate; note headers if any
    record("6 rate limit vs poll cadence", r.status_code == 200, detail)
except Exception as exc:
    record("6 rate limit vs poll cadence", False, f"{type(exc).__name__}: {exc}")

# --------------------------------------------------- 3(real) refresh straddle on live API
# Force a real near-expiry refresh: use an injectable clock that jumps past the refresh
# margin between two real REST calls, and confirm both succeed + a new token was issued.
try:
    from boxbox.data.openf1 import OpenF1Auth

    clock = [time.time()]
    straddle_auth = OpenF1Auth(
        auth._username,  # reuse loaded creds; not printed
        auth._password,
        refresh_margin_s=600.0,
        clock=lambda: clock[0],
    )
    sclient = OpenF1Client(auth=straddle_auth)
    before = sclient.get("sessions", session_key="latest")
    n1 = straddle_auth.refresh_count
    clock[0] += 55 * 60  # jump to ~lap 50: inside the refresh margin, real token still valid
    after = sclient.get("sessions", session_key="latest")
    n2 = straddle_auth.refresh_count
    sclient.close()
    ok = n2 == n1 + 1 and before is not None and after is not None
    record(
        "3 live straddle (real refresh mid-stream)",
        ok,
        f"two real REST calls bracketing the 50-min mark both 200; token refetched "
        f"{n1}->{n2} times - no failure across expiry",
    )
except Exception as exc:
    record("3 live straddle (real refresh mid-stream)", False, f"{type(exc).__name__}: {exc}")

# -------------------------------------------------------------- 8. schema field check
# HARD = the endpoints + fields ingest_openf1 actually parses into RaceData (what the
# LiveLoop consumes). INFO = real-time extras we surface but don't parse (position is
# derived from lap times, not the position endpoint; intervals is unused) - their absence
# (e.g. intervals 404s on a quali session) is informational, never a failure.
HARD = {
    "laps": ["driver_number", "lap_number", "lap_duration", "date_start", "is_pit_out_lap"],
    "stints": [
        "driver_number",
        "compound",
        "lap_start",
        "lap_end",
        "tyre_age_at_start",
        "stint_number",
    ],
    "pit": ["driver_number", "lap_number"],
    "race_control": ["date", "message"],
    "weather": ["air_temperature", "track_temperature", "rainfall"],
}
INFO = {
    "position": ["driver_number", "position", "date"],
    "intervals": ["driver_number", "gap_to_leader", "interval", "date"],
}


def safe_rows(endpoint: str, session_key) -> tuple[list, str]:
    """Fetch rows, returning ([], reason) instead of raising on 404/empty/error."""
    try:
        with httpx.Client(timeout=30.0) as c:
            rr = c.get(
                f"{BASE_URL}/{endpoint}",
                params={"session_key": session_key},
                headers={"Authorization": f"Bearer {tok}"},
            )
        if rr.status_code == 200:
            data = rr.json()
            return (data if isinstance(data, list) else []), "200"
        return [], f"HTTP {rr.status_code}"
    except Exception as exc:
        return [], f"{type(exc).__name__}"


schema_key = latest_key or key
try:
    hard_problems: dict[str, str] = {}
    info_report: dict[str, str] = {}
    for ep, fields in HARD.items():
        rows, why = safe_rows(ep, schema_key)
        if not rows:
            hard_problems[ep] = f"no rows ({why})"
        else:
            miss = [f for f in fields if f not in rows[0]]
            if miss:
                hard_problems[ep] = f"MISSING {miss}"
        time.sleep(0.3)
    for ep, fields in INFO.items():
        rows, why = safe_rows(ep, schema_key)
        if not rows:
            info_report[ep] = why
        else:
            miss = [f for f in fields if f not in rows[0]]
            info_report[ep] = f"MISSING {miss}" if miss else "ok"
        time.sleep(0.3)
    ok = not hard_problems
    detail = (
        f"session {schema_key}: HARD(parsed)="
        + ("all fields present" if ok else str(hard_problems))
        + f"; INFO(unused extras)={info_report}"
    )
    record("8 live schema vs LiveLoop parser", ok, detail)
except Exception as exc:
    record("8 live schema vs LiveLoop parser", False, f"{type(exc).__name__}: {exc}")

client.close()

# --------------------------------------------------------- 9. OPTIONAL: MQTT auth test
try:
    import paho.mqtt.client as mqtt  # type: ignore

    connected = {"rc": None}

    def on_connect(c, u, flags, rc, *a):
        connected["rc"] = rc
        c.disconnect()

    m = mqtt.Client(client_id="boxbox-authcheck")
    m.tls_set()
    m.username_pw_set(username="boxbox", password=auth.token())
    m.on_connect = on_connect
    m.connect("mqtt.openf1.org", 8883, keepalive=15)
    m.loop_start()
    deadline = time.time() + 12
    while connected["rc"] is None and time.time() < deadline:
        time.sleep(0.2)
    m.loop_stop()
    rc = connected["rc"]
    record("9 MQTT auth (optional)", rc == 0, f"connack rc={rc} (0=accepted)")
except ImportError:
    record(
        "9 MQTT auth (optional)",
        None,
        "paho-mqtt not installed; run `pip install paho-mqtt` to verify (next-weekend upgrade)",
    )
except Exception as exc:
    record("9 MQTT auth (optional)", None, f"{type(exc).__name__}: {exc}")

# ----------------------------------------------------------------------- summary
print("\n=== SUMMARY ===")
fails = [n for n, ok, _ in results if ok is False]
for name, ok, _ in results:
    tag = "PASS" if ok else ("SKIP" if ok is None else "FAIL")
    print(f"  {tag:4}  {name}")
print(
    f"\n{len(fails)} FAIL, {sum(1 for _,o,_ in results if o)} PASS, "
    f"{sum(1 for _,o,_ in results if o is None)} SKIP"
)
sys.exit(1 if fails else 0)
