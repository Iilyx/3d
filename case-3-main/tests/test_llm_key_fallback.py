"""Tests for LLM API key fallback mechanism (RED-GREEN-REFACTOR)."""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import MagicMock, patch
import urllib.error
import pytest

from case3.llm_client import LLMClient, LLMConfig, LLMError


def _http_err(code: int, message: str) -> urllib.error.HTTPError:
    body = json.dumps({"error": {"message": message, "code": code}}).encode("utf-8")
    return urllib.error.HTTPError(
        url="https://openrouter.ai/api/v1/chat/completions",
        code=code,
        msg="Error",
        hdrs=None,  # type: ignore[arg-type]
        fp=BytesIO(body),
    )


def test_config_parses_comma_separated_and_fallback_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VISION_API_BASE_URL", "https://openrouter.ai/api")
    monkeypatch.setenv("VISION_API_KEY", "key-one, key-two")
    monkeypatch.setenv("VISION_FALLBACK_API_KEYS", "key-three, key-two")

    cfg = LLMConfig.from_env()
    assert cfg.api_keys == ("key-one", "key-two", "key-three")
    assert cfg.api_key == "key-one"


def test_complete_falls_back_to_second_key_on_429() -> None:
    cfg = LLMConfig(
        base_url="https://openrouter.ai/api",
        api_key="key-one",
        api_keys=("key-one", "key-two"),
        model="openrouter/free",
        max_retries=2,
    )
    client = LLMClient(cfg)

    used_auth_headers: list[str] = []

    ok = MagicMock()
    ok.read.return_value = json.dumps(
        {"choices": [{"message": {"content": "latex response"}, "finish_reason": "stop"}]}
    ).encode("utf-8")
    ok.__enter__ = lambda s: s
    ok.__exit__ = MagicMock(return_value=False)

    err429 = _http_err(429, "Rate limit exceeded: free-models-per-day")

    def fake_urlopen(req, timeout=None):  # noqa: ANN001
        auth = req.headers.get("Authorization", "")
        used_auth_headers.append(auth)
        if auth == "Bearer key-one":
            raise err429
        return ok

    with patch("case3.llm_client.urllib.request.urlopen", side_effect=fake_urlopen):
        with patch.object(client, "_sleep", return_value=None):
            result = client.complete(system="sys", user_text="usr")

    assert result == "latex response"
    assert "Bearer key-one" in used_auth_headers
    assert "Bearer key-two" in used_auth_headers
    assert client.current_api_key == "key-two"


def test_complete_raises_when_all_fallback_keys_exhausted() -> None:
    cfg = LLMConfig(
        base_url="https://openrouter.ai/api",
        api_keys=("key-one", "key-two"),
        max_retries=1,
    )
    client = LLMClient(cfg)
    err429 = _http_err(429, "Rate limit exceeded: free-models-per-day")

    with patch("case3.llm_client.urllib.request.urlopen", side_effect=err429):
        with patch.object(client, "_sleep", return_value=None):
            with pytest.raises(LLMError, match="все ключи исчерпаны: 2/2"):
                client.complete(system="sys", user_text="usr")


def test_stream_falls_back_on_401() -> None:
    cfg = LLMConfig(
        base_url="https://openrouter.ai/api",
        api_keys=("bad-key", "good-key"),
        max_retries=1,
    )
    client = LLMClient(cfg)

    err401 = _http_err(401, "Invalid API key")

    ok = MagicMock()
    # Mock SSE stream
    ok.__iter__ = lambda s: iter([
        b'data: {"choices":[{"delta":{"content":"chunk1"}}]}\n\n',
        b'data: {"choices":[{"delta":{"content":"chunk2"}}]}\n\n',
        b'data: [DONE]\n\n'
    ])
    ok.__enter__ = lambda s: s
    ok.__exit__ = MagicMock(return_value=False)

    def fake_urlopen(req, timeout=None):  # noqa: ANN001
        if req.headers.get("Authorization") == "Bearer bad-key":
            raise err401
        return ok

    with patch("case3.llm_client.urllib.request.urlopen", side_effect=fake_urlopen):
        chunks = list(client.stream(system="sys", user_text="usr"))

    assert chunks == ["chunk1", "chunk2"]
    assert client.current_api_key == "good-key"
