"""Task 4 tests: LLM reliability, chat summaries, source clipping, routing, and inline chat charts."""

from __future__ import annotations

import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from case3.chat_act import resolve_act
from case3.chat_summary import is_clean_chat_summary
from case3.chat_turn import _clip_source, try_chat_answer
from case3.dashboard_remote import might_ask_dashboard
from case3.llm_client import LLMClient, LLMConfig, LLMError
from case3.turn_route import resolve_turn


def test_try_chat_answer_uses_complete_when_on_delta_is_none() -> None:
    class _DualClient:
        def __init__(self) -> None:
            self.used_complete = False
            self.used_stream = False

        def complete(self, **_kwargs) -> str:
            self.used_complete = True
            return "Выручка по данным составила 100."

        def stream(self, **_kwargs):
            self.used_stream = True
            if False:
                yield ""

    client = _DualClient()
    ans = try_chat_answer("Москва | 100", "сколько выручка", client=client)
    assert client.used_complete is True
    assert client.used_stream is False
    assert "100" in ans


def test_llm_stream_strips_think_and_raises_on_empty_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = LLMConfig(
        base_url="http://localhost:9999/v1",
        api_key="test-key",
        model="qwen",
        timeout_s=5.0,
        max_retries=0,
    )
    client = LLMClient(cfg)

    class _Resp:
        def __init__(self, lines: list[bytes]) -> None:
            self._lines = lines

        def __iter__(self):
            return iter(self._lines)

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    chunks = [
        b'data: {"choices":[{"delta":{"content":"<think>hidden thought</think>"}}]}\n',
        b'data: {"choices":[{"delta":{"content":"Real answer."},"finish_reason":"stop"}]}\n',
        b"data: [DONE]\n",
    ]
    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_kw: _Resp(chunks))
    out = "".join(client.stream(system="s", user_text="u"))
    assert "hidden thought" not in out
    assert out == "Real answer."

    empty_chunks = [
        b'data: {"choices":[{"delta":{"reasoning_content":"only thinking"},"finish_reason":"length"}]}\n',
        b"data: [DONE]\n",
    ]
    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_kw: _Resp(empty_chunks))
    with pytest.raises(LLMError):
        "".join(client.stream(system="s", user_text="u"))


def test_llm_complete_retries_timeout_once(monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = LLMConfig(
        base_url="http://localhost:9999/v1",
        api_key="test-key",
        model="qwen",
        timeout_s=5.0,
        max_retries=1,
    )
    client = LLMClient(cfg)
    client._sleep = lambda _s: None
    attempts = 0

    def _fake_urlopen(_req, _timeout, _cancel):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("timed out")
        body = json.dumps({"choices": [{"message": {"content": "OK"}, "finish_reason": "stop"}]}).encode()

        class _CM:
            def read(self):
                return body

            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False

        return _CM()

    monkeypatch.setattr("case3.llm_client._urlopen_until_cancel", _fake_urlopen)
    assert client.complete(system="s", user_text="u") == "OK"
    assert attempts == 2


def test_is_clean_chat_summary_allows_bilingual_technical_summary() -> None:
    assert is_clean_chat_summary("Отчёт Stimulsoft Dashboard (PDF/DOCX): Q3 KPI, ARR и EBITDA по 6 регионам.") is True
    assert is_clean_chat_summary("The user wants me to write a summary. Based on the outline...") is False
    assert is_clean_chat_summary('We need to parse the message: "Сравни округа по выполнению плана" and build a reply.') is False


def test_wrong_row_allows_other_column_on_same_row_and_aggregates() -> None:
    from case3.dashboard_source import derivative_block
    from case3.fact_ground import wrong_row_tokens

    table = (
        "| Округ | Инспекция | Факт | План | Выполнение | Отклонение |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        "| Минская обл. | ИМНС Борисов | 105 865,2 | 100 000,0 | 105,9% | 5 865,2 |\n"
        "| Минская обл. | ИМНС Солигорск | 84 120,0 | 88 000,0 | 95,6% | -3 880,0 |\n"
        "| Гомельская обл. | ИМНС Жлобин | 94 073,0 | 92 000,0 | 102,3% | 2 073,0 |\n"
        "| Гомельская обл. | ИМНС Мозырь | 71 400,0 | 75 000,0 | 95,2% | -3 600,0 |\n"
    )
    src = f"{table}\n## Производные\n\n{derivative_block(table)}\n"
    prose = (
        "ИМНС Жлобин перевыполняет план: 102,3%. "
        "Чистый плюс по Минской обл. +1 985,2 складывается из Борисова и Солигорска."
    )
    assert wrong_row_tokens(prose, src, "") == []
    assert wrong_row_tokens("ИМНС Борисов показал 95,2%.", src, "") == ["95,2%"]


def test_llm_content_rejects_raw_reasoning_without_content() -> None:
    from case3.llm_client import _content

    with pytest.raises(LLMError):
        _content({
            "choices": [
                {
                    "message": {
                        "content": "",
                        "reasoning": "We need to parse the user's message carefully.",
                    },
                    "finish_reason": "length",
                }
            ]
        })


def test_clip_source_single_giant_table_no_duplication() -> None:
    rows = ["| Регион | Факт | План |", "| --- | --- | --- |"]
    for i in range(3000):
        rows.append(f"| Регион_{i:04d} | {1000 + i} | {900 + i} |")
    source = "\n".join(rows)
    assert len(source) > 80_000
    clipped = _clip_source(source, limit=5000, focus="Регион_1200")
    assert len(clipped) <= 5000
    assert "Регион_1200" in clipped
    assert clipped.count("| Регион | Факт | План |") == 1


def test_chat_act_does_not_hijack_new_report_with_charts() -> None:
    act = resolve_act(
        "Сделай новый отчёт за март и добавь графики по регионам",
        has_report=True,
    )
    assert act.kind == "build"
    assert act.build == "report"


def test_might_ask_dashboard_ignores_generic_analyze_data() -> None:
    assert might_ask_dashboard("проанализируй эти данные") is False
    assert might_ask_dashboard("хочу данные по февраль 25") is True
    assert might_ask_dashboard("покажи фильтры дашборда") is True


def test_turn_route_routes_standalone_chart_to_chat_and_report_chart_to_report() -> None:
    from case3.turn_route import wants_chat_chart

    assert resolve_turn("Построй график по областям", None) == "chat"
    assert resolve_turn("Нарисуй диаграмму продаж", None) == "chat"
    assert resolve_turn("Построй график в чате", "report") == "chat"
    assert resolve_turn("Построй график по областям", "report") == "chat"
    assert resolve_turn("Сделай отчёт и график по областям", None) == "report"
    assert wants_chat_chart("Построй график по областям") is True
    assert wants_chat_chart("можешь построить график по этим данным") is True
    assert wants_chat_chart("без графиков, просто расскажи") is False
    assert resolve_turn("Построй схему по этим данным", None) == "chat"
    assert resolve_turn("Сделай схему", None) == "diagram"


def test_chat_pipeline_renders_inline_chart_when_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from case3.pipeline import run_pipeline

    monkeypatch.setenv("VISION_API_BASE_URL", "http://localhost:9999/v1")
    monkeypatch.setenv("VISION_API_KEY", "test-key")

    src = tmp_path / "src.md"
    src.write_text("| Область | Сумма |\n| --- | --- |\n| Минская | 100 |\n| Гомельская | 40 |\n", encoding="utf-8")

    class _FakeLLM:
        last_finish_reason = "stop"

        def __init__(self, *_a, **_kw) -> None:
            pass

        def complete(self, *, system: str = "", user_text: str = "", **_kw) -> str:
            if "charts" in system.lower() or "chart.js" in system.lower() or "json" in system.lower():
                return json.dumps(
                    {
                        "charts": [
                            {
                                "id": "cht_01",
                                "type": "bar",
                                "caption": "Сумма по областям",
                                "html": "<canvas id='c'></canvas><script>new Chart(c,{type:'bar',data:{labels:['Минская','Гомельская'],datasets:[{data:[100,40]}]}});window.__CHART_READY=true;</script>",
                            }
                        ]
                    },
                    ensure_ascii=False,
                )
            return "Минская собрала 100, Гомельская 40."

        def stream(self, **kwargs):
            yield self.complete(**kwargs)

    def _fake_render(items, **_kwargs):
        out = {}
        for cid, _chart, dest, _cdir in items:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"\x89PNG\r\n\x1a\n")
            out[cid] = {"ok": True, "path": str(dest), "kind": "chart"}
        return out

    monkeypatch.setattr("case3.chat_turn.LLMClient", _FakeLLM)
    monkeypatch.setattr("case3.charts.render_charts_batch", _fake_render)

    out_dir = run_pipeline(
        src,
        project_root=tmp_path,
        formats={"none"},
        dry_run=False,
        intent="Построй график по областям",
        max_charts=2,
        output_mode="chat",
    )
    meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["output_mode"] == "chat"
    assert (out_dir / "figures" / "cht_01.png").is_file()
    assert meta.get("charts_ok", 0) == 1


def test_earlier_source_is_the_previous_document(tmp_path: Path) -> None:
    from case3.chat_memory import earlier_source

    runs = tmp_path / "runs"
    doc = runs / "uploads" / "screen.md"
    doc.parent.mkdir(parents=True)
    doc.write_text("| А | Б |\n| --- | --- |\n| Минск | 10 |\n", encoding="utf-8")
    out = runs / "out" / "source_20261123T120000Z"
    out.mkdir(parents=True)
    (out / "meta.json").write_text(
        json.dumps({"source": str(doc)}),
        encoding="utf-8",
    )
    assert "Минск" in earlier_source(tmp_path, "source_20261123T120000Z")
