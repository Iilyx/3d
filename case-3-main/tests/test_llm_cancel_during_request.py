"""Stop must leave complete() while the model HTTP call is still blocked."""

from __future__ import annotations

import threading
import time
from unittest.mock import patch

import pytest

from case3.llm_client import LLMClient, LLMConfig
from case3.run_cancel import RunCancelled


def test_complete_raises_cancel_while_urlopen_is_blocked() -> None:
    cfg = LLMConfig(
        base_url="http://127.0.0.1:9",
        api_key="x",
        model="test",
        max_tokens=16,
        timeout_s=30,
        max_retries=0,
    )
    client = LLMClient(cfg)
    started = threading.Event()

    def _hang(req, timeout=None):  # noqa: ANN001
        started.set()
        time.sleep(2.5)
        raise AssertionError("request should have been abandoned")

    def _cancel() -> None:
        if started.is_set():
            raise RunCancelled("cancelled by user")

    t0 = time.monotonic()
    with patch("case3.llm_client.urllib.request.urlopen", side_effect=_hang):
        with pytest.raises(RunCancelled):
            client.complete(system="s", user_text="u", cancel_check=_cancel)
    assert time.monotonic() - t0 < 1.5
