"""POST /api/dashboard/parse — settings drop of a dashboard PNG and table PDF."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from case3.dashboard_source import DashboardSource, DashboardSourceError
from tests.test_dashboard_source import _tiny_png, _write_grid_pdf


def test_parse_route_reads_a_real_pdf_table(
    api_client: TestClient, tmp_path: Path
) -> None:
    path = tmp_path / "wide.pdf"
    _write_grid_pdf(
        path,
        [["c0", "c1"], ["1 234,56", "77"]],
        caption="January 2025 payments table",
    )
    response = api_client.post(
        "/api/dashboard/parse",
        files={"pdf": ("table.pdf", path.read_bytes(), "application/pdf")},
    )
    assert response.status_code == 200
    data = response.json()
    assert "1 234,56" in data["markdown"]
    assert "1 234,56" in data["pdf_markdown"]
    assert data["png_markdown"] == ""
    assert data["pdf_table_count"] == 1
    assert data["warnings"] == []


def test_parse_route_returns_screen_and_table(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fake(*, png: bytes | None = None, pdf: bytes | None = None, vision=None):
        assert png is not None and png.startswith(b"\x89PNG")
        assert pdf is not None and pdf.startswith(b"%PDF")
        assert vision is None
        return DashboardSource(
            markdown="# Данные дашборда\n\n## Экран\n\nБрест\n",
            png_markdown="Брест\n",
            pdf_markdown="| НДС | 10 |\n",
            warnings=["шапка повторилась"],
            pdf_table_count=1,
            pdf_numeric_cells=4,
        )

    monkeypatch.setattr("case3.api.parse_dashboard", _fake)
    response = api_client.post(
        "/api/dashboard/parse",
        files={
            "png": ("dash.png", _tiny_png(), "image/png"),
            "pdf": ("table.pdf", b"%PDF-1.4", "application/pdf"),
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "Брест" in data["markdown"]
    assert data["pdf_markdown"].startswith("| НДС")
    assert data["warnings"] == ["шапка повторилась"]
    assert data["pdf_numeric_cells"] == 4


def test_parse_route_maps_scan_to_422(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*, png=None, pdf=None, vision=None):
        raise DashboardSourceError(
            "В PDF нет текстового слоя.",
            code="scan_pdf",
        )

    monkeypatch.setattr("case3.api.parse_dashboard", _boom)
    response = api_client.post(
        "/api/dashboard/parse",
        files={"pdf": ("scan.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert response.status_code == 422
    assert "текстового слоя" in response.json()["detail"]


def test_parse_route_rejects_an_empty_drop(api_client: TestClient) -> None:
    response = api_client.post("/api/dashboard/parse")
    assert response.status_code == 400
