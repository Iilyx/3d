"""LLMClient.stream parses OpenAI-compatible SSE."""

from __future__ import annotations

import io
import json
from typing import Any
from unittest.mock import MagicMock, patch

from case3.llm_client import LLMClient, LLMConfig


def _sse_body(chunks: list[str]) -> bytes:
    lines: list[str] = []
    for c in chunks:
        payload = {
            "choices": [{"delta": {"content": c}, "finish_reason": None}]
        }
        lines.append("data: " + json.dumps(payload))
    lines.append("data: [DONE]")
    return ("\n\n".join(lines) + "\n\n").encode("utf-8")


def test_stream_yields_delta_contents() -> None:
    cfg = LLMConfig(base_url="http://example.test", api_key=None, model="m", max_retries=0)
    client = LLMClient(cfg)
    raw = _sse_body(["Hello", " ", "world"])

    mock_resp = MagicMock()
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.read = MagicMock(return_value=raw)
    # Also support line iteration if used
    mock_resp.__iter__ = MagicMock(
        return_value=iter(io.BytesIO(raw).readlines())
    )

    with patch("urllib.request.urlopen", return_value=mock_resp):
        pieces = list(
            client.stream(system="s", user_text="u", reasoning="off", max_tokens=64)
        )
    assert "".join(pieces) == "Hello world"


def test_stream_sets_stream_true_in_body() -> None:
    cfg = LLMConfig(base_url="http://example.test", model="m", max_retries=0)
    client = LLMClient(cfg)
    captured: dict[str, Any] = {}

    def fake_urlopen(req: Any, timeout: float = 0) -> Any:  # noqa: ARG001
        body = json.loads(req.data.decode("utf-8"))
        captured.update(body)
        raw = _sse_body(["ok"])
        mock_resp = MagicMock()
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read = MagicMock(return_value=raw)
        mock_resp.__iter__ = MagicMock(
            return_value=iter(io.BytesIO(raw).readlines())
        )
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        list(client.stream(system="s", user_text="u", max_tokens=32))
    assert captured.get("stream") is True
    assert captured.get("max_tokens") == 32
