from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import RedirectResponse, HTMLResponse
import os
import uuid
import requests
from urllib.parse import urlencode

router = APIRouter()

# Simple in-memory session and state stores for demo purposes
_oauth_states: dict = {}
_sessions: dict = {}

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


@router.get("/auth/google")
def start_google_auth():
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    redirect_uri = os.getenv("GOOGLE_OAUTH_REDIRECT_URI")
    if not client_id or not redirect_uri:
        # Return a friendly HTML page in development explaining how to configure Google OAuth
        notes = "<p>Please set the following environment variables: <code>GOOGLE_CLIENT_ID</code>, <code>GOOGLE_CLIENT_SECRET</code>, and <code>GOOGLE_OAUTH_REDIRECT_URI</code>.\n" \
                "Register your redirect URI in Google Cloud Console and ensure it matches exactly.</p>"
        html = f"<html><body><h3>Google OAuth not configured</h3>{notes}</body></html>"
        return HTMLResponse(content=html, status_code=500) 

    state = uuid.uuid4().hex
    _oauth_states[state] = True

    params = {
        "client_id": client_id,
        "response_type": "code",
        "scope": "openid email profile",
        "redirect_uri": redirect_uri,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }

    url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    return RedirectResponse(url)


@router.get("/auth/google/callback")
def google_callback(request: Request, code: str | None = None, state: str | None = None):
    # Build a small HTML page to post a message back to the opener window and close the popup
    if not code or not state:
        html = "<html><body><h3>Missing code or state</h3></body></html>"
        return HTMLResponse(content=html, status_code=400)

    if state not in _oauth_states:
        html = "<html><body><h3>Invalid state</h3></body></html>"
        return HTMLResponse(content=html, status_code=400)

    # Exchange code for tokens
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_OAUTH_REDIRECT_URI")
    if not client_secret or not client_id or not redirect_uri:
        html = "<html><body><h3>Server misconfigured for Google OAuth</h3></body></html>"
        return HTMLResponse(content=html, status_code=500)

    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    token_resp = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=10)
    if token_resp.status_code != 200:
        html = f"<html><body><h3>Failed to obtain tokens: {token_resp.text}</h3></body></html>"
        return HTMLResponse(content=html, status_code=500)

    token_json = token_resp.json()
    id_token = token_json.get("id_token")
    access_token = token_json.get("access_token")

    # Fetch userinfo
    userinfo = {}
    try:
        resp = requests.get("https://www.googleapis.com/oauth2/v3/userinfo", headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
        if resp.status_code == 200:
            userinfo = resp.json()
    except Exception:
        pass

    # Create a session id and store tokens/profile in memory
    session_id = uuid.uuid4().hex
    _sessions[session_id] = {
        "tokens": token_json,
        "profile": userinfo,
    }

    # Simple HTML that posts the profile to the opener and closes the popup
    payload = {
        "success": True,
        "profile": userinfo,
    }
    safe_payload = str(payload).replace("</", "<\\/")
    html = f"""
<html>
  <body>
    <script>
      try {{
        window.opener.postMessage({safe_payload}, '*');
      }} catch(e) {{}}
      window.close();
    </script>
    <p>Authentication complete. You can close this window.</p>
  </body>
</html>
"""

    response = HTMLResponse(content=html)
    # set session cookie (httponly)
    response.set_cookie(key="session", value=session_id, httponly=True, path="/")

    return response


@router.get("/auth/session")
def get_session(request: Request):
    session_id = request.cookies.get("session")
    if not session_id:
        return {"logged_in": False}
    s = _sessions.get(session_id)
    if not s:
        return {"logged_in": False}
    return {"logged_in": True, "profile": s.get("profile")}


@router.post("/auth/logout")
def logout(request: Request):
    session_id = request.cookies.get("session")
    response = {"ok": True}
    if session_id and session_id in _sessions:
        del _sessions[session_id]
    # instruct client to clear cookie
    return Response(content="", status_code=204)
