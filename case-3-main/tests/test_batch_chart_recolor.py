import json
from pathlib import Path
from fastapi.testclient import TestClient

from case3.api import app
from case3 import run_store
from case3.chart_edit import recolor_all_charts_in_run


SAMPLE_CHART_HTML = """
<canvas id="c1" width="400" height="300"></canvas>
<script>
new Chart(document.getElementById('c1'), {
  type: 'bar',
  data: {
    labels: ['Q1', 'Q2', 'Q3'],
    datasets: [{
      label: 'Выручка',
      data: [100, 150, 200],
      backgroundColor: '#2E4208'
    }]
  }
});
</script>
"""

SAMPLE_KPI_HTML = """
<div class="kpi" style="--kpi-value:#2E4208">
  <div class="kpi-card">
    <div class="kpi-num">42%</div>
    <div class="kpi-lbl">Рост</div>
  </div>
</div>
"""


def _setup_run(tmp_path: Path, run_id: str) -> Path:
    out_dir = tmp_path / "runs" / "out" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    figs_dir = out_dir / "figures"
    figs_dir.mkdir(parents=True, exist_ok=True)

    fj = {
        "charts": [
            {
                "id": "cht_01",
                "type": "bar",
                "palette": "atelier",
                "caption": "Динамика выручки",
                "html": SAMPLE_CHART_HTML,
            },
            {
                "id": "cht_02",
                "type": "kpi",
                "palette": "atelier",
                "caption": "Ключевые показатели",
                "html": SAMPLE_KPI_HTML,
            },
        ],
        "figures": [],
        "diagrams": [],
    }
    (out_dir / "figures.json").write_text(
        json.dumps(fj, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "ok",
                "chart_palette": "atelier",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (out_dir / "report.tex").write_text(
        r"\documentclass{article}\begin{document}Hello\end{document}",
        encoding="utf-8",
    )
    return out_dir


def test_recolor_all_charts_in_run(tmp_path: Path, monkeypatch) -> None:
    run_id = "run_test_recolor"
    out_dir = _setup_run(tmp_path, run_id)

    # Mock render_chart_png to avoid running real Chromium in quick unit test
    def _mock_render(html: str, dest: Path) -> None:
        dest.write_bytes(b"\x89PNG\r\n\x1a\n")

    monkeypatch.setattr("case3.chart_edit.render_chart_png", _mock_render)

    res = recolor_all_charts_in_run(out_dir, palette="ocean")
    assert res["ok"] is True
    assert res["palette"] == "ocean"
    assert res["charts_recolored"] == 2

    # Verify figures.json updated
    fj_after = json.loads((out_dir / "figures.json").read_text(encoding="utf-8"))
    for c in fj_after["charts"]:
        assert c["palette"] == "ocean"
        assert c["style_user"] is True

    # Verify meta.json updated
    meta_after = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta_after["chart_palette"] == "ocean"

    # Verify PNGs were written
    assert (out_dir / "figures" / "cht_01.png").is_file()
    assert (out_dir / "figures" / "cht_02.png").is_file()


def test_api_recolor_endpoint(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(run_store, "ROOT", tmp_path)
    run_id = "run_api_recolor"
    out_dir = _setup_run(tmp_path, run_id)

    def _mock_render(html: str, dest: Path) -> None:
        dest.write_bytes(b"\x89PNG\r\n\x1a\n")

    monkeypatch.setattr("case3.chart_edit.render_chart_png", _mock_render)

    client = TestClient(app)
    res = client.post(
        f"/api/runs/{run_id}/charts/recolor",
        json={"palette": "sunset", "formats": "none"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["palette"] == "sunset"
    assert data["charts_recolored"] == 2

    meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["chart_palette"] == "sunset"
