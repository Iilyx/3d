"""Truncated JSON fences must still yield complete charts."""

from __future__ import annotations

from case3.parse_output import parse_model_output, salvage_json_object


def test_real_upload_085455_style_recovers() -> None:
    """Regression: truncated mid-cht_03 JSON, no LaTeX → still build doc."""
    # Minimal shape of debug/upload-20261019T115559 source_20261019T085455Z
    raw = (
        "```json\n{\n  \"figures\": [],\n  \"charts\": [\n"
        "    {\n      \"id\": \"cht_01\",\n      \"type\": \"line\",\n"
        "      \"caption\": \"Население\",\n"
        "      \"width\": \"0.9\\\\textwidth\",\n"
        "      \"html\": \"<canvas id=\\\"c1\\\" width=\\\"1100\\\" height=\\\"560\\\">"
        "</canvas><script>new Chart(document.getElementById('c1'),"
        "{type:'line',data:{labels:['2019'],datasets:[{data:[9470],"
        "borderColor:'#D62828'}]},options:{animation:false}});"
        "window.__CASE3_CHART_READY=true;</script>\"\n    },\n"
        "    {\n      \"id\": \"cht_02\",\n      \"type\": \"bar\",\n"
        "      \"caption\": \"Рождения\",\n"
        "      \"html\": \"<canvas id=\\\"c2\\\" width=\\\"1100\\\" height=\\\"560\\\">"
        "</canvas><script>new Chart(document.getElementById('c2'),"
        "{type:'bar',data:{labels:['2019'],datasets:[{data:[1],"
        "backgroundColor:'#FCBF49'}]},options:{animation:false}});"
        "window.__CASE3_CHART_READY=true;</script>\"\n    },\n"
        "    {\n      \"id\": \"cht_03\",\n      \"type\": \"donut\",\n"
        "      \"caption\": \"Broken\",\n"
        "      \"html\": \"<canvas id=\\\"c3\\\"\n"
    )
    tex, _figs, charts, _dias, _drops = parse_model_output(raw, max_images=0, max_charts=3)
    assert {c["id"] for c in charts} == {"cht_01", "cht_02"}
    assert "%CASE3_CHART:cht_01%" in tex
    assert r"\documentclass" in tex


def test_salvage_keeps_complete_chart_drops_truncated() -> None:
    raw = r'''```json
{
  "figures": [],
  "charts": [
    {
      "id": "cht_01",
      "type": "line",
      "caption": "Население",
      "width": "0.9\\textwidth",
      "html": "<canvas id=\"c1\" width=\"1100\" height=\"560\"></canvas><script>new Chart(document.getElementById('c1'),{type:'line',data:{labels:['2019'],datasets:[{data:[1],borderColor:'#D62828'}]},options:{animation:false}});window.__CASE3_CHART_READY=true;</script>"
    },
    {
      "id": "cht_02",
      "type": "bar",
      "caption": "Broken",
      "html": "<canvas id=\"c2\"
'''
    data = salvage_json_object(raw)
    assert data is not None
    assert len(data["charts"]) == 1
    assert data["charts"][0]["id"] == "cht_01"


def test_parse_json_only_builds_tex_with_slots() -> None:
    raw = r'''```json
{
  "figures": [],
  "charts": [
    {
      "id": "cht_01",
      "type": "line",
      "caption": "Население",
      "width": "0.9\\textwidth",
      "html": "<canvas id=\"c1\" width=\"1100\" height=\"560\"></canvas><script>new Chart(document.getElementById('c1'),{type:'line',data:{labels:['2019'],datasets:[{data:[9470],borderColor:'#D62828'}]},options:{animation:false}});window.__CASE3_CHART_READY=true;</script>"
    }
  ]
}
```
'''
    tex, figures, charts, _dias, _drops = parse_model_output(raw, max_images=0, max_charts=3)
    assert figures == []
    assert len(charts) == 1
    assert charts[0]["id"] == "cht_01"
    assert r"\documentclass" in tex
    assert "%CASE3_CHART:cht_01%" in tex


def test_parse_prefers_continuation_json_over_truncated_first() -> None:
    raw = (
        "```json\n{\n  \"figures\": [],\n  \"charts\": [\n    {\n"
        '      "id": "cht_01",\n      "type": "line",\n'
        '      "caption": "x",\n      "html": "<canvas id=\\"c1\\"\n'
        "```\n\n"
        "```json\n"
        "{\n  \"figures\": [],\n  \"charts\": [\n    {\n"
        '      "id": "cht_01",\n      "type": "line",\n'
        '      "caption": "ok",\n      "width": "0.9\\\\textwidth",\n'
        '      "html": "<canvas id=\\"c1\\" width=\\"1100\\" height=\\"560\\">'
        "</canvas><script>new Chart(document.getElementById('c1'),"
        "{type:'line',data:{labels:['a'],datasets:[{data:[1],"
        "borderColor:'#D62828'}]},options:{animation:false}});"
        "window.__CASE3_CHART_READY=true;</script>\"\n"
        "    }\n  ]\n}\n"
        "```\n"
    )
    tex, _figs, charts, _dias, _drops = parse_model_output(raw, max_images=0, max_charts=3)
    assert len(charts) == 1
    assert "%CASE3_CHART:cht_01%" in tex
