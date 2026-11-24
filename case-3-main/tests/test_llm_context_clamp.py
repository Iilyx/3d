"""LAN Qwen / llama-server HTTP 500 «Context size exceeded» → shrink max_tokens."""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
import urllib.error

from case3.llm_client import (
    LLMClient,
    LLMConfig,
    LLMError,
    context_exceeded,
    context_shrink_max_tokens,
)


def test_context_exceeded_detects_llama_server_message() -> None:
    assert context_exceeded('{"error":{"message":"Context size has been exceeded."}}')
    assert context_exceeded("context size has been exceeded")
    assert not context_exceeded("internal server error")


def test_context_shrink_halves_until_floor() -> None:
    assert context_shrink_max_tokens(16384) == 8192
    assert context_shrink_max_tokens(2048) == 1024
    assert context_shrink_max_tokens(1024) is None
    assert context_shrink_max_tokens(800) is None


def test_complete_retries_on_500_context_exceeded() -> None:
    cfg = LLMConfig(
        base_url="http://192.168.4.101:8080",
        model="qwen3.5-4b",
        max_retries=3,
        max_tokens=16384,
        timeout_s=5,
        reasoning="off",
    )
    client = LLMClient(cfg)

    err = _http_500("Context size has been exceeded.")
    ok = MagicMock()
    ok.read.return_value = json.dumps(
        {
            "choices": [
                {
                    "message": {"content": "\\documentclass{article}\\begin{document}x\\end{document}"},
                    "finish_reason": "stop",
                }
            ]
        }
    ).encode("utf-8")
    ok.__enter__ = lambda s: s
    ok.__exit__ = MagicMock(return_value=False)

    posts: list[int] = []

    def fake_urlopen(req, timeout=None):  # noqa: ANN001
        data = json.loads(req.data.decode("utf-8"))
        posts.append(int(data["max_tokens"]))
        if len(posts) == 1:
            raise err
        return ok

    with patch("case3.llm_client.urllib.request.urlopen", side_effect=fake_urlopen):
        with patch.object(client, "_sleep", return_value=None):
            text = client.complete(system="sys", user_text="user")

    assert "documentclass" in text
    assert posts[0] == 16384
    assert posts[1] == 8192


def test_complete_raises_500_context_when_cannot_shrink() -> None:
    cfg = LLMConfig(
        base_url="http://192.168.4.101:8080",
        model="qwen3.5-4b",
        max_retries=1,
        max_tokens=1024,
        timeout_s=5,
    )
    client = LLMClient(cfg)
    err = _http_500("Context size has been exceeded.")

    with patch("case3.llm_client.urllib.request.urlopen", side_effect=err):
        with patch.object(client, "_sleep", return_value=None):
            with pytest.raises(LLMError, match="500|Context|контекст"):
                client.complete(system="s", user_text="u")


def _http_500(message: str) -> Exception:
    body = json.dumps({"error": {"code": 500, "message": message, "type": "server_error"}}).encode(
        "utf-8"
    )
    return urllib.error.HTTPError(
        url="http://192.168.4.101:8080/v1/chat/completions",
        code=500,
        msg="Internal Server Error",
        hdrs=None,  # type: ignore[arg-type]
        fp=BytesIO(body),
    )
