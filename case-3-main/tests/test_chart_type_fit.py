"""Type change warns when the new chart cannot show the same data."""

from __future__ import annotations

import json
from pathlib import Path

from case3.chart_edit import preview_chart_html
from case3.chart_type_fit import (
    chart_number_change_warning,
    chart_type_change_warning,
)

_KPI = (
    '<div class="kpi"><div class="value">42</div>'
    '<div class="label">NPS</div></div>'
)

_BAR = (
    "<script>new Chart(c,{type:'bar',data:{labels:['A','B'],"
    "datasets:[{data:[10,20]}]}});</script>"
)

_ONE = (
    "<script>new Chart(c,{type:'bar',data:{labels:['A'],"
    "datasets:[{data:[10]}]}});</script>"
)

_MULTI = (
    "<script>new Chart(c,{type:'bar',data:{labels:['A','B'],"
    "datasets:[{label:'X',data:[10,20]},{label:'Y',data:[3,4]}]}});</script>"
)

_NEG = (
    "<script>new Chart(c,{type:'bar',data:{labels:['A','B'],"
    "datasets:[{data:[10,-2]}]}});</script>"
)


def test_leaving_kpi_warns() -> None:
    msg = chart_type_change_warning({"type": "kpi", "html": _KPI}, "bar")
    assert msg
    assert "KPI" in msg


def test_kpi_to_donut_does_not_invent_a_share() -> None:
    msg = chart_type_change_warning({"type": "kpi", "html": _KPI}, "donut")
    assert "Прочее" not in msg
    assert "одной доли" in msg


def test_same_type_is_silent() -> None:
    assert chart_type_change_warning({"type": "bar", "html": _BAR}, "bar") == ""


def test_bar_to_horizontal_is_silent() -> None:
    assert chart_type_change_warning({"type": "bar", "html": _BAR}, "horizontal_bar") == ""


def test_line_to_area_is_silent() -> None:
    html = _BAR.replace("bar", "line")
    assert chart_type_change_warning({"type": "line", "html": html}, "area") == ""


def test_two_points_to_line_is_silent() -> None:
    assert chart_type_change_warning({"type": "bar", "html": _BAR}, "line") == ""


def test_many_points_to_kpi_warns() -> None:
    msg = chart_type_change_warning({"type": "bar", "html": _BAR}, "kpi")
    assert msg
    assert "одно число" in msg


def test_one_point_to_kpi_is_silent() -> None:
    assert chart_type_change_warning({"type": "bar", "html": _ONE}, "kpi") == ""


def test_one_point_to_line_warns() -> None:
    msg = chart_type_change_warning({"type": "bar", "html": _ONE}, "line")
    assert msg
    assert "две" in msg


def test_donut_rejects_negatives() -> None:
    msg = chart_type_change_warning({"type": "bar", "html": _NEG}, "donut")
    assert msg
    assert "отрицательн" in msg


def test_donut_rejects_several_series() -> None:
    msg = chart_type_change_warning({"type": "grouped_bar", "html": _MULTI}, "donut")
    assert msg
    assert "ряд" in msg


def test_one_series_donut_is_silent() -> None:
    assert chart_type_change_warning({"type": "bar", "html": _BAR}, "donut") == ""


_SCATTER = (
    "<script>new Chart(c,{type:'scatter',data:{datasets:[{label:'T',"
    "data:[{x:1,y:12},{x:2,y:19}],backgroundColor:'#1A4A4B'}]}});</script>"
)


def test_categories_to_scatter_drop_labels() -> None:
    msg = chart_type_change_warning({"type": "bar", "html": _BAR}, "scatter")
    assert msg
    assert "0, 1, 2" in msg


def test_scatter_to_bar_drops_x() -> None:
    msg = chart_type_change_warning({"type": "scatter", "html": _SCATTER}, "bar")
    assert msg
    assert "ось X" in msg


def test_scatter_to_line_drops_x() -> None:
    msg = chart_type_change_warning({"type": "scatter", "html": _SCATTER}, "line")
    assert "ось X" in msg


def test_scatter_to_donut_drops_x() -> None:
    msg = chart_type_change_warning({"type": "scatter", "html": _SCATTER}, "donut")
    assert "ось X" in msg


def test_same_numbers_are_silent() -> None:
    assert chart_number_change_warning(_BAR, _BAR, chart_type="bar") == ""


def test_reordered_numbers_are_silent() -> None:
    swapped = _BAR.replace("[10,20]", "[20,10]")
    assert chart_number_change_warning(_BAR, swapped, chart_type="bar") == ""


def test_changed_numbers_warn() -> None:
    changed = _BAR.replace("[10,20]", "[10,25]")
    msg = chart_number_change_warning(_BAR, changed, chart_type="bar")
    assert msg
    assert "числа" in msg


def test_style_rewrite_stops_before_save_when_numbers_change(
    tmp_path: Path, monkeypatch
) -> None:
    from unittest.mock import MagicMock

    from case3.chart_edit import ChartNumberChange, edit_chart_in_run

    out = tmp_path / "runs" / "out" / "fit_20260101T000000Z"
    out.mkdir(parents=True)
    (out / "figures.json").write_text(
        json.dumps(
            {
                "charts": [
                    {
                        "id": "cht_01",
                        "type": "bar",
                        "caption": "Выручка",
                        "html": _BAR,
                        "palette": "editorial",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (out / "demo.tex").write_text(
        r"\documentclass{article}\begin{document}Hi\end{document}",
        encoding="utf-8",
    )
    (out / "meta.json").write_text("{}", encoding="utf-8")
    changed = _BAR.replace("[10,20]", "[10,25]")
    spy = MagicMock(return_value=changed)
    monkeypatch.setattr("case3.chart_edit.rewrite_chart_html_with_llm", spy)

    def _fake_png(chart, dest, work_dir=None):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"\x89PNG\r\n\x1a\n")
        return dest

    monkeypatch.setattr("case3.chart_edit.render_chart_png", _fake_png)
    monkeypatch.setattr(
        "case3.chart_edit.rebuild_run_docs",
        lambda *a, **k: {"pdf": Path("x.pdf")},
    )
    try:
        edit_chart_in_run(
            out,
            "cht_01",
            palette="editorial",
            style="поменяй масштаб",
            chart_type="bar",
            formats=set(),
        )
        raise AssertionError("expected ChartNumberChange")
    except ChartNumberChange as exc:
        assert "числа" in str(exc)
        assert "10,25" in exc.html or "10, 25" in exc.html
    stored = json.loads((out / "figures.json").read_text(encoding="utf-8"))
    assert "[10,20]" in stored["charts"][0]["html"] or "10,20" in stored["charts"][0]["html"]

    edit_chart_in_run(
        out,
        "cht_01",
        palette="editorial",
        style="поменяй масштаб",
        chart_type="bar",
        formats=set(),
        accepted_html=changed,
    )
    spy.assert_called_once()
    stored = json.loads((out / "figures.json").read_text(encoding="utf-8"))
    assert "25" in stored["charts"][0]["html"]


def test_preview_returns_the_warning(tmp_path: Path) -> None:
    out = tmp_path / "runs" / "out" / "fit_20260101T000000Z"
    out.mkdir(parents=True)
    (out / "figures.json").write_text(
        json.dumps(
            {
                "charts": [
                    {
                        "id": "cht_01",
                        "type": "kpi",
                        "caption": "NPS",
                        "html": _KPI,
                        "palette": "editorial",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = preview_chart_html(out, "cht_01", palette="editorial", chart_type="bar")
    assert result["type_warning"]
    assert "KPI" in result["type_warning"]
