"""API figure generation must not let uploads consume the max_images slice."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from case3.image_api import ImageApiConfig, generate_all_figures

_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_uploads_do_not_block_api_slots(tmp_path: Path) -> None:
    # Naive figures[:max_images] with max=3 would be fine; with max=2 it hid fig_01
    # behind two uploads. Remaining budget after uploads must still call /generate.
    figs = [
        {"id": "usr_01", "source": "upload", "prompt": "skip"},
        {"id": "usr_02", "source": "upload", "prompt": "skip"},
        {"id": "fig_01", "prompt": "a cat"},
    ]
    cfg = ImageApiConfig(
        base_url="http://127.0.0.1:9",
        max_images=3,
        timeout_s=1,
        width=64,
        height=64,
        steps=1,
        guidance=1.0,
        seed=0,
        allow_url_download=False,
    )
    called: list[str] = []

    def fake_generate(c, prompt, dest, **kwargs):
        called.append(prompt)
        dest.write_bytes(_PNG)

    with (
        patch("case3.image_api.probe_image_api", return_value=(True, None)),
        patch("case3.image_api.generate_png", side_effect=fake_generate),
    ):
        st = generate_all_figures(figs, tmp_path, cfg=cfg)

    assert called == ["a cat"]
    assert st["fig_01"]["ok"] is True
    assert (tmp_path / "fig_01.png").is_file()
