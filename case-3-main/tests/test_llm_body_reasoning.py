"""OpenRouter vs local reasoning body shapes."""

from __future__ import annotations

from case3.llm_client import LLMClient, LLMConfig, build_body
import io
import json
import urllib.error
from unittest.mock import patch


def test_local_off_uses_chat_template_kwargs() -> None:
    body = build_body(
        system="s",
        user_text="u",
        reasoning="off",
        base_url="http://192.168.1.10:8080",
    )
    assert body["chat_template_kwargs"] == {"enable_thinking": False}
    assert "reasoning" not in body


def test_openrouter_off_disables_reasoning_for_nemotron() -> None:
    """Nemotron free burns max_tokens on hidden reasoning unless enabled=False."""
    body = build_body(
        system="s",
        user_text="u",
        model="nvidia/nemotron-3.5-lightning:free",
        reasoning="off",
        base_url="https://openrouter.ai/api",
    )
    assert body["reasoning"] == {"enabled": False}
    assert "chat_template_kwargs" not in body


def test_openrouter_off_minimax_keeps_low_exclude() -> None:
    body = build_body(
        system="s",
        user_text="u",
        model="minimax/minimax-m3.1-flash:free",
        reasoning="off",
        base_url="https://openrouter.ai/api",
    )
    assert body["reasoning"] == {"effort": "low", "exclude": True}


def test_openrouter_free_off_disables_reasoning() -> None:
    body = build_body(
        system="s",
        user_text="u",
        model="openrouter/free",
        reasoning="off",
        base_url="https://openrouter.ai/api",
    )
    assert body["reasoning"] == {"enabled": False}


def test_images_become_qwen_vision_parts() -> None:
    body = build_body(
        system="s",
        user_text="build the deck",
        reasoning="off",
        base_url="http://192.168.1.10:8080",
        images=[("usr_01", "data:image/jpeg;base64,aaaa")],
    )
    content = body["messages"][1]["content"]
    assert isinstance(content, list)
    assert content[0]["text"] == "build the deck"
    assert content[1]["text"] == "Image id usr_01."
    assert content[2]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    # Local Qwen still gets the thinking switch alongside vision parts.
    assert body["chat_template_kwargs"]["enable_thinking"] is False


def test_no_images_keeps_plain_string_content() -> None:
    body = build_body(system="s", user_text="u", reasoning="off", images=[])
    assert body["messages"][1]["content"] == "u"


def test_llm_complete_falls_back_to_text_on_400_with_images() -> None:
    cfg = LLMConfig(
        base_url="http://test.api",
        api_key="key",
        max_retries=1,
    )
    client = LLMClient(cfg)

    calls = 0
    posted_contents = []

    def mock_urlopen(req, timeout=None):
        nonlocal calls
        calls += 1
        payload = json.loads(req.data.decode("utf-8"))
        posted_contents.append(payload["messages"][1]["content"])
        if calls == 1:
            # First call with images fails with 400 (e.g. image not supported)
            err = urllib.error.HTTPError(
                url="http://test.api/chat/completions",
                code=400,
                msg="Bad Request",
                hdrs={},
                fp=io.BytesIO(b'{"error": "Images not supported by this model"}'),
            )
            raise err
        # Second call succeeds
        resp_obj = {
            "choices": [
                {
                    "message": {"content": "ok text response"},
                    "finish_reason": "stop",
                }
            ]
        }
        mock_resp = io.BytesIO(json.dumps(resp_obj).encode("utf-8"))
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        res = client.complete(
            system="sys",
            user_text="describe",
            images=[("usr_01", "data:image/jpeg;base64,1234")],
        )

    assert res == "ok text response"
    assert calls == 2
    # First call had list content (multimodal)
    assert isinstance(posted_contents[0], list)
    # Fallback call was pure string
    assert posted_contents[1] == "describe"


def test_llm_shared_key_cooldown_skips_rate_limited_primary_across_clients() -> None:
    from case3.llm_client import clear_key_cooldowns

    clear_key_cooldowns()
    try:
        cfg = LLMConfig(
            base_url="http://test.api",
            api_key="key_primary",
            api_keys=("key_primary", "key_backup"),
            max_retries=1,
        )
        seen_auth: list[str] = []

        def mock_urlopen(req, timeout=None):
            auth = req.headers.get("Authorization", "")
            seen_auth.append(auth)
            if "key_primary" in auth:
                raise urllib.error.HTTPError(
                    url="http://test.api/chat/completions",
                    code=429,
                    msg="Rate limit",
                    hdrs={},
                    fp=io.BytesIO(b'{"error": "rate limit"}'),
                )
            return io.BytesIO(
                json.dumps(
                    {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]}
                ).encode("utf-8")
            )

        with patch("urllib.request.urlopen", side_effect=mock_urlopen):
            c1 = LLMClient(cfg, sleep=lambda _s: None)
            assert c1.complete(system="s", user_text="u") == "ok"
            # New LLMClient in same process skips cooled-down key_primary immediately!
            c2 = LLMClient(cfg, sleep=lambda _s: None)
            assert c2.complete(system="s", user_text="u2") == "ok"

        assert seen_auth == [
            "Bearer key_primary",
            "Bearer key_backup",
            "Bearer key_backup",
        ]
    finally:
        clear_key_cooldowns()


def test_content_rejects_english_cot_mentioning_charts_in_reasoning() -> None:
    from case3.llm_client import LLMError, _content

    payload = {
        "choices": [
            {
                "finish_reason": "length",
                "message": {
                    "content": "",
                    "reasoning": 'Thinking Process: 1. The user wants "charts" and "figures" analysis.',
                },
            }
        ]
    }
    try:
        _content(payload)
        raise AssertionError("expected LLMError when content is empty and reasoning is English CoT")
    except LLMError as exc:
        assert "empty response" in str(exc)


def test_complete_retries_openrouter_length_empty_with_reasoning_disabled_and_400_fallback() -> None:
    cfg = LLMConfig(
        base_url="https://openrouter.ai/api",
        api_key="key1",
        model="openrouter/free",
        max_retries=2,
        max_tokens=1024,
        reasoning="off",
    )
    seen: list[dict[str, object]] = []

    class _Resp:
        def __init__(self, body: dict[str, object]) -> None:
            self._raw = json.dumps(body).encode("utf-8")

        def read(self) -> bytes:
            return self._raw

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *args: object) -> bool:
            return False

    def fake_urlopen(req, _timeout, _cancel):
        payload = json.loads(req.data.decode("utf-8"))
        seen.append(payload)
        if len(seen) == 1:
            return _Resp({"choices": [{"finish_reason": "length", "message": {"content": ""}}]})
        if len(seen) in (2, 3):
            raise urllib.error.HTTPError(
                req.full_url,
                400,
                "Bad Request",
                {},
                io.BytesIO(b'{"error":{"message":"Reasoning is mandatory for this endpoint"}}'),
            )
        return _Resp({"choices": [{"finish_reason": "stop", "message": {"content": "Готово"}}]})

    client = LLMClient(cfg, sleep=lambda _s: None)
    with patch("case3.llm_client._urlopen_until_cancel", side_effect=fake_urlopen):
        out = client.complete(system="s", user_text="u")

    assert out == "Готово"
    assert seen[0].get("reasoning") == {"enabled": False}
    assert seen[1].get("reasoning") == {"enabled": False}
    assert seen[1]["max_tokens"] == 6144
    assert seen[2].get("reasoning") == {"effort": "low", "exclude": True}
    assert seen[2]["max_tokens"] == 6144
    assert "reasoning" not in seen[3]
    assert seen[3]["max_tokens"] == 6144


def test_abort_https_handler_works_without_check_hostname_attr() -> None:
    import urllib.request
    from case3.llm_client import _AbortHTTPSConnection, _AbortHTTPSHandler

    handler = _AbortHTTPSHandler()
    # Python 3.12+ removed self._check_hostname from urllib.request.HTTPSHandler.
    if hasattr(handler, "_check_hostname"):
        delattr(handler, "_check_hostname")

    captured: dict[str, object] = {}

    def fake_do_open(cls, req, **kwargs):  # type: ignore[no-untyped-def]
        captured["cls"] = cls
        captured["req"] = req
        captured["kwargs"] = kwargs
        return "ok"

    handler.do_open = fake_do_open  # type: ignore[method-assign]
    req = urllib.request.Request("https://example.com/v1/chat/completions")
    assert handler.https_open(req) == "ok"
    assert captured["cls"] is _AbortHTTPSConnection
    assert "check_hostname" not in captured["kwargs"]  # type: ignore[operator]
    assert "context" in captured["kwargs"]  # type: ignore[operator]
