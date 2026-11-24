"""CASE3_MAX_DIAGRAMS is the only diagrams ceiling (default 5, clamp 0–5)."""

import pytest

from case3.diagrams import DIAGRAMS_HARD_MAX, max_diagrams_from_env


def test_hard_max_is_five() -> None:
    assert DIAGRAMS_HARD_MAX == 5


def test_default_is_five(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CASE3_MAX_DIAGRAMS", raising=False)
    assert max_diagrams_from_env() == 5


def test_env_clamped_to_hard_max(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASE3_MAX_DIAGRAMS", "99")
    assert max_diagrams_from_env() == 5


def test_env_zero_disables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASE3_MAX_DIAGRAMS", "0")
    assert max_diagrams_from_env() == 0


def test_env_five_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CASE3_MAX_DIAGRAMS", "5")
    assert max_diagrams_from_env() == 5
