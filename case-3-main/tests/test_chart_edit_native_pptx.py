"""Original + regenerated charts stay native-editable in PPTX (and DOCX)."""

from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from case3.chart_coerce import apply_type_to_chart
from case3.slides_chart_data import NATIVE_CHART_TYPES, attach_series_ir
from case3.slides_pptx_native import build_native_pptx

_BAR_HTML = """
<canvas id="c1"></canvas>
<script>new Chart(document.getElementById('c1'),{type:'bar',data:{
labels:['Q1','Q2','Q3'],
datasets:[{label:'Rev',data:[10,20,30],backgroundColor:['#2E4208','#4F6B14','#7A9A28']}]
},options:{}});</script>
"""

DOCX_FIX = Path(__file__).resolve().parent / "fixtures" / "docx_with_cht_pictures.docx"

_STYLE = {
    "pack_id": "atelier",
    "colors": {
        "primary": "#2E4208",
        "accent": "#4F6B14",
        "ink": "#14161a",
        "ink2": "#2c3028",
        "muted": "#6A7160",
        "paper": "#f0ede4",
        "sheet": "#fffcf7",
        "rule": "#e6e2d8",
    },
    "fonts": {"title": "Georgia", "body": "Calibri", "fallback_pptx": "Calibri"},
    "chart_series": ["#2E4208", "#4F6B14", "#7A9A28"],
}


def _deck(cid: str = "cht_01") -> dict:
    return {
        "version": 1,
        "aspect": "16:9",
        "palette": "atelier",
        "style": _STYLE,
        "slides": [
            {
                "id": "s1",
                "layout": "chart_hero",
                "title": "Revenue",
                "chart_id": cid,
                "takeaway": "Up",
            }
        ],
    }


def _ooxml_hint(ctype: str) -> str:
    t = (ctype or "bar").lower()
    if t == "line":
        return "lineChart"
    if t == "area":
        return "areaChart"
    if t == "donut":
        return "doughnutChart"
    if t == "horizontal_bar":
        return "barChart"
    if t == "stacked_bar":
        return "barChart"
    # clustered column
    return "barChart"


def test_original_and_regenerated_types_are_native_in_pptx(tmp_path: Path) -> None:
    """First bar + each native regen type → ppt/charts/* with matching OOXML kind."""
    chart0 = {
        "id": "cht_01",
        "type": "bar",
        "caption": "Выручка",
        "html": _BAR_HTML,
    }
    assert attach_series_ir(chart0) is not None
    assert chart0["series"]["type"] == "bar"

    dest0 = tmp_path / "orig.pptx"
    build_native_pptx(
        _deck(),
        dest0,
        chart_series_by_id={"cht_01": chart0["series"]},
    )
    with zipfile.ZipFile(dest0) as zf:
        parts = [n for n in zf.namelist() if re.match(r"ppt/charts/chart\d+\.xml$", n)]
        assert parts
        xml0 = zf.read(parts[0]).decode("utf-8")
        assert "barChart" in xml0

    for want in sorted(NATIVE_CHART_TYPES):
        chart = apply_type_to_chart(
            {
                "id": "cht_01",
                "type": "bar",
                "caption": "Выручка",
                "html": _BAR_HTML,
                "series": chart0["series"],  # stale bar IR — must refresh
            },
            want,
        )
        ir = attach_series_ir(chart)
        assert ir is not None, want
        assert ir["type"] == want, f"{want}: got {ir['type']}"
        dest = tmp_path / f"{want}.pptx"
        build_native_pptx(
            _deck(),
            dest,
            chart_series_by_id={"cht_01": ir},
        )
        with zipfile.ZipFile(dest) as zf:
            parts = [
                n for n in zf.namelist() if re.match(r"ppt/charts/chart\d+\.xml$", n)
            ]
            assert parts, f"{want}: no native chart part"
            xml = zf.read(parts[0]).decode("utf-8")
            hint = _ooxml_hint(want)
            assert hint in xml, f"{want}: expected {hint} in OOXML"


def test_edit_chart_in_run_refreshes_series_and_deck(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Liber type edit writes new Series IR and triggers deck refresh."""
    from case3.chart_edit import edit_chart_in_run

    # parents[2] from runs/out/<id> → project root
    out = tmp_path / "runs" / "out" / "native_edit_20260101T000000Z"
    out.mkdir(parents=True)
    figs = out / "figures"
    figs.mkdir()
    (figs / "cht_01.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)
    fj = {
        "charts": [
            {
                "id": "cht_01",
                "type": "bar",
                "caption": "Выручка",
                "html": _BAR_HTML,
                "palette": "editorial",
                "series": {
                    "type": "bar",
                    "categories": ["Q1", "Q2", "Q3"],
                    "series": [{"name": "Rev", "values": [10.0, 20.0, 30.0]}],
                },
            }
        ],
        "figures": [],
    }
    (out / "figures.json").write_text(json.dumps(fj), encoding="utf-8")
    (out / "demo.tex").write_text(
        r"\documentclass{article}\begin{document}Hi\end{document}",
        encoding="utf-8",
    )
    (out / "meta.json").write_text("{}", encoding="utf-8")
    slides = out / "slides"
    slides.mkdir()
    (slides / "deck.json").write_text(json.dumps(_deck()), encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    refreshed = {"n": 0}

    def fake_png(chart, dest, work_dir=None):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8)
        return dest

    def fake_refresh(out_dir: Path) -> bool:
        refreshed["n"] += 1
        return True

    with (
        patch("case3.chart_edit.render_chart_png", side_effect=fake_png),
        patch(
            "case3.chart_edit.rebuild_run_docs",
            return_value={"pdf": out / "demo.pdf"},
        ),
        patch("case3.deck_refresh.refresh_deck_from_ir", side_effect=fake_refresh),
        patch("case3.run_undo.capture_before_edit"),
        patch("case3.run_undo.undo_meta", return_value={"can_undo": True}),
    ):
        edit_chart_in_run(
            out,
            "cht_01",
            palette="editorial",
            style="",
            chart_type="donut",
            formats={"pdf"},
        )

    assert refreshed["n"] == 1
    saved = json.loads((out / "figures.json").read_text(encoding="utf-8"))
    series = saved["charts"][0]["series"]
    assert series["type"] == "donut"
    assert len(series["series"]) == 1

    # Native PPTX from post-edit IR
    dest = tmp_path / "after_edit.pptx"
    build_native_pptx(
        _deck(),
        dest,
        chart_series_by_id={"cht_01": series},
    )
    with zipfile.ZipFile(dest) as zf:
        parts = [n for n in zf.namelist() if re.match(r"ppt/charts/chart\d+\.xml$", n)]
        assert parts
        assert "doughnutChart" in zf.read(parts[0]).decode("utf-8")


def test_docx_native_after_regen_to_line(tmp_path: Path) -> None:
    if not DOCX_FIX.is_file():
        pytest.skip("docx fixture missing")
    from case3.docx_charts import replace_docx_native_charts

    chart = apply_type_to_chart(
        {"id": "cht_01", "type": "bar", "caption": "Тренд", "html": _BAR_HTML},
        "line",
    )
    attach_series_ir(chart)
    assert chart["series"]["type"] == "line"
    docx = tmp_path / "out.docx"
    shutil.copy2(DOCX_FIX, docx)
    fj = tmp_path / "figures.json"
    fj.write_text(json.dumps({"charts": [chart]}), encoding="utf-8")
    replaced = replace_docx_native_charts(
        docx,
        figures_path=fj,
        series_hexes=["#2E4208", "#4F6B14"],
    )
    assert "cht_01" in replaced
    with zipfile.ZipFile(docx) as zf:
        charts = [n for n in zf.namelist() if re.match(r"word/charts/chart\d+\.xml$", n)]
        assert charts
        xml = zf.read(charts[0]).decode("utf-8")
        assert "lineChart" in xml
        assert "externalData" not in xml
