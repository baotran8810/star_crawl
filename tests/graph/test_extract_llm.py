"""LLM extractor unit tests — mock the HTTP router, never hit the network."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
import respx

from star_crawl.graph.extract_llm import (
    BudgetExceeded,
    LLMConfig,
    LLMExtractor,
    _parse_keywords,
)


SAMPLE_TEXT = (
    "We migrated our order processing from synchronous REST calls to an "
    "event-driven architecture using Apache Kafka. The shift reduced p99 "
    "latency and decoupled service deployments across the platform. "
    "PostgreSQL is the system of record for orders."
)


def _ok_response(content: dict) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "id": "x",
            "choices": [{"message": {"role": "assistant", "content": json.dumps(content)}}],
            "usage": {"prompt_tokens": 400, "completion_tokens": 80, "total_tokens": 480},
        },
    )


@pytest.fixture(autouse=True)
def isolate_cache(tmp_path: Path, monkeypatch):
    """Redirect cache + spend files to tmp_path so tests don't pollute data/."""
    monkeypatch.chdir(tmp_path)
    yield


@pytest.mark.unit
def test_parse_keywords_strict_json():
    content = json.dumps({"keywords": [
        {"term": "kafka", "score": 0.91},
        {"term": "event-driven architecture", "score": 0.74},
    ]})
    out = _parse_keywords(content)
    assert out == [("kafka", 0.91), ("event-driven architecture", 0.74)]


@pytest.mark.unit
def test_parse_keywords_with_code_fence():
    content = (
        "Here you go:\n"
        "```json\n"
        '{"keywords": [{"term": "kafka", "score": 0.9}]}\n'
        "```"
    )
    out = _parse_keywords(content)
    assert out == [("kafka", 0.9)]


@pytest.mark.unit
def test_parse_keywords_handles_strings_in_array():
    content = json.dumps({"keywords": ["kafka", "postgres"]})
    out = _parse_keywords(content)
    assert ("kafka", 0.8) in out
    assert ("postgres", 0.8) in out


@pytest.mark.unit
def test_parse_keywords_returns_empty_on_bad_json():
    assert _parse_keywords("garbage") == []
    assert _parse_keywords("") == []


@pytest.mark.integration
def test_extract_calls_router_and_caches():
    cfg = LLMConfig(
        base_url="http://localhost:20128/v1",
        model="xiaomi/mimo-v2.5-pro",
    )
    ext = LLMExtractor(cfg, title="Order Pipeline at Scale")

    with respx.mock(assert_all_called=False) as router:
        route = router.post("http://localhost:20128/v1/chat/completions").mock(
            return_value=_ok_response({"keywords": [
                {"term": "kafka", "score": 0.92},
                {"term": "event-driven architecture", "score": 0.78},
                {"term": "postgresql", "score": 0.65},
            ]})
        )
        first = ext.extract(SAMPLE_TEXT)
        # Second call with same text hits cache — no extra HTTP
        second = ext.extract(SAMPLE_TEXT)

    assert first == second
    assert ("kafka", 0.92) in first
    assert ("postgresql", 0.65) in first
    assert route.call_count == 1


@pytest.mark.integration
def test_short_text_no_call():
    ext = LLMExtractor(LLMConfig())
    with respx.mock(assert_all_called=False) as router:
        router.post("http://localhost:20128/v1/chat/completions").mock(
            return_value=_ok_response({"keywords": []})
        )
        assert ext.extract("hello world") == []
        assert ext.extract("") == []


@pytest.mark.integration
def test_retries_on_5xx_then_succeeds(monkeypatch):
    # Speed up the backoff sleep so the test isn't slow
    import star_crawl.graph.extract_llm as mod
    monkeypatch.setattr(mod.time, "sleep", lambda *_a, **_k: None)

    ext = LLMExtractor(LLMConfig())
    with respx.mock(assert_all_called=False) as router:
        route = router.post("http://localhost:20128/v1/chat/completions").mock(
            side_effect=[
                httpx.Response(503, text="bad gateway"),
                _ok_response({"keywords": [{"term": "kafka", "score": 0.9}]}),
            ]
        )
        out = ext.extract(SAMPLE_TEXT)
    assert out == [("kafka", 0.9)]
    assert route.call_count == 2


@pytest.mark.integration
def test_budget_exceeded_blocks_call(tmp_path: Path):
    # Pre-populate the spend file with a high value
    from star_crawl.graph.extract_llm import CACHE_DIR, SPEND_FILE
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    SPEND_FILE.write_text(
        json.dumps({"total_usd": 5.0, "calls": 100, "in_tokens": 1, "out_tokens": 1}),
        encoding="utf-8",
    )

    ext = LLMExtractor(LLMConfig(budget_usd=1.0))
    with pytest.raises(BudgetExceeded):
        ext.extract(SAMPLE_TEXT)


@pytest.mark.integration
def test_spend_accumulates_after_calls():
    ext = LLMExtractor(LLMConfig(in_usd_per_m=1.0, out_usd_per_m=3.0))
    with respx.mock(assert_all_called=False) as router:
        router.post("http://localhost:20128/v1/chat/completions").mock(
            return_value=_ok_response({"keywords": [{"term": "kafka", "score": 0.9}]})
        )
        ext.extract(SAMPLE_TEXT)

    from star_crawl.graph.extract_llm import SPEND_FILE
    sp = json.loads(SPEND_FILE.read_text(encoding="utf-8"))
    # 400 input @ $1/M + 80 output @ $3/M = 0.0004 + 0.00024 = 0.00064
    assert sp["calls"] == 1
    assert sp["in_tokens"] == 400
    assert sp["out_tokens"] == 80
    assert sp["total_usd"] == pytest.approx(0.00064, abs=1e-7)


@pytest.mark.integration
def test_bearer_auth_sent_when_api_key_set():
    ext = LLMExtractor(LLMConfig(api_key="secret-abc"))
    with respx.mock(assert_all_called=False) as router:
        route = router.post("http://localhost:20128/v1/chat/completions").mock(
            return_value=_ok_response({"keywords": [{"term": "kafka", "score": 0.9}]})
        )
        ext.extract(SAMPLE_TEXT)
    request = route.calls[0].request
    assert request.headers.get("authorization") == "Bearer secret-abc"


@pytest.mark.integration
def test_no_auth_header_when_key_empty():
    ext = LLMExtractor(LLMConfig(api_key=""))
    with respx.mock(assert_all_called=False) as router:
        route = router.post("http://localhost:20128/v1/chat/completions").mock(
            return_value=_ok_response({"keywords": [{"term": "kafka", "score": 0.9}]})
        )
        ext.extract(SAMPLE_TEXT)
    request = route.calls[0].request
    assert "authorization" not in {k.lower() for k in request.headers}
