"""G9: local live chart preview (palette/type) without LLM or disk write."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from case3 import api as api_mod
from case3.chart_edit import ChartEditError, preview_chart_html

_BAR_HTML = (
    '<canvas id="c1" width="1100" height="560"></canvas>'
    "<script>new Chart(document.getElementById('c1'),"
    "{type:'bar',data:{labels:['A','B'],datasets:[{data:[10,20],"
    "backgroundColor:['#1A4A4B','#5A6E28']}]},"
    "options:{animation:false}});"
    "window.__CASE3_CHART_READY=true;</script>"
)


def _seed_run(root: Path, run_id: str = "live_prev_20260101T000000Z") -> Path:
    out = root / "runs" / "out" / run_id
    out.mkdir(parents=True, exist_ok=True)
    fj = {
        "charts": [
            {
                "id": "cht_01",
                "type": "bar",
                "caption": "Выручка",
                "html": _BAR_HTML,
            }
        ],
        "figures": [],
    }
    (out / "figures.json").write_text(
        json.dumps(fj, ensure_ascii=False), encoding="utf-8"
    )
    (out / "demo.tex").write_text(
        r"\documentclass{article}\begin{document}Hi\end{document}",
        encoding="utf-8",
    )
    return out


def test_preview_palette_changes_html_colors(tmp_path: Path) -> None:
    out = _seed_run(tmp_path)
    result = preview_chart_html(out, "cht_01", palette="sunset", chart_type="bar")
    assert result["chart_id"] == "cht_01"
    assert result["type"] == "bar"
    assert result["palette"] == "sunset"
    assert "local_palette" in result["modes"]
    assert "#1A4A4B" not in result["html"] or "sunset" in result["palette"]
    # Sunset primary is warm; remapped HTML should differ from seed
    assert result["html"] != _BAR_HTML
    assert "backgroundColor" in result["html"]


def test_preview_type_change_is_local_coerce(tmp_path: Path) -> None:
    out = _seed_run(tmp_path)
    result = preview_chart_html(
        out, "cht_01", palette="ocean", chart_type="horizontal_bar"
    )
    assert result["type"] == "horizontal_bar"
    assert "type_change" in result["modes"] or "local_type" in result["modes"]
    assert "indexAxis" in result["html"]
    # Disk unchanged
    fj = json.loads((out / "figures.json").read_text(encoding="utf-8"))
    assert fj["charts"][0]["type"] == "bar"


def test_preview_missing_chart_raises(tmp_path: Path) -> None:
    out = _seed_run(tmp_path)
    with pytest.raises(ChartEditError):
        preview_chart_html(out, "cht_99", palette="atelier")


@pytest.fixture()
def client(api_client: TestClient) -> TestClient:
    return api_client


def test_api_get_chart_and_preview(client: TestClient, tmp_path: Path) -> None:
    run_id = "live_prev_20260101T000000Z"
    _seed_run(tmp_path, run_id)

    g = client.get(f"/api/runs/{run_id}/charts/cht_01")
    assert g.status_code == 200, g.text
    body = g.json()
    assert body["id"] == "cht_01"
    assert body["type"] == "bar"
    assert "canvas" in body["html"]

    p = client.post(
        f"/api/runs/{run_id}/charts/cht_01/preview",
        json={"palette": "ocean", "chart_type": "line"},
    )
    assert p.status_code == 200, p.text
    prev = p.json()
    assert prev["type"] == "line"
    assert prev["palette"] == "ocean"
    assert "html" in prev
    assert prev.get("style_deferred") is True
