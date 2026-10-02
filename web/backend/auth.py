"""Environment-configured demo login and signed browser sessions."""

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Optional

from fastapi import HTTPException, Request, Response, status

SESSION_COOKIE = "intent_os_session"
SESSION_MAX_AGE = 60 * 60 * 12


def public_demo_enabled() -> bool:
    return os.getenv("WEB_PUBLIC_DEMO", "").strip().lower() == "true"


def _session_secret() -> Optional[str]:
    secret = os.getenv("WEB_SESSION_SECRET", "")
    return secret if len(secret) >= 32 else None


def web_login_configured() -> bool:
    return bool(
        os.getenv("WEB_DEMO_USERNAME")
        and os.getenv("WEB_DEMO_PASSWORD")
        and _session_secret()
    )


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _create_session(username: str) -> str:
    secret = _session_secret()
    if not secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "login_not_configured", "message": "Web sign-in is not configured."},
        )
    payload = _encode(json.dumps({"sub": username, "exp": int(time.time()) + SESSION_MAX_AGE}).encode())
    signature = _encode(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def _read_session(token: str) -> Optional[str]:
    secret = _session_secret()
    if not secret:
        return None
    try:
        payload, signature = token.split(".", 1)
        expected = _encode(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        claims = json.loads(_decode(payload))
        if not isinstance(claims.get("sub"), str) or claims.get("exp", 0) < time.time():
            return None
        return claims["sub"]
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def login(username: str, password: str, response: Response) -> str:
    configured_username = os.getenv("WEB_DEMO_USERNAME", "")
    configured_password = os.getenv("WEB_DEMO_PASSWORD", "")
    if not web_login_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "login_not_configured", "message": "Web sign-in is not configured."},
        )
    if not (
        hmac.compare_digest(username, configured_username)
        and hmac.compare_digest(password, configured_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": "Username or password is incorrect."},
        )

    response.set_cookie(
        key=SESSION_COOKIE,
        value=_create_session(username),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=os.getenv("VERCEL") == "1" or os.getenv("WEB_COOKIE_SECURE") == "1",
        samesite="lax",
        path="/",
    )
    return username


def require_user(request: Request) -> str:
    if public_demo_enabled():
        return "public-demo"

    username = _read_session(request.cookies.get(SESSION_COOKIE, ""))
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "sign_in_required", "message": "Sign in to use the Intent OS web agent."},
        )
    return username


def logout(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE, path="/", httponly=True, samesite="lax")