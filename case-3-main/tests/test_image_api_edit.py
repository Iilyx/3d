"""Office /edit sends multipart file first (FastAPI UploadFile), then JSON/form fallbacks."""

from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from case3.image_api import ImageApiConfig, edit_png

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _cfg() -> ImageApiConfig:
    return ImageApiConfig(
        base_url="http://192.168.4.101:8000",
        timeout_s=5,
        max_images=2,
        width=512,
        height=512,
        steps=4,
        guidance=3.0,
        seed=0,
        allow_url_download=False,
    )


def test_edit_png_sends_multipart_first(tmp_path: Path) -> None:
    src = tmp_path / "fig.png"
    dest = tmp_path / "out.png"
    src.write_bytes(_PNG)

    calls: list[dict] = []

    class _Resp:
        def __init__(self, code: int, body: bytes, ctype: str = "image/png") -> None:
            self.status_code = code
            self.content = body
            self.headers = {"content-type": ctype}
            self.text = ""

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    "err", request=MagicMock(), response=MagicMock(status_code=self.status_code)
                )

    def _post(url: str, **kwargs):
        calls.append({"url": url, **{k: kwargs.get(k) for k in ("data", "files", "json")}})
        # first call: multipart with image file -> return PNG bytes
        if kwargs.get("files") and "image" in kwargs["files"]:
            return _Resp(200, _PNG)
        return _Resp(422, b"nope", "application/json")

    client = MagicMock()
    client.__enter__ = lambda s: s
    client.__exit__ = MagicMock(return_value=False)
    client.post = _post

    with patch("case3.image_api.httpx.Client", return_value=client):
        edit_png(_cfg(), "warmer light", src, dest)

    assert dest.read_bytes().startswith(b"\x89PNG")
    assert calls, "expected at least one POST"
    assert calls[0]["url"].endswith("/edit")
    assert calls[0]["files"] is not None
    assert "image" in calls[0]["files"]


def test_edit_png_falls_back_to_json_and_form(tmp_path: Path) -> None:
    src = tmp_path / "fig.png"
    dest = tmp_path / "out.png"
    src.write_bytes(_PNG)

    calls: list[dict] = []

    class _Resp:
        def __init__(self, code: int, body: bytes, ctype: str = "image/png") -> None:
            self.status_code = code
            self.content = body
            self.headers = {"content-type": ctype}
            self.text = "test-error"

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise httpx.HTTPStatusError(
                    "err", request=MagicMock(), response=MagicMock(status_code=self.status_code)
                )

    def _post(url: str, **kwargs):
        calls.append({"url": url, **{k: kwargs.get(k) for k in ("data", "files", "json")}})
        # multipart fails, json succeeds
        if kwargs.get("json") and "image" in kwargs["json"]:
            return _Resp(200, _PNG)
        return _Resp(422, b"nope", "application/json")

    client = MagicMock()
    client.__enter__ = lambda s: s
    client.__exit__ = MagicMock(return_value=False)
    client.post = _post

    with patch("case3.image_api.httpx.Client", return_value=client):
        edit_png(_cfg(), "warmer light", src, dest)

    assert dest.read_bytes().startswith(b"\x89PNG")
    assert len(calls) == 2
    assert calls[0]["files"] is not None
    assert calls[1]["json"] is not None
    assert isinstance(calls[1]["json"]["image"], list)

