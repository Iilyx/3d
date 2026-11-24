"""LLMClient honors optional cancel_check between attempts."""

from __future__ import annotations

from case3.llm_client import LLMClient, LLMConfig
from case3.run_cancel import RunCancelled


def test_complete_cancel_check_before_request() -> None:
    cfg = LLMConfig(
        base_url="http://127.0.0.1:9",
        api_key="x",
        model="test",
        max_tokens=16,
        timeout_s=1,
        max_retries=0,
    )
    client = LLMClient(cfg)

    def _boom() -> None:
        raise RunCancelled("cancelled by user")

    try:
        client.complete(
            system="s",
            user_text="u",
            cancel_check=_boom,
        )
        raise AssertionError("expected RunCancelled")
    except RunCancelled:
        pass
