"""LLM often emits scales:{y:{…},title:{…}} — Chart.js throws; READY never fires."""

from case3.chart_html import sanitize_chart_html


def _compact(s: str) -> str:
    return "".join(s.split())


def test_orphan_y_scale_title_nested() -> None:
    raw = (
        "<canvas id='c1'></canvas><script>"
        "new Chart(document.getElementById('c1'),{type:'bar',data:{labels:['A','B'],"
        "datasets:[{data:[1,2],backgroundColor:['#004D47','#0077BB']}]},"
        "options:{plugins:{legend:{display:false}},"
        "scales:{y:{beginAtZero:true},title:{display:true,text:'Минуты'}},"
        "animation:false}});"
        "</script>"
    )
    compact = _compact(sanitize_chart_html(raw))
    assert "y:{beginAtZero:true,title:{display:true,text:'Минуты'}}" in compact
    assert "scales:{y:{beginAtZero:true},title:" not in compact


def test_orphan_x_scale_title_nested() -> None:
    raw = (
        "<canvas id='c1'></canvas><script>"
        "new Chart(document.getElementById('c1'),{type:'bar',data:{labels:['A'],"
        "datasets:[{data:[1]}]},"
        "options:{indexAxis:'y',scales:{x:{beginAtZero:true},title:{display:true,text:'X'}},"
        "animation:false}});"
        "</script>"
    )
    compact = _compact(sanitize_chart_html(raw))
    assert "x:{beginAtZero:true,title:{display:true,text:'X'}}" in compact


def test_chart_timeout_floor_at_least_45() -> None:
    import os
    from case3.charts import chart_timeout_s

    old = os.environ.get("CASE3_CHART_TIMEOUT_S")
    try:
        os.environ["CASE3_CHART_TIMEOUT_S"] = "15"
        assert chart_timeout_s() >= 45.0
    finally:
        if old is None:
            os.environ.pop("CASE3_CHART_TIMEOUT_S", None)
        else:
            os.environ["CASE3_CHART_TIMEOUT_S"] = old


def test_missing_closing_paren_and_duplicate_script_ready_repaired() -> None:
    raw = (
        "<canvas id='c1' width='1100' height='560'></canvas>"
        "<script>new Chart(document.getElementById('c1'),"
        "{type:'bar',data:{labels:['А','Б'],datasets:[{label:'Факт',data:[10,20]}]},"
        "options:{responsive:false}};</script>"
        "window.__CASE3_CHART_READY=true;</script>"
    )
    cleaned = sanitize_chart_html(raw)
    # Must close `new Chart(...)` before `;`, and strip stray outer READY / </script>
    assert "});" in cleaned or ")\n;" in cleaned or "),window.__CASE3_CHART_READY" not in cleaned
    assert cleaned.count("<script") == 1
    assert cleaned.count("</script>") == 1
    assert "options:{responsive:false}});" in _compact(cleaned)


def test_hbar_y_ticks_with_grid_before_ticks_avoids_duplicate_ticks_key() -> None:
    from case3.chart_harden import harden_chart_html

    raw = (
        '<canvas id="c" width="800" height="400"></canvas>'
        "<script>new Chart(document.getElementById('c'), {"
        "type:'bar',"
        "data:{labels:['А','Б','В'],datasets:[{label:'Факт',data:[10,20,30]}]},"
        "options:{indexAxis:'y',scales:{x:{grid:{display:true}},y:{grid:{display:false},ticks:{font:{size:11}}}}}"
        "});</script>"
    )
    out = harden_chart_html(raw, "horizontal_bar")
    assert out.count("ticks:") == 1
    assert "autoSkip:false" in out
    assert "font:{size:11}" in out


def test_scales_title_both_axes_relocated_to_plugins_title_in_harden_and_sanitize() -> None:
    from case3.chart_harden import harden_chart_html

    raw = (
        '<canvas id="c" width="1100" height="560"></canvas><script>'
        "new Chart(document.getElementById('c'), {type: 'bar', "
        "data: {labels: ['г. Минск', 'Минская область'], datasets: [{label: 'Факт, тыс. руб.', data: [184520, 94073.2]}]}, "
        "options: {responsive: false, scales: {x: {ticks: {fontSize: 16}}, y: {ticks: {fontSize: 16}}, "
        "title: {display: true, text: 'Факт поступлений по областям', fontSize: 18}}, "
        "plugins:{tooltip:{enabled:true},legend: {display: false}}}});"
        "</script>"
    )
    for fn in (lambda h: harden_chart_html(h, "bar"), sanitize_chart_html):
        out = fn(raw)
        # No `title:` left as a top-level child of `scales: {...}`
        scales_idx = out.index("scales:")
        plugins_idx = out.index("plugins:")
        scales_part = out[scales_idx:plugins_idx]
        assert "title:" not in scales_part
        assert "Факт поступлений по областям" in out


def test_scales_misplaced_plugins_legend_tooltip_animation_stripped() -> None:
    from case3.chart_harden import harden_chart_html

    raw = (
        '<canvas id="c" width="1100" height="560"></canvas><script>'
        "new Chart(document.getElementById('c'), {type: 'line', "
        "data: {labels: ['А', 'Б'], datasets: [{label: 'Факт', data: [10, 20]}]}, "
        "options: {responsive: false, scales: {x: {grid: {display: false}}, y: {beginAtZero: true}, "
        "plugins: {legend: {display: true}}, legend: {display: false}, tooltip: {enabled: true}, animation: false}}});"
        "</script>"
    )
    hardened = harden_chart_html(raw, "line")
    sanitized = sanitize_chart_html(hardened)
    for out in (hardened, sanitized):
        m_start = out.index("scales:")
        # Ensure plugins/legend/tooltip/animation are not inside scales:{...}
        brace_start = out.index("{", m_start)
        depth = 0
        end = brace_start
        for i in range(brace_start, len(out)):
            if out[i] == "{":
                depth += 1
            elif out[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        scales_block = out[brace_start:end]
        assert "plugins:" not in scales_block
        assert "legend:" not in scales_block
        assert "tooltip:" not in scales_block
        assert "animation:" not in scales_block
        assert "beginAtZero:true" in _compact(scales_block)


def test_scales_with_js_comments_and_quoted_keys_repaired() -> None:
    from case3.chart_harden import repair_misplaced_scales_keys

    commented = (
        '<canvas id="c"></canvas><script>'
        "new Chart(document.getElementById('c'), {type: 'bar', "
        "data: {labels: ['A', 'B'], datasets: [{label: 'V', data: [10, 20]}]}, "
        "options: {responsive: false, scales: {\n"
        "  // it's the x axis\n"
        "  x: {}, y: {},\n"
        "  // chart title shouldn't stay in scales\n"
        "  title: {display: true, text: 'Title'}\n"
        "}}});</script>"
    )
    out1 = repair_misplaced_scales_keys(commented)
    assert "plugins:{title:{display:true,text:'Title'}}" in _compact(out1)
    scales_start = out1.index("scales:")
    options_tail = out1[scales_start:]
    assert "text: 'Title'" not in options_tail
    out1_san = sanitize_chart_html(commented)
    assert "}}});}}});" not in _compact(out1_san)
    assert "plugins:{title:{display:true,text:'Title'}}" in _compact(out1_san)

    quoted = (
        '<canvas id="c"></canvas><script>'
        'new Chart(document.getElementById("c"), {"type": "bar", '
        '"data": {"labels": ["A", "B"], "datasets": [{"label": "V", "data": [10, 20]}]}, '
        '"options": {"responsive": false, "plugins": {"legend": {"display": false}}, '
        '"scales": {"x": {}, "y": {}, "title": {"display": true, "text": "Quoted"}}}});'
        "</script>"
    )
    out2 = repair_misplaced_scales_keys(quoted)
    assert '"title":{"display":true,"text":"Quoted"}' not in _compact(out2[out2.index('"scales"'):])
    assert 'title:{"display":true,"text":"Quoted"}' in _compact(out2)


def test_scales_misplaced_subtitle_and_axis_subkeys_repaired() -> None:
    from case3.chart_harden import repair_misplaced_scales_keys

    raw = (
        '<canvas id="c"></canvas><script>'
        "new Chart(document.getElementById('c'), {type: 'bar', "
        "data: {labels: ['A', 'B'], datasets: [{label: 'V', data: [10, 20]}]}, "
        "options: {responsive: false, scales: {x: {}, y: {}, "
        "subtitle: {display: true, text: 'Sub'}, ticks: {fontSize: 16}, grid: {display: false}, border: {display: false}}}});"
        "</script>"
    )
    out = repair_misplaced_scales_keys(raw)
    compact = _compact(out)
    assert "plugins:{subtitle:{display:true,text:'Sub'}}" in compact
    scales_block = compact[compact.index("scales:") :]
    assert "subtitle:" not in scales_block
    assert "ticks:" not in scales_block
    assert "grid:" not in scales_block
    assert "border:" not in scales_block
