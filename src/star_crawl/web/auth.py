"""Optional HTTP basic auth driven by STAR_CRAWL_AUTH env var."""

from __future__ import annotations

import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

ENV_VAR = "STAR_CRAWL_AUTH"
_security = HTTPBasic(auto_error=False)


def _credentials_from_env() -> tuple[str, str] | None:
    raw = os.environ.get(ENV_VAR)
    if not raw or ":" not in raw:
        return None
    user, _, pw = raw.partition(":")
    return user, pw


def auth_required(
    creds: HTTPBasicCredentials | None = Depends(_security),
) -> str | None:
    """Dependency: enforces HTTP basic auth if STAR_CRAWL_AUTH is set."""
    expected = _credentials_from_env()
    if expected is None:
        return None  # no auth required

    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="auth required",
            headers={"WWW-Authenticate": "Basic"},
        )

    user_ok = secrets.compare_digest(creds.username, expected[0])
    pw_ok = secrets.compare_digest(creds.password, expected[1])
    if not (user_ok and pw_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    return creds.username


def auth_enabled() -> bool:
    return _credentials_from_env() is not None
