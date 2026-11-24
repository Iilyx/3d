"""The prompt the chat model actually receives.

format_thread can be perfect and still never arrive. These tests walk the
same assembly as /api/run: disk chain, prior block, UI rules stripped,
then try_chat_answer.
"""

import json
from pathlib import Path

from case3.chat_turn import try_chat_answer
from case3.input_validation import user_text_before_ui
from case3.intent_compose import build_intent_from_ui
from case3.prior_turn import insert_prior_turn, prior_block_for_form


class _Seq:
    def __init__(self, texts: list[str]) -> None:
        self.texts = list(texts)
        self.seen: list[str] = []

    def stream(self, **kwargs):
        self.seen.append(kwargs.get("user_text") or "")
        yield self.texts.pop(0)


def _write_run(root: Path, run_id: str, meta: dict) -> None:
    out = root / "runs" / "out" / run_id
    out.mkdir(parents=True)
    (out / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False),
        encoding="utf-8",
    )


def _model_text(question: str, block: str) -> str:
    """Intent after UI rules are removed, which is what the pipeline sends."""
    full = build_intent_from_ui(
        chat=question,
        chart_types=[],
        max_charts=0,
        max_images=0,
        forbid_charts=True,
        forbid_images=True,
        output_mode="chat",
        max_diagrams=0,
    )
    return user_text_before_ui(insert_prior_turn(full, block))


def test_disk_chain_reaches_the_model_with_paragraphs_and_recall(tmp_path: Path):
    old = "source_20261119T100000Z"
    new = "source_20261119T110000Z"
    source = tmp_path / "runs" / "uploads" / "source_20261119T110000Z" / "source.txt"
    source.parent.mkdir(parents=True)
    source.write_text("Касса была 20.", encoding="utf-8")
    _write_run(
        tmp_path,
        old,
        {
            "run_id": old,
            "chat_prompt": "вопрос про склад",
            "chat_summary": "СКЛАДПАМЯТЬ было тихо.",
            "output_mode": "chat",
        },
    )
    _write_run(
        tmp_path,
        new,
        {
            "run_id": new,
            "prior_run_id": old,
            "chat_prompt": "что с кассой",
            "chat_summary": "Касса держится.\n\nХВОСТМАРКЕР в конце.",
            "output_mode": "chat",
            "source": str(source),
            "dialogue": [
                {"user": "подвинь заголовок", "assistant": "Переименовал введение."}
            ],
        },
    )
    question = "вспомни что ты говорил про склад"
    block = prior_block_for_form(new, root=tmp_path, user_text=question)
    client = _Seq(["Касса в документе 20. Склад помню отдельно."])
    try_chat_answer(
        "Касса была 20.",
        _model_text(question, block),
        client=client,
    )
    prompt = client.seen[0]
    assert "Касса держится.\n\nХВОСТМАРКЕР в конце." in prompt
    assert "СКЛАДПАМЯТЬ было тихо." in prompt
    assert "подвинь заголовок" in prompt
    assert "Один прошлый ход" in prompt
    assert "не Source" in prompt
    assert "Требования UI" not in prompt
    assert "Chart.js" not in prompt
    recall_at = prompt.index("Один прошлый ход")
    assert prompt.index("ТЕКСТ:") < prompt.index("ХВОСТМАРКЕР") < recall_at
    assert "СКЛАДПАМЯТЬ было тихо." in prompt[recall_at:]


def test_overflow_keeps_recall_after_the_latest_answer():
    from case3.chat_turn import _MEMORY_CAP

    filler = "ДРЕВНИЙ " + ("н" * (_MEMORY_CAP + 2000))
    block = (
        "Разговор этого чата (не Source).\n"
        "Ход 1. Запрос: про склад\n"
        f"Ответ: {filler}\n"
        "Ход 2. Запрос: сейчас\n"
        "Ответ: ХВОСТМАРКЕР свежий.\n\n"
        "Один прошлый ход (не Source).\n"
        "Ответ: СКЛАДПАМЯТЬ коротко."
    )
    client = _Seq(["Касса в документе 20. Новых цифр не добавляю."])
    try_chat_answer("Касса была 20.", _model_text("Что с кассой?", block), client=client)
    prompt = client.seen[0]
    assert "ХВОСТМАРКЕР свежий." in prompt
    assert "СКЛАДПАМЯТЬ коротко." in prompt
    assert "ДРЕВНИЙ" not in prompt
    assert "нннннннннн" not in prompt
    assert prompt.index("ХВОСТМАРКЕР свежий.") < prompt.index("СКЛАДПАМЯТЬ коротко.")
    assert "Требования UI" not in prompt


def test_retry_still_sees_the_tail():
    block = (
        "Разговор этого чата (не Source).\n"
        "Ход 1. Запрос: сейчас\n"
        "Ответ: Касса держится.\n\nХВОСТМАРКЕР в конце."
    )
    client = _Seq(
        [
            "Касса была 99 по моей оценке.",
            "Касса в документе 20. Новых цифр не добавляю.",
        ]
    )
    text = try_chat_answer(
        "Касса была 20.",
        _model_text("Что с кассой?", block),
        client=client,
    )
    assert client.seen[0].count("ХВОСТМАРКЕР") == 1
    assert "ХВОСТМАРКЕР" in client.seen[1]
    assert "Повтор:" in client.seen[1]
    assert "99" not in text
    assert "20" in text
