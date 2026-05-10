"""Auth gating + safe-bind tests."""

from __future__ import annotations

from importlib import reload
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from star_crawl.db import migrate as db_migrate


@pytest.mark.integration
def test_no_auth_when_env_unset(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("STAR_CRAWL_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("STAR_CRAWL_AUTH", raising=False)
    db_migrate.migrate(tmp_path)

    import star_crawl.web.app as app_module
    reload(app_module)
    client = TestClient(app_module.app)

    r = client.get("/")
    assert r.status_code == 200


@pytest.mark.integration
def test_auth_required_when_env_set(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("STAR_CRAWL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("STAR_CRAWL_AUTH", "alice:s3cret")
    db_migrate.migrate(tmp_path)

    import star_crawl.web.app as app_module
    reload(app_module)
    client = TestClient(app_module.app)

    r = client.get("/")
    assert r.status_code == 401

    r2 = client.get("/", auth=("alice", "s3cret"))
    assert r2.status_code == 200

    r3 = client.get("/", auth=("alice", "wrong"))
    assert r3.status_code == 401


@pytest.mark.integration
def test_serve_refuses_non_loopback_without_auth(monkeypatch):
    """The CLI `serve` command exits non-zero on non-loopback host without auth."""
    from typer.testing import CliRunner

    from star_crawl.cli import app as cli_app

    monkeypatch.delenv("STAR_CRAWL_AUTH", raising=False)
    runner = CliRunner()
    result = runner.invoke(cli_app, ["serve", "--host", "0.0.0.0", "--port", "8123"])
    assert result.exit_code == 3
    assert "STAR_CRAWL_AUTH" in result.output or "exposed" in result.output.lower()
