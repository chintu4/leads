from fastapi.testclient import TestClient
import os
import types
import json

from src.handlers import auth_google
import main

client = TestClient(main.app)


def test_cors_allows_github_origin():
    origin = "https://chintu4.github.io"
    r = client.get("/", headers={"Origin": origin})
    assert r.status_code == 200
    # FastAPI CORSMiddleware should echo the allowed origin
    assert r.headers.get("access-control-allow-origin") == origin


def test_preflight_allows_post():
    origin = "https://chintu4.github.io"
    headers = {
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type",
    }
    r = client.options("/scrape", headers=headers)
    assert r.status_code in (200, 204)
    assert r.headers.get("access-control-allow-origin") == origin


class DummyResp:
    def __init__(self, status_code, json_obj):
        self.status_code = status_code
        self._json = json_obj

    def json(self):
        return self._json


def test_oauth_callback_sets_cookie(monkeypatch):
    # Simulate environment variables and token/userinfo responses
    os.environ["GOOGLE_CLIENT_ID"] = "x"
    os.environ["GOOGLE_CLIENT_SECRET"] = "y"
    os.environ["GOOGLE_OAUTH_REDIRECT_URI"] = "https://leads.example.com/auth/google/callback"

    # Prepare a valid state
    state = "teststate123"
    auth_google._oauth_states[state] = True

    # Mock token exchange
    def fake_post(url, data=None, timeout=None):
        return DummyResp(200, {"id_token": "idt", "access_token": "acc"})

    def fake_get(url, headers=None, timeout=None):
        return DummyResp(200, {"email": "u@example.com", "name": "User"})

    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("requests.get", fake_get)

    r = client.get(f"/auth/google/callback?code=somecode&state={state}")
    assert r.status_code == 200
    set_cookie = r.headers.get("set-cookie", "")
    assert "session=" in set_cookie
    # Ensure cookie is marked Secure and SameSite=None for cross-site usage (case-insensitive)
    sc = set_cookie.lower()
    assert "samesite=none" in sc
    assert "secure" in sc
