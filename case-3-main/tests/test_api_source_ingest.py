"""POST /api/source/ingest contract."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from case3 import api as api_mod
from case3.source_ingest import (
    IngestDependencyError,
    IngestResult,
    ScanPdfError,
)


@pytest.fixture()
def client(api_client: TestClient) -> TestClient:
    return api_client


def test_ingest_txt_via_api(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fake(path: Path, **_kw: object) -> IngestResult:
        text = Path(path).read_text(encoding="utf-8")
        return IngestResult(markdown=text, format="txt", filename=Path(path).name)

    monkeypatch.setattr(api_mod, "file_to_markdown", _fake)
    r = client.post(
        "/api/source/ingest",
        files={"file": ("facts.txt", b"A 10\n\nB 20\n", "text/plain")},
    )
    assert r.status_code == 200
    data = r.json()
    assert "A 10" in data["markdown"]
    assert data["format"] == "txt"
    assert data["filename"] == "facts.txt"
    assert data["view_mode"] == "text"
    assert data["ingest_id"]
    assert data.get("preview_url") is None


def test_ingest_scan_pdf_returns_422(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(_path: Path, **_kw: object) -> IngestResult:
        raise ScanPdfError("В PDF нет пригодного текстового слоя")

    monkeypatch.setattr(api_mod, "file_to_markdown", _boom)
    r = client.post(
        "/api/source/ingest",
        files={"file": ("scan.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert r.status_code == 422
    assert "текстового слоя" in r.json()["detail"]


def test_ingest_missing_pypdfium2_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(_path: Path, **_kw: object) -> IngestResult:
        raise IngestDependencyError("pypdfium2 не установлен")

    monkeypatch.setattr(api_mod, "file_to_markdown", _boom)
    r = client.post(
        "/api/source/ingest",
        files={"file": ("t.pdf", b"%PDF", "application/pdf")},
    )
    assert r.status_code == 503
    assert "pypdfium2" in r.json()["detail"]


def test_ingest_rejects_empty_upload(client: TestClient) -> None:
    r = client.post(
        "/api/source/ingest",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert r.status_code == 400
