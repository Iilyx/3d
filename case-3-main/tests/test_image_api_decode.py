"""Decode Image API string payloads without network."""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from case3.image_api import ImageApiConfig, _parse_http_body, decode_image_string

# 1x1 PNG
_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _cfg() -> ImageApiConfig:
    return ImageApiConfig(
        base_url="http://192.168.4.101:8000",
        timeout_s=5,
        max_images=2,
        width=1024,
        height=1024,
        steps=4,
        guidance=3.0,
        seed=0,
        allow_url_download=False,
    )


def test_decode_raw_base64(tmp_path: Path) -> None:
    dest = tmp_path / "a.png"
    decode_image_string(base64.b64encode(_PNG).decode(), cfg=_cfg(), dest=dest)
    assert dest.read_bytes().startswith(b"\x89PNG")


def test_decode_data_url(tmp_path: Path) -> None:
    dest = tmp_path / "b.png"
    b64 = base64.b64encode(_PNG).decode()
    decode_image_string(f"data:image/png;base64,{b64}", cfg=_cfg(), dest=dest)
    assert dest.read_bytes() == _PNG


def test_decode_json_string_wrapper(tmp_path: Path) -> None:
    dest = tmp_path / "c.png"
    # FastAPI Response[str] often arrives already unquoted via json.loads
    decode_image_string({"image": base64.b64encode(_PNG).decode()}, cfg=_cfg(), dest=dest)
    assert dest.is_file()


def test_decode_relative_path_without_leading_slash(tmp_path: Path) -> None:
    """Office wrappers often return 'outputs/foo.png' (not base64, not absolute URL)."""
    dest = tmp_path / "d.png"

    def _fake_download(url: str, dest_path: Path, *, cfg: ImageApiConfig) -> None:
        assert url == "http://192.168.4.101:8000/outputs/foo.png"
        dest_path.write_bytes(_PNG)

    with patch("case3.image_api._download_url", side_effect=_fake_download):
        decode_image_string("outputs/foo.png", cfg=_cfg(), dest=dest)
    assert dest.read_bytes().startswith(b"\x89PNG")


def test_parse_http_body_raw_png() -> None:
    resp = MagicMock()
    resp.headers = {"content-type": "image/png"}
    resp.content = _PNG
    resp.text = "should-not-use"
    assert _parse_http_body(resp) == _PNG


def test_decode_invalid_string_mentions_snippet(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="not base64"):
        decode_image_string("кот-не-картинка", cfg=_cfg(), dest=tmp_path / "e.png")


def test_rewrite_loopback_url_to_api_base(tmp_path: Path) -> None:
    """Office API often returns http://127.0.0.1:8000/... — must hit IMAGE_API host."""
    from case3.image_api import _rewrite_loopback_url

    assert (
        _rewrite_loopback_url(
            "http://127.0.0.1:8000/outputs/a.png",
            "http://192.168.4.101:8000",
        )
        == "http://192.168.4.101:8000/outputs/a.png"
    )
    dest = tmp_path / "f.png"

    def _fake_download(url: str, dest_path: Path, *, cfg: ImageApiConfig) -> None:
        assert url == "http://192.168.4.101:8000/outputs/a.png"
        dest_path.write_bytes(_PNG)

    with patch("case3.image_api._download_url", side_effect=_fake_download):
        decode_image_string(
            "http://127.0.0.1:8000/outputs/a.png", cfg=_cfg(), dest=dest
        )
    assert dest.read_bytes().startswith(b"\x89PNG")
