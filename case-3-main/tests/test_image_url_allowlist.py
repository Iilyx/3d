"""Image bytes may come from the Image API host, not from an arbitrary URL."""

from __future__ import annotations

import base64
import socket
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from case3.image_api import ImageApiConfig, _download_url

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _cfg(*, allow: bool = False) -> ImageApiConfig:
    return ImageApiConfig(
        base_url="http://192.168.4.101:8000",
        timeout_s=5,
        max_images=1,
        width=64,
        height=64,
        steps=1,
        guidance=1.0,
        seed=0,
        allow_url_download=allow,
    )


def _public_dns(host, port, *args, **kwargs):  # noqa: ANN001
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port or 443))]


def _private_dns(host, port, *args, **kwargs):  # noqa: ANN001
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.1.1.5", port or 80))]


def test_foreign_public_url_is_blocked_without_flag(tmp_path: Path) -> None:
    dest = tmp_path / "a.png"
    with patch("case3.image_api.socket.getaddrinfo", side_effect=_public_dns):
        with patch("case3.image_api.httpx.Client") as client:
            client.return_value.__enter__.return_value.get.return_value = MagicMock(
                is_redirect=False, content=_PNG
            )
            with pytest.raises(RuntimeError, match="blocked"):
                _download_url("https://evil.example/a.png", dest, cfg=_cfg())
            client.assert_not_called()


def test_private_url_stays_blocked_even_with_flag(tmp_path: Path) -> None:
    dest = tmp_path / "b.png"
    with patch("case3.image_api.socket.getaddrinfo", side_effect=_private_dns):
        with pytest.raises(RuntimeError, match="blocked"):
            _download_url(
                "https://intranet.example/a.png",
                dest,
                cfg=_cfg(allow=True),
            )


def test_same_api_host_is_still_fetched(tmp_path: Path) -> None:
    dest = tmp_path / "c.png"
    resp = MagicMock(is_redirect=False, content=_PNG)
    resp.raise_for_status.return_value = None
    client = MagicMock()
    client.__enter__.return_value.get.return_value = resp
    client.__exit__.return_value = False
    with patch("case3.image_api.httpx.Client", return_value=client):
        _download_url(
            "http://192.168.4.101:8000/outputs/a.png",
            dest,
            cfg=_cfg(),
        )
    client.__enter__.return_value.get.assert_called_once()
