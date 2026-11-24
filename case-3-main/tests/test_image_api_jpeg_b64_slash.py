"""JPEG base64 starts with /9j/ — must not be treated as a relative path."""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

from PIL import Image

from case3.image_api import ImageApiConfig, decode_image_string


def _tiny_jpeg() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (2, 2), (200, 30, 30)).save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def test_jpeg_b64_with_slash_prefix_decodes(tmp_path: Path) -> None:
    cfg = ImageApiConfig(
        base_url="http://127.0.0.1:8787",
        timeout_s=5,
        max_images=2,
        width=64,
        height=64,
        steps=1,
        guidance=1.0,
        seed=0,
        allow_url_download=False,
    )
    b64 = base64.b64encode(_tiny_jpeg()).decode("ascii")
    assert b64.startswith("/9j")
    dest = tmp_path / "out.png"
    decode_image_string({"image": b64}, cfg=cfg, dest=dest)
    assert dest.is_file()
    assert dest.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
