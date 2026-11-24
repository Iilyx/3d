"""IMAGE_MAX_IMAGES defaults when Image API URL is set (Win desk gotcha)."""

from __future__ import annotations

import pytest

from case3.image_api import ImageApiConfig, max_images_from_env


def test_max_images_defaults_to_2_when_url_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IMAGE_API_BASE_URL", "http://192.168.4.101:8000")
    monkeypatch.delenv("IMAGE_MAX_IMAGES", raising=False)
    monkeypatch.delenv("KANDINSKY_MAX_IMAGES", raising=False)
    assert max_images_from_env() == 2
    assert ImageApiConfig.from_env().max_images == 2


def test_max_images_stays_0_when_url_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("IMAGE_API_BASE_URL", raising=False)
    monkeypatch.delenv("KANDINSKY_API_BASE_URL", raising=False)
    monkeypatch.delenv("IMAGE_MAX_IMAGES", raising=False)
    monkeypatch.delenv("KANDINSKY_MAX_IMAGES", raising=False)
    assert max_images_from_env() == 0


def test_explicit_zero_still_disables_photos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IMAGE_API_BASE_URL", "http://192.168.4.101:8000")
    monkeypatch.setenv("IMAGE_MAX_IMAGES", "0")
    assert max_images_from_env() == 0
