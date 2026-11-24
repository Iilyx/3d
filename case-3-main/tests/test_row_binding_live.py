"""Chat, slides, and the Word source drop a swapped sum and a share used as a sum."""

from __future__ import annotations

from case3.chat_turn import try_chat_answer
from case3.dashboard_source import derivative_block
from case3.fact_ground import bind_deck_numbers, ground_generated
from case3.tex_preamble import tex_for_pandoc

_TABLE = (
    "| Область | Сумма |\n"
    "| --- | --- |\n"
    "| Минская | 105 865,2 |\n"
    "| Гомельская | 94 073,0 |\n"
)
_SOURCE = _TABLE + "\n## Производные\n" + derivative_block(_TABLE)


class _Seq:
    def __init__(self, texts: list[str]) -> None:
        self.texts = list(texts)
        self.calls = 0

    def stream(self, **_kwargs):
        self.calls += 1
        yield self.texts.pop(0)


def test_word_source_keeps_only_the_matching_sentence() -> None:
    tex = r"""
\documentclass{article}
\begin{document}
Минская 94 073,0; Гомельская 105 865,2.
Минская собрала 52,9.
Минская 105 865,2 и Гомельская 94 073,0.
Доля Минской 52,9%.
\end{document}
"""
    grounded, _charts, _figures, _diagrams, _dropped = ground_generated(
        tex, [], [], [], source=_SOURCE, intent="отчёт"
    )
    word = tex_for_pandoc(grounded)
    assert "94 073,0; Гомельская" not in word
    assert "собрала" not in word
    assert "Минская 105 865,2 и Гомельская 94 073,0" in word
    assert "Доля Минской 52,9%" in word


def test_chat_refuses_a_swapped_pair_and_keeps_the_true_one() -> None:
    swapped = _Seq(
        [
            "Минская 94 073,0 и Гомельская 105 865,2.",
            "Минская 94 073,0; Гомельская 105 865,2.",
        ]
    )
    refused = try_chat_answer(_SOURCE, "сравни области", client=swapped)
    assert swapped.calls == 2
    assert "105 865,2" not in refused
    assert "другой строки" in refused

    kept = _Seq(["Минская 105 865,2 и Гомельская 94 073,0."])
    answer = try_chat_answer(_SOURCE, "сравни области", client=kept)
    assert kept.calls == 1
    assert answer == "Минская 105 865,2 и Гомельская 94 073,0."


def test_chat_refuses_a_share_written_as_the_sum() -> None:
    client = _Seq(["Минская собрала 52,9.", "Минская собрала 52,9."])
    text = try_chat_answer(_SOURCE, "сколько собрала Минская", client=client)
    assert client.calls == 2
    assert "52,9" not in text
    assert "другой строки" in text

    share = _Seq(["Доля Минской 52,9%."])
    spoken = try_chat_answer(_SOURCE, "какая доля Минской", client=share)
    assert share.calls == 1
    assert spoken == "Доля Минской 52,9%."


def test_a_slide_drops_the_swapped_sum_and_the_fake_share() -> None:
    deck = bind_deck_numbers(
        {
            "slides": [
                {
                    "id": "s1",
                    "layout": "bullets",
                    "title": "Области",
                    "bullets": [
                        "Минская 94 073,0; Гомельская 105 865,2.",
                        "Минская собрала 52,9.",
                        "Минская 105 865,2 и Гомельская 94 073,0.",
                        "Доля Минской 52,9%.",
                    ],
                }
            ]
        },
        source=_SOURCE,
        intent="собери слайды",
    )
    bullets = deck["slides"][0]["bullets"]
    assert bullets == [
        "Минская 105 865,2 и Гомельская 94 073,0.",
        "Доля Минской 52,9%.",
    ]
