"""Say when a chart type change cannot show the stored numbers.

Local rules only. The edit still proceeds if the user confirms.
"""

from __future__ import annotations

import re
from typing import Any

from case3.chart_harden import _is_kpi_html
from case3.chart_html import CHART_TYPES
from case3.slides_chart_data import _SCATTER_POINT, extract_chart_series


def _shape(chart: dict[str, Any]) -> dict[str, Any]:
    ctype = str(chart.get("type") or "").strip()
    html = str(chart.get("html") or "")
    if ctype == "kpi" or _is_kpi_html(html):
        return {"kind": "kpi", "points": 1, "series": 1, "negative": False}
    if ctype == "scatter":
        pts = _SCATTER_POINT.findall(html)
        ys = [float(y) for _x, y in pts]
        return {
            "kind": "scatter",
            "points": len(pts),
            "series": 1,
            "negative": any(y < 0 for y in ys),
        }
    ir = extract_chart_series(html, chart_type=ctype or "bar")
    if not ir or ir.get("type") == "kpi":
        return {"kind": "unknown", "points": 0, "series": 0, "negative": False}
    if ir.get("type") == "scatter":
        pts = list((ir.get("series") or [{}])[0].get("points") or [])
        ys = [float(p.get("y") or 0) for p in pts if isinstance(p, dict)]
        return {
            "kind": "scatter",
            "points": len(pts),
            "series": 1,
            "negative": any(y < 0 for y in ys),
        }
    series = [s for s in (ir.get("series") or []) if isinstance(s, dict)]
    points = len(ir.get("categories") or [])
    negative = False
    for s in series:
        for raw in s.get("values") or []:
            try:
                if float(raw) < 0:
                    negative = True
            except (TypeError, ValueError):
                continue
    if points < 1:
        points = max((len(s.get("values") or []) for s in series), default=0)
    return {
        "kind": "category",
        "points": points,
        "series": len(series),
        "negative": negative,
    }


def chart_type_change_warning(chart: dict[str, Any], target: str) -> str:
    """Empty string when the new type can show the same numbers."""
    src = str(chart.get("type") or "").strip()
    want = (target or "").strip()
    if not want or want == src or want not in CHART_TYPES:
        return ""
    shape = _shape(chart)
    if shape["kind"] == "unknown":
        return ""
    if shape["kind"] == "kpi" and want != "kpi":
        if want == "donut":
            return (
                "Сейчас это одно число (KPI). Кольцо будет из одной доли, "
                "без сравнения с другими."
            )
        return (
            "Сейчас это одно число (KPI). Другой тип оставит одну точку — "
            "график будет пустым."
        )
    if want == "kpi" and (shape["points"] > 1 or shape["series"] > 1):
        return (
            "В графике несколько значений. KPI оставит только одно число, "
            "остальное пропадёт."
        )
    if want in {"line", "area"} and shape["points"] < 2:
        return (
            "Для линии или области нужны хотя бы две точки. "
            "Сейчас точка одна — график будет пустым."
        )
    if want == "scatter" and shape["points"] < 2:
        return (
            "Для точечного графика нужны хотя бы две точки. "
            "Сейчас их меньше — на поле останется одна точка."
        )
    if want == "scatter" and shape["kind"] != "scatter":
        return (
            "Подписи категорий пропадут. По оси X встанут номера 0, 1, 2, "
            "а не исходные подписи."
        )
    if shape["kind"] == "scatter" and want not in {"scatter", "kpi"}:
        return (
            "Настоящая ось X пропадёт, останутся только значения Y. "
            "Если X был величиной, график будет врать."
        )
    if want == "donut" and shape["negative"]:
        return (
            "В данных есть отрицательные числа. Кольцо их не покажет, "
            "картинка будет кривой."
        )
    if want == "donut" and shape["series"] > 1:
        return (
            "Несколько рядов в кольцо схлопнутся в один. "
            "Сравнение между рядами пропадёт."
        )
    if want == "donut" and shape["points"] < 2:
        return "Для кольца нужна хотя бы пара долей. Сейчас значение одно."
    return ""


def _rounded(nums: list[float]) -> tuple[float, ...]:
    return tuple(sorted(round(n, 6) for n in nums))


def _chart_numbers(html: str) -> tuple[float, ...]:
    """Multiset of data values. Scatter keeps both x and y."""
    pts = _SCATTER_POINT.findall(html or "")
    if pts:
        vals: list[float] = []
        for x, y in pts:
            vals.append(float(x))
            vals.append(float(y))
        return _rounded(vals)
    vals = []
    for match in re.finditer(r"data\s*:\s*\[([^\]]*)\]", html or "", flags=re.I):
        raw = match.group(1)
        if re.search(r"\bx\s*:", raw):
            continue
        for num in re.findall(r"-?\d+(?:\.\d+)?", raw):
            vals.append(float(num))
    if vals:
        return _rounded(vals)
    value = re.search(
        r"""class\s*=\s*['"]value['"][^>]*>([^<]+)""",
        html or "",
        flags=re.I,
    )
    if value:
        text = value.group(1).replace(" ", "").replace(",", ".")
        vals = [float(num) for num in re.findall(r"-?\d+(?:\.\d+)?", text)]
    return _rounded(vals)


def chart_number_change_warning(
    before_html: str,
    after_html: str,
    *,
    chart_type: str = "",
) -> str:
    """Empty when a style rewrite kept the same numbers."""
    del chart_type  # reserved so callers can pass the stored type
    before = _chart_numbers(before_html)
    after = _chart_numbers(after_html)
    if not before or before == after:
        return ""
    return (
        "Модель изменила числа графика. В отчёт попадут другие значения, "
        "не из исходных данных."
    )
