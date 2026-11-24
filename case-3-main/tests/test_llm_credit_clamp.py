"""OpenRouter 402 credit clamp — re-clamp when afford drops on retry."""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from case3.llm_client import LLMClient, LLMConfig, LLMError, parse_openrouter_afford


def test_parse_openrouter_afford_reads_afford_not_requested() -> None:
    body = (
        'You requested up to 7835 tokens, but can only afford 7002. '
        "To increase, visit https://openrouter.ai/settings/credits"
    )
    assert parse_openrouter_afford(body) == 7002
    assert parse_openrouter_afford("nope") is None


def test_complete_reclamps_on_second_402() -> None:
    """First afford 7899 → 7835; second afford 7002 must clamp again, not raise."""
    cfg = LLMConfig(
        base_url="https://openrouter.ai/api",
        api_key="test-key",
        model="test/model",
        max_retries=3,
        max_tokens=16384,
        timeout_s=5,
    )
    client = LLMClient(cfg)

    err1 = _http_402(
        "You requested up to 16384 tokens, but can only afford 7899."
    )
    err2 = _http_402(
        "You requested up to 7835 tokens, but can only afford 7002."
    )
    ok = MagicMock()
    ok.read.return_value = json.dumps(
        {"choices": [{"message": {"content": '{"slides":[]}'}, "finish_reason": "stop"}]}
    ).encode("utf-8")
    ok.__enter__ = lambda s: s
    ok.__exit__ = MagicMock(return_value=False)

    posts: list[int] = []

    def fake_urlopen(req, timeout=None):  # noqa: ANN001
        data = json.loads(req.data.decode("utf-8"))
        posts.append(int(data["max_tokens"]))
        if len(posts) == 1:
            raise err1
        if len(posts) == 2:
            raise err2
        return ok

    with patch("case3.llm_client.urllib.request.urlopen", side_effect=fake_urlopen):
        with patch.object(client, "_sleep", return_value=None):
            text = client.complete(system="sys", user_text="user")

    assert "slides" in text
    assert posts[0] == 16384
    assert posts[1] == 7899 - 64  # first clamp
    assert posts[2] == 7002 - 64  # second clamp must happen


def test_complete_raises_when_afford_not_lower() -> None:
    cfg = LLMConfig(
        base_url="https://openrouter.ai/api",
        api_key="k",
        model="m",
        max_retries=1,
        max_tokens=2048,
    )
    client = LLMClient(cfg)
    err = _http_402("can only afford 9000.")  # higher than request — no clamp help

    with patch("case3.llm_client.urllib.request.urlopen", side_effect=err):
        with patch.object(client, "_sleep", return_value=None):
            with pytest.raises(LLMError, match="402"):
                client.complete(system="s", user_text="u")


def test_complete_raises_helpful_error_on_openrouter_free_rate_limit() -> None:
    cfg = LLMConfig(
        base_url="https://openrouter.ai/api",
        api_key="k",
        model="m",
        max_retries=3,
        max_tokens=2048,
    )
    client = LLMClient(cfg)
    import urllib.error

    body = json.dumps({
        "error": {
            "message": "Rate limit exceeded: free-models-per-day. Add 10 credits to unlock 1000 free model requests per day",
            "code": 429
        }
    }).encode("utf-8")
    err = urllib.error.HTTPError(
        url="https://openrouter.ai/api/v1/chat/completions",
        code=429,
        msg="Too Many Requests",
        hdrs=None,  # type: ignore[arg-type]
        fp=BytesIO(body),
    )

    with patch("case3.llm_client.urllib.request.urlopen", side_effect=err):
        with pytest.raises(LLMError, match="Исчерпан суточный лимит бесплатных запросов OpenRouter"):
            client.complete(system="s", user_text="u")


def _http_402(message: str) -> Exception:
    body = json.dumps({"error": {"message": message, "code": 402}}).encode("utf-8")
    exc = Exception("402")
    # Build a real HTTPError-like object
    import urllib.error

    return urllib.error.HTTPError(
        url="https://openrouter.ai/api/v1/chat/completions",
        code=402,
        msg="Payment Required",
        hdrs=None,  # type: ignore[arg-type]
        fp=BytesIO(body),
    )
