"""Adversarial locks for chat_memory rules (format, recall, chain, edits, dialogue)."""

import json
from pathlib import Path

from case3.chat_memory import (
    _LINE,
    _NOTE,
    _NOTE_SHORT,
    _PREV,
    _TAIL,
    _WINDOW_CAPS,
    append_dialogue,
    chain_limit_payload,
    format_thread,
    load_chain,
    merge_edit,
    recall_block,
)


def _prose(marker: str, head: int, mid: int, tail_marker: str) -> str:
  return (
      f"{marker} start.\n\n"
      + ("н" * head)
      + f"{marker} MID"
      + ("н" * mid)
      + tail_marker
  )


# --- Attack 1: format_thread turn budgets ---


def test_attack_format_last_turn_prose_up_to_2000():
    body = _prose("ХВОСТ", 400, 1700, "ОТРЕЗАТЬХВОСТ")
    text = format_thread([{"chat_prompt": "запрос", "chat_summary": body, "output_mode": "chat"}])
    assert "ХВОСТ start." in text
    assert "ХВОСТ MID" in text
    assert "ОТРЕЗАТЬХВОСТ" not in text


def test_attack_format_previous_turn_capped_near_1600():
    turns = [
        {"chat_prompt": "old", "chat_summary": "archive"},
        {"chat_prompt": "far", "chat_summary": "shrink"},
        {"chat_prompt": "mid", "chat_summary": "also shrink"},
        {
            "chat_prompt": "prev",
            "chat_summary": "PREV" + ("н" * 1400) + "KEEPPREV" + ("н" * 400) + "CUTPREV",
        },
        {"chat_prompt": "now", "chat_summary": "current"},
    ]
    text = format_thread(turns)
    assert "KEEPPREV" in text
    assert "CUTPREV" not in text


def test_attack_format_oldest_full_turn_keeps_prose_near_800():
    from case3.chat_memory import _LINE, _WINDOW

    summary = "ДАЛЕКО" + ("н" * 820) + "TAILDROP"
    turns = [{"chat_prompt": "z", "chat_summary": summary}]
    turns.extend(
        {"chat_prompt": "a", "chat_summary": "a"} for _ in range(_WINDOW - 1)
    )
    text = format_thread(turns)
    assert "ДАЛЕКО" in text
    assert "TAILDROP" not in text
    assert _WINDOW_CAPS == (2000, 1600, 1200, 800)
    assert _LINE == 800


def test_attack_format_dialogue_notes_shrink_behind_the_two_newest():
    long_user = "у" * 200 + "USER300"
    long_agent = "а" * 200 + "AGENT300"
    old_note_user = "СТАРТ" + ("о" * 140) + "ОБРЕЗАНО"
    turns = [
        {
            "chat_prompt": "давно",
            "chat_summary": "one",
            "dialogue": [{"user": old_note_user, "assistant": "ok"}],
        },
        {"chat_prompt": "a", "chat_summary": "a"},
        {
            "chat_prompt": "prev",
            "chat_summary": "b",
            "dialogue": [{"user": "заметка предыдущего", "assistant": "сделано"}],
        },
        {
            "chat_prompt": "now",
            "chat_summary": "last",
            "dialogue": [{"user": long_user, "assistant": long_agent}],
        },
    ]
    text = format_thread(turns)
    assert "USER300" in text
    assert "AGENT300" in text
    assert "заметка предыдущего" in text
    assert "СТАРТ" in text
    assert "ОБРЕЗАНО" not in text
    assert _NOTE == 300
    assert _NOTE_SHORT == 160
    assert _TAIL == 2000
    assert _PREV == 1600


# --- Attack 2: recall ---


def test_attack_recall_lifts_matched_turn_prose_near_2000():
    summary = _prose("RECALL", 400, 1700, "RECALLTAILGONE")
    turns = [
        {"chat_prompt": "про маржу", "chat_summary": "не то"},
        {"chat_prompt": "разбор кассы", "chat_summary": summary},
    ]
    hit = recall_block(turns, "что ты говорил про кассу")
    assert "RECALL start." in hit
    assert "RECALL MID" in hit
    assert "RECALLTAILGONE" not in hit
    assert "не то" not in hit


def test_attack_recall_says_when_nothing_matches():
    turns = [{"chat_prompt": "про долю", "chat_summary": "доля"}]
    miss = recall_block(turns, "как ты отвечал про кассу")
    assert "не видно" in miss


# --- Attack 3: chain > 48 and self-loop ---


def test_attack_chain_stops_at_48_hops(tmp_path: Path):
    root = tmp_path
    prev = ""
    ids = []
    for i in range(55):
        run_id = f"source_20261119T{i:04d}Z"
        ids.append(run_id)
        out = root / "runs" / "out" / run_id
        out.mkdir(parents=True)
        (out / "meta.json").write_text(
            json.dumps(
                {"run_id": run_id, "prior_run_id": prev, "chat_prompt": str(i)},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        prev = run_id
    chain = load_chain(root, ids[-1])
    assert len(chain) == 48
    assert chain[0]["chat_prompt"] == "7"
    assert chain[-1]["chat_prompt"] == "54"


def test_attack_chain_limit_payload_after_48(tmp_path: Path):
    root = tmp_path
    prev = ""
    last = ""
    for i in range(49):
        run_id = f"source_20261119T{i:04d}Z"
        last = run_id
        out = root / "runs" / "out" / run_id
        out.mkdir(parents=True)
        (out / "meta.json").write_text(
            json.dumps({"run_id": run_id, "prior_run_id": prev}, ensure_ascii=False),
            encoding="utf-8",
        )
        prev = run_id
    assert chain_limit_payload(root, last) is not None
    assert chain_limit_payload(root, "") is None


def test_attack_chain_no_loop_when_prior_points_to_self(tmp_path: Path):
    root = tmp_path
    run_id = "source_20261119TselfZ"
    out = root / "runs" / "out" / run_id
    out.mkdir(parents=True)
    (out / "meta.json").write_text(
        json.dumps(
            {"run_id": run_id, "prior_run_id": run_id, "chat_prompt": "solo"},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    chain = load_chain(root, run_id)
    assert len(chain) == 1
    assert chain[0]["chat_prompt"] == "solo"


# --- Attack 4: merge_edit / undo ---


def test_attack_merge_undo_does_not_erase_section():
    found = {"op": "rewrite", "section": "Введение", "pack": "board"}
    after = merge_edit(found, {"op": "undo"})
    assert after["section"] == "Введение"
    assert after["op"] == "undo"
    assert after.get("pack") == "board"


def test_attack_merge_new_section_replaces_old():
    found = {"op": "rewrite", "section": "Введение"}
    after = merge_edit(found, {"op": "rewrite", "section": "Заключение"})
    assert after["section"] == "Заключение"


# --- Attack 5: append_dialogue cap ---


def test_attack_append_dialogue_caps_at_twelve():
    meta: dict = {"dialogue": []}
    for i in range(13):
        append_dialogue(meta, f"user-{i}", f"agent-{i}")
    notes = meta["dialogue"]
    assert len(notes) == 12
    assert notes[0]["user"] == "user-1"
    assert notes[-1]["user"] == "user-12"


def test_attack_append_dialogue_keeps_short_user_text():
    meta: dict = {}
    short = "  короткий  запрос  "
    append_dialogue(meta, short, "ответ")
    assert meta["dialogue"][0]["user"] == "короткий запрос"


# --- Attack 6: nasty edge cases ---


def test_attack_recall_ё_e_equivalent_does_not_cross_topic():
    turns = [
        {"chat_prompt": "ёлка в парке", "chat_summary": "ЁЛКАОТВЕТ"},
        {"chat_prompt": "елка другая", "chat_summary": "ЕЛКАДРУГАЯ"},
    ]
    hit = recall_block(turns, "что ты говорил про ёлку")
    assert "ЁЛКАОТВЕТ" in hit or "ЕЛКА" in hit
    miss = recall_block(turns, "что ты говорил про метро")
    assert "не видно" in miss
    assert "ЁЛКАОТВЕТ" not in miss


def test_attack_format_skips_empty_turn_dicts_but_keeps_valid():
    turns = [
        {},
        {"chat_prompt": "   \n\t  ", "chat_summary": ""},
        {"chat_prompt": "живой", "chat_summary": "ответ"},
    ]
    text = format_thread(turns)
    assert "живой" in text
    assert "Ход 3" in text


def test_attack_recall_whitespace_only_topic_prompts_clarify():
    turns = [{"chat_prompt": "x", "chat_summary": "y"}]
    hint = recall_block(turns, "вспомни про    ")
    assert "про какой" in hint