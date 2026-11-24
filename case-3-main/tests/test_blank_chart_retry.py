"""Blank chart screenshot → one relaunch retry (post-Image-API flake)."""

from __future__ import annotations

from case3.charts import is_blank_chart_error


def test_blank_chart_error_detected() -> None:
    assert is_blank_chart_error(
        RuntimeError("blank chart screenshot: {'ok': False, 'reason': 'canvas painted=0'}")
    )
    assert is_blank_chart_error(RuntimeError("blank chart screenshot: empty mount"))


def test_other_errors_not_blank() -> None:
    assert not is_blank_chart_error(RuntimeError("playwright not installed"))
    assert not is_blank_chart_error(RuntimeError("chart png too large: 999"))
    # Marker alone is not enough — wrong exception type stays non-retryable
    assert not is_blank_chart_error(ValueError("blank chart screenshot: x"))
    assert not is_blank_chart_error(OSError("blank chart screenshot: x"))
