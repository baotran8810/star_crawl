"""LLM-based keyword extractor over any OpenAI-compatible router.

Reads three env vars (all overridable via CLI flags):

  STAR_CRAWL_LLM_BASE_URL  default http://localhost:20128/v1   (9router)
  STAR_CRAWL_LLM_MODEL     default xiaomi/mimo-v2.5-pro
  STAR_CRAWL_LLM_API_KEY   default ""  (local router needs no auth)

Each article's keywords are cached by content_hash under
data/.llm_cache/<hash>.json so re-runs cost zero. A cumulative
spend tracker (data/.llm_cache/_spend.json) prevents accidental
runaway when STAR_CRAWL_LLM_BUDGET_USD is set.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://localhost:20128/v1"
DEFAULT_MODEL = "xiaomi/mimo-v2.5-pro"
CACHE_DIR = Path("data") / ".llm_cache"
SPEND_FILE = CACHE_DIR / "_spend.json"

# Default per-million-token pricing for mimo-v2.5-pro on OpenRouter.
# Used only for budget tracking — change via env if your router differs.
DEFAULT_IN_USD_PER_M = 1.0
DEFAULT_OUT_USD_PER_M = 3.0

PROMPT_SYSTEM = (
    "You are a precise keyword extractor for technical engineering blog "
    "articles. Return only JSON. No prose, no markdown code fences, no "
    "commentary."
)
PROMPT_USER_TEMPLATE = """\
Extract the most useful keywords/phrases from the article below.

Rules:
- Focus on concrete technical concepts, technologies, frameworks,
  architectures, methodologies, and domain entities.
- Avoid generic words (team, system, engineer, blog, article, post,
  data, feature). Avoid stop words.
- Each keyword is 1–3 words.
- Output 8–15 keywords. No duplicates.
- "score" is 0.0–1.0 confidence that this is a salient keyword for the
  article (be picky; not every extracted phrase deserves 0.9).

Return strict JSON of this shape, with NO other text:

{{
  "keywords": [
    {{"term": "kafka", "score": 0.92}},
    {{"term": "event-driven architecture", "score": 0.78}}
  ]
}}

Article title: {title}

Article body:
{body}
"""


@dataclass(frozen=True)
class LLMConfig:
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    api_key: str = ""
    timeout_s: float = 180.0               # reasoning models can take a while
    max_input_chars: int = 8_000           # ~2k tokens cap on body
    max_output_tokens: int = 8_192         # reasoning models need headroom
    in_usd_per_m: float = DEFAULT_IN_USD_PER_M
    out_usd_per_m: float = DEFAULT_OUT_USD_PER_M
    budget_usd: float | None = None

    @classmethod
    def from_env(cls, *, model: str | None = None) -> "LLMConfig":
        budget = os.environ.get("STAR_CRAWL_LLM_BUDGET_USD")
        return cls(
            base_url=os.environ.get("STAR_CRAWL_LLM_BASE_URL", DEFAULT_BASE_URL),
            model=model or os.environ.get("STAR_CRAWL_LLM_MODEL", DEFAULT_MODEL),
            api_key=os.environ.get("STAR_CRAWL_LLM_API_KEY", ""),
            in_usd_per_m=float(os.environ.get("STAR_CRAWL_LLM_IN_USD", DEFAULT_IN_USD_PER_M)),
            out_usd_per_m=float(os.environ.get("STAR_CRAWL_LLM_OUT_USD", DEFAULT_OUT_USD_PER_M)),
            budget_usd=float(budget) if budget else None,
        )


class BudgetExceeded(RuntimeError):
    """Raised when cumulative spend would exceed STAR_CRAWL_LLM_BUDGET_USD."""


class LLMExtractor:
    """Implements the CandidateExtractor protocol from extract.py.

    extract(text) returns list[(term, score)] just like KeyBertExtractor.
    """

    def __init__(
        self,
        config: LLMConfig | None = None,
        *,
        title: str = "",
        client: httpx.Client | None = None,
    ) -> None:
        self.config = config or LLMConfig.from_env()
        self.title = title
        self._client = client or httpx.Client(timeout=self.config.timeout_s)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # The protocol is `extract(text) -> list[(term, score)]`.
    # We accept an optional title via instance state so the prompt is richer.
    def extract(self, text: str) -> list[tuple[str, float]]:
        if not text or len(text) < 100:
            return []

        body = text.strip()
        if len(body) > self.config.max_input_chars:
            body = body[: self.config.max_input_chars]

        cache_key = self._cache_key(body)
        cached = self._load_cache(cache_key)
        if cached is not None:
            return cached

        self._guard_budget()
        keywords, usage = self._call(body)
        self._record_spend(usage)
        self._save_cache(cache_key, keywords)
        return keywords

    # ─────────── HTTP call ───────────
    def _call(self, body: str) -> tuple[list[tuple[str, float]], dict]:
        prompt = PROMPT_USER_TEMPLATE.format(title=self.title or "(none)", body=body)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": PROMPT_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": self.config.max_output_tokens,
            "response_format": {"type": "json_object"},
        }

        url = self.config.base_url.rstrip("/") + "/chat/completions"
        last_err: Exception | None = None
        for attempt in range(1, 4):
            try:
                resp = self._client.post(url, headers=headers, json=payload)
            except httpx.HTTPError as e:
                last_err = e
                time.sleep(min(2 ** attempt, 8))
                continue

            if resp.status_code in (429, 500, 502, 503, 504):
                time.sleep(min(2 ** attempt, 8))
                continue
            if resp.status_code != 200:
                raise RuntimeError(
                    f"LLM router returned {resp.status_code}: {resp.text[:300]}"
                )

            # 9router always returns Server-Sent Events (text/event-stream)
            # even when stream=false. Detect either format.
            ctype = (resp.headers.get("content-type") or "").lower()
            if "event-stream" in ctype or resp.text.lstrip().startswith("data:"):
                data = _parse_sse_completion(resp.text)
            else:
                data = resp.json()
            try:
                content = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError, TypeError) as e:
                raise RuntimeError(
                    f"LLM router malformed response: {str(data)[:300]}"
                ) from e
            keywords = _parse_keywords(content)
            usage = data.get("usage", {}) or {}
            return keywords, usage

        raise RuntimeError(f"LLM call failed after retries: {last_err}")

    # ─────────── cache ───────────
    def _cache_key(self, body: str) -> str:
        h = hashlib.sha256()
        h.update(self.config.model.encode("utf-8"))
        h.update(b"|")
        h.update((self.title or "").encode("utf-8"))
        h.update(b"|")
        h.update(body.encode("utf-8"))
        return h.hexdigest()[:32]

    def _cache_path(self, key: str) -> Path:
        return CACHE_DIR / f"{key}.json"

    def _load_cache(self, key: str) -> list[tuple[str, float]] | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return [(str(t), float(s)) for t, s in data]
        except Exception:
            return None

    def _save_cache(self, key: str, keywords: list[tuple[str, float]]) -> None:
        path = self._cache_path(key)
        path.write_text(json.dumps(keywords), encoding="utf-8")

    # ─────────── budget tracker ───────────
    def _load_spend(self) -> dict:
        if not SPEND_FILE.exists():
            return {"total_usd": 0.0, "calls": 0, "in_tokens": 0, "out_tokens": 0}
        try:
            return json.loads(SPEND_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {"total_usd": 0.0, "calls": 0, "in_tokens": 0, "out_tokens": 0}

    def _guard_budget(self) -> None:
        if self.config.budget_usd is None:
            return
        spent = self._load_spend()["total_usd"]
        if spent >= self.config.budget_usd:
            raise BudgetExceeded(
                f"LLM budget exceeded: spent ${spent:.4f} of "
                f"${self.config.budget_usd:.2f}. Raise STAR_CRAWL_LLM_BUDGET_USD "
                f"or unset it to continue."
            )

    def _record_spend(self, usage: dict) -> None:
        in_t = int(usage.get("prompt_tokens", 0))
        out_t = int(usage.get("completion_tokens", 0))
        cost = (in_t / 1_000_000) * self.config.in_usd_per_m + (
            out_t / 1_000_000
        ) * self.config.out_usd_per_m
        spend = self._load_spend()
        spend["total_usd"] = round(spend["total_usd"] + cost, 6)
        spend["calls"] += 1
        spend["in_tokens"] += in_t
        spend["out_tokens"] += out_t
        SPEND_FILE.write_text(json.dumps(spend, indent=2), encoding="utf-8")


# ─────────── SSE + JSON parsing ───────────


def _parse_sse_completion(text: str) -> dict:
    """Reconstruct an OpenAI-style completion dict from an SSE response.

    9router emits `data: {…}\\n\\n` chunks ending with `data: [DONE]`. For
    non-streaming requests it still emits exactly one full payload chunk
    before [DONE] — we return that payload.

    For true streaming responses (multiple chunks with delta), we
    concatenate the deltas into a single `choices[0].message.content`.
    """
    full = {"choices": [{"message": {"content": "", "role": "assistant"}}], "usage": {}}
    parts: list[str] = []
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue

        choices = obj.get("choices") or []
        if choices:
            first = choices[0]
            # streaming delta
            delta = first.get("delta") or {}
            if "content" in delta and delta["content"] is not None:
                parts.append(str(delta["content"]))
            # non-streaming full message in one chunk
            msg = first.get("message") or {}
            if "content" in msg and msg["content"] is not None:
                parts.append(str(msg["content"]))
        if obj.get("usage"):
            full["usage"] = obj["usage"]
        # Carry common metadata from the last seen chunk
        for k in ("id", "model", "created", "object"):
            if k in obj:
                full[k] = obj[k]

    full["choices"][0]["message"]["content"] = "".join(parts)
    return full


_FENCE_RE = re.compile(r"```(?:json)?\s*(.+?)\s*```", re.DOTALL | re.IGNORECASE)


def _parse_keywords(content: str) -> list[tuple[str, float]]:
    """Robust JSON parse — tolerates code fences and surrounding chatter."""
    if not content:
        return []
    text = content.strip()
    m = _FENCE_RE.search(text)
    if m:
        text = m.group(1).strip()
    # Locate the first { … } block if the model wrote extra prose
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    raw = data.get("keywords") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return []
    out: list[tuple[str, float]] = []
    for entry in raw:
        if isinstance(entry, str):
            out.append((entry.strip(), 0.8))
        elif isinstance(entry, dict):
            term = str(entry.get("term", "")).strip()
            try:
                score = float(entry.get("score", 0.7))
            except (TypeError, ValueError):
                score = 0.7
            if term:
                out.append((term, max(0.0, min(1.0, score))))
    return out
