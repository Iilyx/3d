"""Apply text-only and structural patches to deck IR (no LLM)."""

from __future__ import annotations

import copy
import re
from typing import Any

from case3.slides_ir import (
    SLIDE_LAYOUTS,
    DeckIrError,
    _MAX_BULLETS,
    _MAX_TABLE_COLS,
    _MAX_TABLE_ROWS,
    _norm_ws,
)

_ID_OK = re.compile(r"^[a-z][a-z0-9_]{1,31}$")

_TEXT_KEYS = (
    "title",
    "subtitle",
    "kicker",
    "takeaway",
    "body",
    "caption",
    "term",
    "definition",
)
_KPI_KEYS = ("label", "value", "hint", "delta")


def apply_deck_text_patch(
    deck: dict[str, Any],
    patch: dict[str, Any],
) -> dict[str, Any]:
    """Merge text fields from ``patch`` into a copy of ``deck``.

    Allowed: string fields, bullets (1–5, add or remove), kpis[i] text keys
    (same length), table rows (add/remove within the slide caps). Forbidden:
    layout, media/chart ids, slide add/remove, chapter, style.
    """
    if not isinstance(deck, dict) or not isinstance(patch, dict):
        raise DeckIrError("deck/patch must be objects")
    out = copy.deepcopy(deck)
    slides = out.get("slides")
    if not isinstance(slides, list):
        raise DeckIrError("deck.slides required")
    by_id = {
        str(s.get("id")): s
        for s in slides
        if isinstance(s, dict) and s.get("id")
    }
    patch_slides = patch.get("slides")
    if not isinstance(patch_slides, list):
        raise DeckIrError("patch.slides must be a list")

    for ps in patch_slides:
        if not isinstance(ps, dict):
            raise DeckIrError("patch slide must be object")
        sid = str(ps.get("id") or "")
        if not sid or sid not in by_id:
            raise DeckIrError(f"unknown slide id in patch: {sid!r}")
        target = by_id[sid]
        if "layout" in ps and str(ps.get("layout")) != str(target.get("layout")):
            raise DeckIrError("cannot change layout")
        layout = str(target.get("layout") or "")
        allow_media_change = layout in ("media_hero", "media_split", "title", "closing")

        for forbidden in (
            "chart_id",
            "media_id",
            "chapter",
            "appendix",
            "id",
        ):
            if forbidden == "id":
                continue
            if forbidden == "media_id" and allow_media_change:
                continue
            if forbidden in ps and ps.get(forbidden) != target.get(forbidden):
                raise DeckIrError(f"cannot change {forbidden}")

        if "media_id" in ps and allow_media_change:
            mid = ps.get("media_id")
            if mid is not None:
                if not isinstance(mid, str) or not _ID_OK.match(mid):
                    raise DeckIrError(f"invalid media_id in patch: {mid!r}")
                target["media_id"] = mid

        for key in _TEXT_KEYS:
            if key not in ps:
                continue
            val = ps.get(key)
            if val is None:
                continue
            if not isinstance(val, str):
                raise DeckIrError(f"{key} must be string")
            target[key] = _norm_ws(val)

        if "bullets" in ps:
            _patch_bullets(target, ps["bullets"])
        if "kpis" in ps:
            _patch_kpis(target, ps["kpis"])
        if "cards" in ps:
            _patch_cards(target, ps["cards"])
        if "rows" in ps:
            _patch_rows(target, ps["rows"])

    return out


def _patch_bullets(target: dict[str, Any], bullets: Any) -> None:
    cur = target.get("bullets")
    if cur is not None and not isinstance(cur, list):
        raise DeckIrError("slide has no bullets to patch")
    if not isinstance(bullets, list):
        raise DeckIrError("bullets must be list")
    if len(bullets) < 1:
        raise DeckIrError("bullets cannot be empty")
    if len(bullets) > _MAX_BULLETS:
        raise DeckIrError(f"bullet count exceeds {_MAX_BULLETS}")
    out: list[str] = []
    for b in bullets:
        if not isinstance(b, str):
            raise DeckIrError("bullet must be string")
        out.append(_norm_ws(b))
    target["bullets"] = out


_CARD_KEYS = ("kicker", "title", "body")


def _patch_cards(target: dict[str, Any], cards: Any) -> None:
    cur = target.get("cards")
    if not isinstance(cur, list):
        raise DeckIrError("slide has no cards to patch")
    if not isinstance(cards, list):
        raise DeckIrError("cards must be list")
    if len(cards) != len(cur):
        raise DeckIrError("cannot change cards length")
    for i, nc in enumerate(cards):
        if not isinstance(nc, dict) or not isinstance(cur[i], dict):
            raise DeckIrError("card must be object")
        for key in _CARD_KEYS:
            if key not in nc:
                continue
            val = nc.get(key)
            if val is None:
                continue
            if not isinstance(val, str):
                raise DeckIrError(f"card.{key} must be string")
            cur[i][key] = _norm_ws(val)


def _patch_kpis(target: dict[str, Any], kpis: Any) -> None:
    cur = target.get("kpis")
    if not isinstance(cur, list):
        raise DeckIrError("slide has no kpis to patch")
    if not isinstance(kpis, list):
        raise DeckIrError("kpis must be list")
    if len(kpis) != len(cur):
        raise DeckIrError("cannot change kpis length")
    for i, nk in enumerate(kpis):
        if not isinstance(nk, dict) or not isinstance(cur[i], dict):
            raise DeckIrError("kpi must be object")
        for key in _KPI_KEYS:
            if key not in nk:
                continue
            val = nk.get(key)
            if val is None:
                continue
            if not isinstance(val, str):
                raise DeckIrError(f"kpi.{key} must be string")
            cur[i][key] = _norm_ws(val)
        if "status" in nk:
            # allow only if already present or valid — keep existing if omitted
            st = nk.get("status")
            if isinstance(st, str) and st in ("up", "down", "flat"):
                cur[i]["status"] = st


def _patch_rows(target: dict[str, Any], rows: Any) -> None:
    """Replace table cells. Row and column counts may change inside the slide caps."""
    cur = target.get("rows")
    if not isinstance(cur, list) or not cur:
        raise DeckIrError("slide has no rows to patch")
    if not isinstance(rows, list):
        raise DeckIrError("rows must be list")
    if len(rows) < 2:
        raise DeckIrError("table needs a header and at least one data row")
    if len(rows) > _MAX_TABLE_ROWS:
        raise DeckIrError(f"table row count exceeds {_MAX_TABLE_ROWS}")
    out: list[list[str]] = []
    width = 0
    for i, nrow in enumerate(rows):
        if not isinstance(nrow, list) or not nrow:
            raise DeckIrError("table row must be a non-empty list")
        if i == 0 and len(nrow) > _MAX_TABLE_COLS:
            raise DeckIrError(f"table column count exceeds {_MAX_TABLE_COLS}")
        cells: list[str] = []
        for cell in nrow[:_MAX_TABLE_COLS]:
            if not isinstance(cell, str):
                raise DeckIrError("table cell must be string")
            cells.append(_norm_ws(cell) or "—")
        if i == 0:
            if len(cells) < 2:
                raise DeckIrError("table needs at least 2 columns")
            width = len(cells)
        elif len(cells) < width:
            cells = cells + ["—"] * (width - len(cells))
        elif len(cells) > width:
            cells = cells[:width]
        out.append(cells)
    target["rows"] = out


def _slide_list(deck: dict[str, Any]) -> list[dict[str, Any]]:
    slides = deck.get("slides")
    if not isinstance(slides, list) or not slides:
        raise DeckIrError("deck.slides required")
    for s in slides:
        if not isinstance(s, dict) or not s.get("id"):
            raise DeckIrError("each slide needs id")
    return slides  # type: ignore[return-value]


def _fresh_slide_id(existing: set[str]) -> str:
    for i in range(1, 10_000):
        cand = f"s{i:02d}"
        if cand not in existing and _ID_OK.match(cand):
            return cand
    raise DeckIrError("could not allocate slide id")


def _default_slide_for_layout(
    new_id: str,
    layout: str,
    op_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    slide: dict[str, Any] = {"id": new_id, "layout": layout}
    if layout == "title":
        slide.update({
            "title": "Новый заголовок презентации",
            "subtitle": "Подзаголовок и краткое описание",
            "kicker": "СТРАТЕГИЯ",
            "takeaway": "Цель — Рост показателей",
        })
    elif layout == "section":
        slide.update({
            "title": "Новый раздел",
            "subtitle": "Краткое введение в тему раздела",
            "kicker": "ГЛАВА",
        })
    elif layout == "callout":
        slide.update({
            "title": "Ключевой стратегический тезис",
            "kicker": "ТЕЗИС",
            "term": "ГЛАВНЫЙ ВЫВОД",
            "definition": "Формулировка решения или принципа, определяющего дальнейшие действия.",
            "body": "Пояснение контекста и условий реализации принятого решения.",
        })
    elif layout == "quote":
        slide.update({
            "title": "Фокусная позиция или цитата",
            "kicker": "ПОЗИЦИЯ",
            "definition": "Точная цитата или формулировка ключевого аргумента из источника.",
            "term": "ЭКСПЕРТ ИЛИ ИСТОЧНИК",
        })
    elif layout == "scorecard":
        slide.update({
            "title": "Сводная панель показателей",
            "kicker": "МЕТРИКИ",
            "kpis": [
                {"label": "Выручка", "value": "Показатель", "delta": "динамика", "status": "up"},
                {"label": "Удержание", "value": "Показатель", "delta": "динамика", "status": "up"},
                {"label": "Маржа", "value": "Показатель", "delta": "динамика", "status": "up"},
                {"label": "Касса", "value": "Показатель", "delta": "запас", "status": "up"},
            ],
            "caption": "Данные за последний отчетный период",
        })
    elif layout == "stat_hero":
        slide.update({
            "title": "Ключевой мультипликатор эффективности",
            "kicker": "МАСШТАБ",
            "kpis": [
                {"label": "Рост отдачи ключевого канала", "value": "Эффект", "delta": "к базе"}
            ],
            "bullets": [
                "Фактор ускорения за счет фокуса на ядре",
                "Снижение издержек на единицу продукции",
            ],
        })
    elif layout == "compare":
        slide.update({
            "title": "Сравнение ключевых подходов",
            "kicker": "ВЫБОР МОДЕЛИ",
            "cards": [
                {
                    "kicker": "ВАРИАНТ А · МАСШТАБ",
                    "title": "Целевая архитектура",
                    "body": "Быстрый вывод в промышленный контур, предсказуемая экономика и снижение операционных рисков.",
                },
                {
                    "kicker": "ВАРИАНТ Б · СТАТУС-КВО",
                    "title": "Текущий процесс",
                    "body": "Растянутые циклы согласования, высокая стоимость сопровождения и распыление ресурсов.",
                },
            ],
        })
    elif layout == "card_row":
        slide.update({
            "title": "Приоритетные направления",
            "kicker": "ПРИОРИТЕТЫ",
            "cards": [
                {"kicker": "ТРЕК А", "title": "Ускорение ядра", "body": "Оптимизация ключевых сценариев взаимодействия."},
                {"kicker": "ТРЕК Б", "title": "Автоматизация", "body": "Внедрение типовых шаблонов и контроля качества."},
                {"kicker": "ТРЕК В", "title": "Масштабирование", "body": "Выход в смежные сегменты и каналы привлечения."},
            ],
        })
    elif layout == "table_hero":
        slide.update({
            "title": "Сводная матрица параметров",
            "kicker": "ДАННЫЕ",
            "rows": [
                ["Сегмент", "План", "Факт", "Статус"],
                ["Корпоративный", "План", "Факт", "Выполнен"],
                ["Малый бизнес", "План", "Факт", "Выполнен"],
                ["Партнеры", "План", "Факт", "В работе"],
            ],
            "caption": "Итоги выполнения программы по ключевым каналам",
        })
    elif layout == "timeline":
        slide.update({
            "title": "Дорожная карта реализации",
            "kicker": "ПЛАН РЕАЛИЗАЦИИ",
            "cards": [
                {"kicker": "ЭТАП I", "title": "Аудит и рамка", "body": "Формулировка целевых требований."},
                {"kicker": "ЭТАП II", "title": "Пилотный запуск", "body": "Проверка гипотез на первом сегменте."},
                {"kicker": "ЭТАП III", "title": "Тиражирование", "body": "Масштабирование на всю клиентскую базу."},
                {"kicker": "ЭТАП IV", "title": "Фиксация метрик", "body": "Оценка совокупного эффекта программы."},
            ],
        })
    elif layout == "closing":
        slide.update({
            "title": "Финальные решения и следующие шаги",
            "kicker": "РЕШЕНИЕ",
            "takeaway": "Ключевые договоренности",
            "bullets": [
                "Утвердить план и закрепить ответственных владельцев",
                "Запустить реализацию первого этапа в течение недели",
                "Провести промежуточный статус-чек по итогам периода",
            ],
        })
    elif layout in ("media_hero", "media_split"):
        mid = str((op_body or {}).get("media_id") or "usr_01").strip()
        slide.update({
            "title": str((op_body or {}).get("title") or "Иллюстрация к разделу").strip(),
            "kicker": str((op_body or {}).get("kicker") or ("СХЕМА" if mid.startswith("dia_") else "КАДР")).strip(),
            "media_id": mid,
            "caption": str((op_body or {}).get("caption") or "").strip(),
        })
        if layout == "media_split":
            body = str((op_body or {}).get("body") or "").strip()
            bullets = (op_body or {}).get("bullets")
            if body:
                slide["body"] = body
            if isinstance(bullets, list) and bullets:
                slide["bullets"] = bullets
            elif not body:
                slide["bullets"] = [
                    "Ключевой аспект отображаемых данных",
                    "Практические выводы и дальнейшие шаги",
                ]
    else:  # bullets, chart_hero, etc.
        slide.update({
            "title": "Ключевые тезисы реализации",
            "kicker": "ТЕЗИСЫ",
            "bullets": [
                "Первый ключевой тезис реализации",
                "Второй аргумент в пользу выбранного направления",
                "Ожидаемый результат и сроки исполнения",
            ],
        })
    return slide


def structure_focus_ids(
    before: dict[str, Any],
    after: dict[str, Any],
    op_body: dict[str, Any],
) -> str:
    """Comma-separated slide ids to show after undo or redo.

    The client picks the first id that still exists. A new slide is listed
    first so redo lands on the copy; the slide the user acted on follows,
    so undo (which drops the copy) lands there. Delete lists the removed
    id first, then a neighbor that remains after redo.
    """

    def _ids(deck: dict[str, Any]) -> list[str]:
        out: list[str] = []
        for slide in deck.get("slides") or []:
            if isinstance(slide, dict) and slide.get("id"):
                out.append(str(slide["id"]))
        return out

    before_ids = _ids(before if isinstance(before, dict) else {})
    after_ids = _ids(after if isinstance(after, dict) else {})
    added = [i for i in after_ids if i not in before_ids]
    removed = [i for i in before_ids if i not in after_ids]
    anchor = str((op_body or {}).get("id") or "")
    op = str((op_body or {}).get("op") or "").strip().lower()
    focus: list[str] = []
    if op == "reorder":
        order = [str(x) for x in ((op_body or {}).get("order") or [])]
        for i, sid in enumerate(order):
            if i >= len(before_ids) or before_ids[i] != sid:
                focus.append(sid)
                break
    elif op == "delete":
        focus.extend(removed)
        if anchor in before_ids:
            idx = before_ids.index(anchor)
            for j in (idx + 1, idx - 1):
                if 0 <= j < len(before_ids) and before_ids[j] != anchor:
                    focus.append(before_ids[j])
                    break
    else:
        focus.extend(added)
        if anchor:
            focus.append(anchor)
    seen: list[str] = []
    for sid in focus:
        if sid and sid not in seen:
            seen.append(sid)
    return ",".join(seen) or "*"


def apply_deck_structure(
    deck: dict[str, Any],
    op_body: dict[str, Any],
) -> dict[str, Any]:
    """Reorder / duplicate / delete slides. Returns a new deck dict."""
    if not isinstance(deck, dict) or not isinstance(op_body, dict):
        raise DeckIrError("deck/op must be objects")
    op = str(op_body.get("op") or "").strip().lower()
    out = copy.deepcopy(deck)
    slides = list(_slide_list(out))
    by_id = {str(s["id"]): s for s in slides}

    if op == "reorder":
        order = op_body.get("order")
        if not isinstance(order, list) or not order:
            raise DeckIrError("reorder requires order list")
        ids = [str(x) for x in order]
        if len(ids) != len(by_id) or set(ids) != set(by_id):
            raise DeckIrError("order must be a permutation of slide ids")
        out["slides"] = [copy.deepcopy(by_id[i]) for i in ids]
        return out

    if op == "duplicate":
        sid = str(op_body.get("id") or "")
        if sid not in by_id:
            raise DeckIrError(f"unknown slide id: {sid!r}")
        idx = next(i for i, s in enumerate(slides) if str(s["id"]) == sid)
        clone = copy.deepcopy(slides[idx])
        new_id = _fresh_slide_id(set(by_id))
        clone["id"] = new_id
        slides.insert(idx + 1, clone)
        out["slides"] = slides
        return out

    if op == "delete":
        sid = str(op_body.get("id") or "")
        if sid not in by_id:
            raise DeckIrError(f"unknown slide id: {sid!r}")
        if len(slides) <= 1:
            raise DeckIrError("cannot delete the last slide")
        out["slides"] = [s for s in slides if str(s["id"]) != sid]
        return out

    if op in ("insert", "add"):
        layout = str(op_body.get("layout") or "bullets").strip().lower()
        if layout not in SLIDE_LAYOUTS:
            raise DeckIrError(f"unknown layout: {layout!r}")
        new_id = _fresh_slide_id(set(by_id))
        new_slide = _default_slide_for_layout(new_id, layout, op_body=op_body)
        at_id = str(op_body.get("id") or op_body.get("after_id") or "")
        if at_id and at_id in by_id:
            idx = next(i for i, s in enumerate(slides) if str(s["id"]) == at_id)
            slides.insert(idx + 1, new_slide)
        else:
            slides.append(new_slide)
        out["slides"] = slides
        return out

    raise DeckIrError(f"unknown structure op: {op!r}")
