"""Playwright fixtures for web/e2e tests.

Each test boots a uvicorn process on an auto-assigned port against a fresh
fixture corpus. Requires `playwright` installed in the venv with chromium
already provisioned (see specs/004-obsidian-ui/quickstart.md).
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path
from urllib.request import Request, urlopen

import pytest


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_up(url: str, timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urlopen(Request(url), timeout=1)
            return
        except Exception:
            time.sleep(0.15)
    raise TimeoutError(f"server did not come up at {url}")


@pytest.fixture
def server_url(populated_data_dir: Path, tmp_path: Path):
    """Boot uvicorn against the populated fixture; yield base URL."""
    port = _free_port()
    env = {
        "STAR_CRAWL_DATA_DIR": str(populated_data_dir),
        "PATH": "/usr/bin:/bin:" + str(Path(sys.executable).parent),
    }
    log = open(tmp_path / "uvicorn.log", "wb")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "star_crawl.web.app:app",
         "--host", "127.0.0.1", "--port", str(port)],
        env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    try:
        # /healthz returns 401 when auth disabled? No — auth_required allows when env unset.
        _wait_up(f"http://127.0.0.1:{port}/", timeout=15)
        yield f"http://127.0.0.1:{port}"
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill()
        log.close()


@pytest.fixture
def page(server_url):
    """Yield a fresh chromium page pointed at the server, localStorage cleared."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        pytest.skip("playwright not installed")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        p = context.new_page()
        try:
            p.goto(server_url + "/", wait_until="networkidle", timeout=15000)
            p.evaluate("localStorage.removeItem('star_crawl.workspace.v1')")
            yield p
        finally:
            browser.close()
