"""Every Liber chart type → native DOCX/PPTX or intentional PNG fallback."""

from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path

import pytest
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.util import Inches

from case3.chart_coerce import apply_type_to_chart
from case3.chart_html import CHART_TYPES
from case3.docx_charts import replace_docx_native_charts
from case3.slides_chart_data import NATIVE_CHART_TYPES, attach_series_ir
from case3.slides_pptx_charts import add_native_chart, add_native_kpi

FIX = Path(__file__).resolve().parent / "fixtures" / "docx_with_cht_pictures.docx"

_BAR_HTML = """
<canvas id="c1"></canvas>
<script>new Chart(document.getElementById('c1'),{type:'bar',data:{
labels:['A','B','C'],
datasets:[{label:'S1',data:[10,20,30]},{label:'S2',data:[5,15,25]}]
},options:{}});</script>
"""


@pytest.fixture
def seed_chart() -> dict:
    return {
        "id": "cht_01",
        "type": "bar",
        "caption": "Метрика",
        "html": _BAR_HTML,
    }


def test_coerce_attach_native_matrix(seed_chart: dict) -> None:
    """Each type: native-eligible get Series IR + add_native_chart.

    PPTX also renders kpi (editable text box) and scatter (XY chart) natively;
    DOCX keeps both as pictures (see test_docx_kpi_stays_picture).
    """
    for want in sorted(CHART_TYPES):
        chart = apply_type_to_chart(dict(seed_chart), want)
        ir = attach_series_ir(chart)
        if want == "kpi":
            assert ir is not None, "kpi: expected KPI IR"
            assert ir["type"] == "kpi"
            assert ir["value"], "kpi: value must be extracted"
            assert chart.get("series", {}).get("type") == "kpi"
            prs = Presentation()
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            ok = add_native_kpi(
                slide,
                ir,
                left=Inches(0.5),
                top=Inches(0.5),
                width=Inches(8),
                height=Inches(4.5),
                color=RGBColor(0x1F, 0x2A, 0x44),
            )
            assert ok, "kpi: add_native_kpi failed"
            texts = [sh.text_frame.text for sh in slide.shapes if sh.has_text_frame]
            assert any(ir["value"] in t for t in texts)
        elif want == "scatter":
            assert ir is not None, "scatter: expected XY IR"
            assert ir["type"] == "scatter"
            assert len(ir["series"][0]["points"]) >= 2
            assert chart.get("series", {}).get("type") == "scatter"
            prs = Presentation()
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            ok = add_native_chart(
                slide,
                ir,
                left=Inches(0.5),
                top=Inches(0.5),
                width=Inches(8),
                height=Inches(4.5),
            )
            assert ok, "scatter: add_native_chart failed"
            assert any(sh.has_chart for sh in slide.shapes)
        elif want in NATIVE_CHART_TYPES:
            assert ir is not None, f"{want}: expected Series IR"
            assert ir["type"] == want, f"{want}: IR type mismatch {ir['type']}"
            assert chart.get("series", {}).get("type") == want
            prs = Presentation()
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            ok = add_native_chart(
                slide,
                ir,
                left=Inches(0.5),
                top=Inches(0.5),
                width=Inches(8),
                height=Inches(4.5),
            )
            assert ok, f"{want}: add_native_chart failed"
        else:
            assert ir is None, f"{want}: must stay PNG (no Series IR)"
            assert "series" not in chart


def test_docx_native_after_type_change(tmp_path: Path, seed_chart: dict) -> None:
    if not FIX.is_file():
        pytest.skip("docx fixture missing")
    chart = apply_type_to_chart(dict(seed_chart), "horizontal_bar")
    attach_series_ir(chart)
    assert chart["series"]["type"] == "horizontal_bar"

    docx = tmp_path / "out.docx"
    shutil.copy2(FIX, docx)
    fj = tmp_path / "figures.json"
    fj.write_text(
        json.dumps({"charts": [chart]}, ensure_ascii=False),
        encoding="utf-8",
    )
    replaced = replace_docx_native_charts(
        docx,
        figures_path=fj,
        series_hexes=["#2E4208", "#4F6B14"],
    )
    assert "cht_01" in replaced
    with zipfile.ZipFile(docx) as zf:
        charts = [
            n for n in zf.namelist() if re.match(r"word/charts/chart\d+\.xml$", n)
        ]
        assert charts
        xml = zf.read(charts[0]).decode("utf-8")
        assert "numCache" in xml or "strCache" in xml
        assert "externalData" not in xml
        # horizontal_bar → OOXML barChart (clustered bars)
        assert "barChart" in xml


def test_docx_kpi_stays_picture(tmp_path: Path, seed_chart: dict) -> None:
    if not FIX.is_file():
        pytest.skip("docx fixture missing")
    chart = apply_type_to_chart(dict(seed_chart), "kpi")
    attach_series_ir(chart)
    docx = tmp_path / "out.docx"
    shutil.copy2(FIX, docx)
    fj = tmp_path / "figures.json"
    fj.write_text(json.dumps({"charts": [chart]}), encoding="utf-8")
    replaced = replace_docx_native_charts(docx, figures_path=fj)
    assert replaced == []
