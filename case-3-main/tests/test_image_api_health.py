"""G1: live Image API health probe."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from case3.image_api import probe_image_api


def test_probe_empty_base_not_ok() -> None:
    with patch.dict("os.environ", {"IMAGE_API_BASE_URL": ""}, clear=False):
        # Also clear alias if present
        with patch("case3.image_api.ImageApiConfig.from_env") as fe:
            fe.return_value = MagicMock(base_url="", health_url="")
            ok, err = probe_image_api(timeout_s=0.5)
            assert ok is False
            assert err


def test_probe_ok_on_200() -> None:
    cfg = MagicMock()
    cfg.base_url = "http://image.test"
    cfg.health_url = "http://image.test/"
    with patch("case3.image_api.ImageApiConfig.from_env", return_value=cfg):
        with patch("case3.image_api.httpx.Client") as client_cls:
            client = MagicMock()
            resp = MagicMock()
            resp.status_code = 200
            client.get.return_value = resp
            client.__enter__.return_value = client
            client.__exit__.return_value = False
            client_cls.return_value = client
            ok, err = probe_image_api(timeout_s=0.5)
            assert ok is True
            assert err is None


def test_probe_down_on_connect_error() -> None:
    cfg = MagicMock()
    cfg.base_url = "http://image.test"
    cfg.health_url = "http://image.test/"
    with patch("case3.image_api.ImageApiConfig.from_env", return_value=cfg):
        with patch("case3.image_api.httpx.Client") as client_cls:
            client = MagicMock()
            client.get.side_effect = ConnectionError("refused")
            client.__enter__.return_value = client
            client.__exit__.return_value = False
            client_cls.return_value = client
            ok, err = probe_image_api(timeout_s=0.5)
            assert ok is False
            assert "refused" in (err or "").lower() or err
