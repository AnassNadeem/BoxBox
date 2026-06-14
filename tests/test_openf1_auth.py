"""Deterministic tests for OpenF1 OAuth2 token handling.

The refresh-before-expiry behaviour is the thing that silently breaks mid-race, so we
prove it with an injected clock and a fake token server — no network, no real sleeping.
"""

from __future__ import annotations

import json

import httpx
import pytest

from boxbox.data.openf1 import (
    DEFAULT_REFRESH_MARGIN_S,
    OpenF1Auth,
    OpenF1AuthError,
    OpenF1Client,
)


class _FakeResp:
    def __init__(self, status: int, payload: dict):
        self.status_code = status
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self) -> dict:
        return self._payload


class _FakeTokenServer:
    """Hands out tok-1, tok-2, ... and counts how often the token endpoint is hit."""

    def __init__(self, expires_in: str = "3600"):
        self.calls = 0
        self.expires_in = expires_in
        self.last_data: dict | None = None

    def post(self, url, data=None, headers=None):
        self.calls += 1
        self.last_data = data
        return _FakeResp(
            200,
            {
                "access_token": f"tok-{self.calls}",
                "token_type": "bearer",
                "expires_in": self.expires_in,
            },
        )


def _auth_with(server, now):
    return OpenF1Auth(
        "user", "pw", refresh_margin_s=DEFAULT_REFRESH_MARGIN_S, clock=lambda: now[0], client=server
    )


def test_first_token_is_fetched_and_posts_credentials_form():
    server = _FakeTokenServer()
    auth = _auth_with(server, [1000.0])
    assert auth.token() == "tok-1"
    assert server.calls == 1
    # credentials go in the form body, exactly the two documented fields
    assert server.last_data == {"username": "user", "password": "pw"}


def test_token_is_cached_until_refresh_margin():
    now = [1000.0]
    server = _FakeTokenServer()  # 3600s life, 600s margin -> refresh at t+3000
    auth = _auth_with(server, now)
    assert auth.token() == "tok-1"
    # 49 minutes later: still well inside the token's life, before the margin -> no refetch
    now[0] = 1000.0 + 49 * 60
    assert auth.token() == "tok-1"
    assert server.calls == 1


def test_token_refreshes_before_hard_expiry():
    now = [1000.0]
    server = _FakeTokenServer()
    auth = _auth_with(server, now)
    assert auth.token() == "tok-1"
    # 51 minutes in: past the 50 min refresh mark but BEFORE the 60 min hard expiry.
    now[0] = 1000.0 + 51 * 60
    assert auth.token() == "tok-2"  # refreshed proactively, not after dying
    assert server.calls == 2


def test_request_straddling_expiry_gets_a_fresh_token():
    """Simulate two requests bracketing the 50-min refresh point inside one race."""
    now = [0.0]
    server = _FakeTokenServer()
    auth = _auth_with(server, now)
    first = auth.token()  # t=0, e.g. just before lights out
    now[0] = 55 * 60  # ~lap 50, still racing; old token would have <5 min left
    second = auth.token()
    assert first == "tok-1"
    assert second == "tok-2"  # the straddling request transparently got a live token
    assert auth.expires_in() == pytest.approx(3600.0)  # fresh full hour again


def test_invalidate_forces_refetch():
    now = [0.0]
    server = _FakeTokenServer()
    auth = _auth_with(server, now)
    assert auth.token() == "tok-1"
    auth.invalidate()  # what a 401 triggers
    assert auth.token() == "tok-2"
    assert server.calls == 2


def test_missing_credentials_raise():
    with pytest.raises(OpenF1AuthError):
        OpenF1Auth("", "pw")


def test_non_200_token_response_raises_with_status_and_body():
    class _Boom:
        def post(self, *a, **k):
            return _FakeResp(403, {"detail": "bad credentials"})

    auth = OpenF1Auth("u", "p", client=_Boom())
    with pytest.raises(OpenF1AuthError) as ei:
        auth.token()
    assert "403" in str(ei.value)


def test_client_attaches_bearer_header_when_authed():
    """The GET path must carry Authorization: Bearer <token> when auth is present."""
    now = [0.0]
    server = _FakeTokenServer()
    auth = _auth_with(server, now)

    seen_headers: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return httpx.Response(200, json=[{"ok": True}])

    client = OpenF1Client(auth=auth)
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    out = client.get("sessions", year=2026)
    assert out == [{"ok": True}]
    assert seen_headers.get("authorization") == "Bearer tok-1"


def test_anonymous_client_sends_no_auth_header():
    seen_headers: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.update(request.headers)
        return httpx.Response(200, json=[])

    client = OpenF1Client(auth=None)
    client._client = httpx.Client(transport=httpx.MockTransport(handler))
    client.get("sessions", year=2026)
    assert "authorization" not in {k.lower() for k in seen_headers}
