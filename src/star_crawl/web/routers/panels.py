"""Shared helper for legacy → shell redirects.

Each legacy route (/articles/{id}, /runs[/N], /sources[/N], /graph,
/search) wraps the existing handler body with this guard: if the
request did NOT come through /panel/..., redirect to the workspace
shell with an `?open=<legacy-url>` query so workspace.js can pick it
up and open the right tab.

This makes the workspace the single user-facing UI; direct bookmarks
and external links still land at meaningful content, just inside the
shell instead of the legacy base.html chrome.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi import Request
from fastapi.responses import RedirectResponse


def is_panel_request(request: Request) -> bool:
    return request.url.path.startswith("/panel/")


def redirect_to_shell(request: Request) -> RedirectResponse:
    """Build a 302 to `/?open=<path-and-query>` preserving the query string."""
    target = request.url.path
    if request.url.query:
        target = f"{target}?{request.url.query}"
    return RedirectResponse(f"/?open={quote(target, safe='')}", status_code=302)
