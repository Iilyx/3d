"""POST /slides must not wipe structure/pack stamped by /api/run."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(api_client: TestClient) -> TestClient:
    return api_client


def _seed(tmp_path: Path, run_id: str) -> Path:
    out = tmp_path / "runs" / "out" / run_id
    out.mkdir(parents=True)
    src = tmp_path / "runs" / "uploads" / run_id / "source.txt"
    src.parent.mkdir(parents=True)
    src.write_text("Выручка 120 млн.", encoding="utf-8")
    (out / "meta.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "ok",
                "stage": "ok",
                "source": str(src),
                "intent": "дек",
                "slides_theme_pack": "board",
                "slides_structure_id": "board_update",
                "slides_style": {
                    "theme_pack": "board",
                    "structure_id": "board_update",
                    "style_settings": {"primary": "#142C40", "accent": "#087F8C"},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (out / "report.pdf").write_bytes(b"%PDF-1.4 fake")
    return out


def test_post_slides_without_structure_keeps_desk_structure(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Liber UI kick often omits structure_id; must not freeform-collapse the deck."""
    run_id = "run_keep_struct"
    out = _seed(tmp_path, run_id)

    monkeypatch.setattr(
        "case3.api_slides._kick_slides_thread", lambda *_a, **_k: None
    )

    # Body like deckStyleToApiPayload when structureId missing from a stale closure
    r = client.post(
        f"/api/runs/{run_id}/slides",
        json={
            "theme_pack": "atelier",
            "style_settings": {
                "primary": "#2E4208",
                "accent": "#4F6B14",
                "background": "#FFFCF7",
                "text": "#14161A",
            },
        },
    )
    assert r.status_code == 202, r.text
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    ss = meta.get("slides_style") or {}
    assert meta.get("slides_structure_id") == "board_update"
    assert ss.get("structure_id") == "board_update"
    # Default atelier body must not clobber desk-stamped board pack
    assert meta.get("slides_theme_pack") == "board"
    assert ss.get("theme_pack") == "board"
    assert (ss.get("style_settings") or {}).get("primary") == "#142C40"


def test_atelier_motif_has_no_forced_split() -> None:
    from case3.deck_theme import resolve_deck_theme

    motif = resolve_deck_theme("atelier").as_dict()["motif"]
    assert "split" not in motif
    relay = resolve_deck_theme("relay").as_dict()["motif"]
    assert "split" in relay


def test_post_slides_explicit_structure_overrides(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = "run_override_struct"
    out = _seed(tmp_path, run_id)
    monkeypatch.setattr(
        "case3.api_slides._kick_slides_thread", lambda *_a, **_k: None
    )
    r = client.post(
        f"/api/runs/{run_id}/slides",
        json={
            "theme_pack": "botanical",
            "structure_id": "investor",
            "style_settings": {"primary": "#1A3026"},
        },
    )
    assert r.status_code == 202, r.text
    meta = json.loads((out / "meta.json").read_text(encoding="utf-8"))
    assert meta.get("slides_structure_id") == "investor"
    assert meta.get("slides_theme_pack") == "botanical"
