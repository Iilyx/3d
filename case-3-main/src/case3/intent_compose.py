"""Compose Liber Intent prose from UI controls (desk Form fields)."""

from __future__ import annotations

from case3.chart_html import CHART_TYPES
from case3.chart_style import intent_palette_lines, normalize_palette_id
from case3.diagrams import clamp_diagram_budget

_CHART_TYPE_LIST = ", ".join(sorted(CHART_TYPES))


def build_intent_from_ui(
    *,
    chat: str,
    chart_types: list[str],
    max_charts: int,
    max_images: int,
    forbid_charts: bool,
    forbid_images: bool,
    chart_hints: str = "",
    chart_auto: bool = False,
    chart_palette: str = "atelier",
    chart_style: str = "",
    doc_title: str = "",
    max_diagrams: int = 2,
    output_mode: str = "auto",
    deck_pack: str = "",
) -> str:
    """Compose Intent from chat + UI controls.

    chart_auto / empty chart_types → model picks type from CHART_TYPES by Source.
    chart_hints → free-text wishes (pie, «воронка»…); model maps to whitelist or skips.
    chart_palette / chart_style → color preset + optional look notes.
    doc_title → forced \\title (also applied post-LLM).
    max_* are ceilings, not quotas.
    max_diagrams → Liber Mermaid schemas; independent of charts.
    output_mode → report|diagram|presentation|auto (Liber composer pills).
    """
    parts: list[str] = []
    chat = (chat or "").strip()
    if chat:
        parts.append(chat)
    mode = (output_mode or "auto").strip().lower()
    if mode not in {"report", "diagram", "presentation", "auto"}:
        mode = "auto"
    md = clamp_diagram_budget(max_diagrams)
    req: list[str] = ["Требования UI:"]
    if mode == "diagram":
        hi = md if md > 1 else 1
        req.append(
            f"- РЕЖИМ СХЕМА (output_mode=diagram): только Mermaid diagrams[] (1–{hi}) "
            "и короткий LaTeX-stub — \\title + 1–2 абзаца описания схем; "
            "без таблиц KPI, без полного отчёта; PDF/DOCX не нужны"
        )
    elif mode == "presentation":
        pack = (deck_pack or "").strip() or "atelier"
        req.append(
            f"- РЕЖИМ ПРЕЗЕНТАЦИЯ: без PDF/DOCX — сразу дек (pack «{pack}»). "
            "Короткий LaTeX-stub + цифры/графики из Source; "
            "takeaways и KPI слайдопригодные (slides job соберёт PPTX)"
        )
    elif mode == "report":
        req.append("- РЕЖИМ ОТЧЁТ: полный PDF/DOCX как обычно")
    hints = (chart_hints or "").strip()
    clean = [t for t in chart_types if t in CHART_TYPES]
    auto = bool(chart_auto) or (not clean and not hints)
    palette = normalize_palette_id(chart_palette)
    title = (doc_title or "").strip()
    if title:
        # Marker parsed by generate.doc_title_from_intent — keep format stable.
        req.append(f"- CASE3_DOC_TITLE: {title}")
        req.append(
            f"- заголовок документа (\\title): «{title}» — ОБЯЗАТЕЛЬНО этот текст, "
            "не подменяй и не сокращай"
        )

    if forbid_charts or max_charts <= 0:
        req.append("- без HTML-графиков (charts: []; Chart.js) — это не про Mermaid-схемы")
    else:
        req.append(
            f"- не больше {max_charts} HTML-графиков (Chart.js); 0 OK если чисел мало; "
            "если в Source есть числа/даты/доли — сделай полезные диаграммы, "
            "не раздувай charts ради квоты"
        )
        req.append(
            f"- JSON charts[].type — только: {_CHART_TYPE_LIST} "
            "(pie→donut, столбцы→bar, тренд→line, топ-N→horizontal_bar, KPI→kpi)"
        )
        req.append(
            "- при 2+ графиках — РАЗНЫЕ типы (например line+donut или bar+horizontal_bar)"
        )
        req.extend(intent_palette_lines(palette, chart_style))
        req.append(
            "- caption на русском, конкретный (что сравниваем); "
            "canvas 1100×560; без фиолетового нейрослопа"
        )
        req.append(
            "- слот %CASE3_CHART:id% один на строке, БЕЗ обёртки \\begin{figure}; "
            "числа только из Source"
        )
        req.append(
            "- вёрстка: A4 portrait; широкие таблицы — tabularx{\\textwidth}{…} "
            "или p{…}/X; если всё ещё не влезает (≈6+ колонок) — "
            "только эту table в \\begin{landscape}…\\end{landscape}; "
            "не весь документ; не tabular{lll}"
        )
        if auto and not hints:
            req.append(
                "- типы на усмотрение модели по смыслу данных (playbook time→line, "
                "share→donut, compare→bar/grouped_bar)"
            )
        elif clean:
            req.append(
                "- ОБЯЗАТЕЛЬНО типы графиков по порядку (charts[0], charts[1], …): "
                + ", ".join(clean)
                + " — не подменяй на line/donut без причины"
            )
        if hints:
            req.append(f"- пожелания по виду/типу: {hints} (сведи к whitelist или пропусти)")
    if forbid_images:
        req.append("- без фото/иллюстраций (figures: [])")
    elif max_images <= 0:
        req.append(
            "- без сгенерированных fig_* (Image API); figures[] только usr_* "
            "если прикреплены, иначе figures: []"
        )
    else:
        # max_images > 0 only when API/pipeline already detected opt-in.
        req.append(
            f"- до {max_images} фото/иллюстраций (figures); DEFAULT-OFF, но сейчас "
            f"явный запрос на картинку — сделай до {max_images} сильных фото "
            "(лучше заполнить бюджет, если визуальных зацепок хватает); "
            "не выдумывай fig_* без запроса"
        )
        req.append(
            "- figures[].caption — русская подпись; "
            "figures[].prompt — English, photorealistic, detailed lighting/subject, "
            "no Cyrillic/watermark/tiny text; не дублируй числами charts; "
            "слот %CASE3_FIG:id% рядом с абзацем, не в конце документа"
        )
    # Liber Mermaid — independent of charts/photos; default-on when budget ≥ 1.
    if md <= 0:
        req.append("- без Mermaid-схем (diagrams: []) — CASE3_MAX_DIAGRAMS=0")
    else:
        req.append(
            f"- до {md} Mermaid-схем (JSON diagrams[] + слот %CASE3_DIAG:dia_NN% в LaTeX); "
            "DEFAULT-ON: если в Source есть шаги/роли/ветвления/структура/≥3 раздела — "
            "сделай ≥1 схему; пустой diagrams[] только при «без схем» в Intent "
            "или чисто числовом Source без структуры"
        )
        req.append(
            "- diagrams[].type: flowchart|sequence|mindmap|timeline|stateDiagram; "
            "первая строка mermaid соответствует type; id узлов ASCII, подписи RU из Source; "
            "держи схему компактной: 6–12 узлов (не >14; длинные списки инспекций/регионов группируй в 3–5 групп, без паутины из 30–40 узлов); "
            "для flowchart: каждый узел :::start|process|decision|ok|warn|data + classDef "
            "(Liber hex, без фиолетового); цвета задаёт модель"
        )
    parts.append("\n".join(req))
    return "\n\n".join(parts).strip()
