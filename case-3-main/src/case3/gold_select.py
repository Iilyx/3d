"""Pick 2–3 gold exemplars by tag overlap with intent text."""

from __future__ import annotations

import re
from pathlib import Path

_TAG_SPLIT = re.compile(r"[,\s]+")


def _parse_index(text: str) -> list[dict]:
    items: list[dict] = []
    cur: dict | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- id:"):
            if cur:
                items.append(cur)
            cur = {"id": line.split(":", 1)[1].strip(), "file": "", "tags": []}
        elif cur is not None and line.startswith("file:"):
            cur["file"] = line.split(":", 1)[1].strip()
        elif cur is not None and line.startswith("tags:"):
            inside = line.split(":", 1)[1].strip().strip("[]")
            cur["tags"] = [t.strip() for t in _TAG_SPLIT.split(inside) if t.strip()]
    if cur:
        items.append(cur)
    return items


def intent_tokens(intent: str) -> set[str]:
    low = (intent or "").lower()
    tokens = set(re.findall(r"[a-zа-яё0-9_]+", low, flags=re.I))

    no_tables = bool(re.search(r"без\s+таблиц", low))
    no_images = bool(
        re.search(r"без\s+картин", low)
        or re.search(r"без\s+рисун", low)
        or re.search(r"без\s+иллюстрац", low)
    )
    no_charts = bool(
        re.search(r"без\s+график", low)
        or re.search(r"без\s+диаграмм", low)
        or re.search(r"без\s+chart", low)
    )

    boosts = [
        ("таблиц", "table"),
        ("список", "list"),
        ("списки", "list"),
        ("раздел", "sections"),
        ("отчёт", "report"),
        ("отчет", "report"),
        ("кратко", "short"),
        ("заметка", "memo"),
        ("картинк", "image"),
        ("рисунок", "figure"),
        ("рисунк", "figure"),
        ("схем", "figure"),
        ("иллюстрац", "illustration"),
        ("фото", "photo"),
        ("график", "chart"),
        ("диаграмм", "diagram"),
        ("столбчат", "bar"),
        ("линейн", "line"),
        ("круг", "donut"),
    ]
    for ru, en in boosts:
        if ru in low:
            tokens.add(en)

    # Phrase overrides AFTER stems («без таблиц» contains «таблиц»)
    if no_tables:
        tokens.add("no_table")
        tokens.discard("table")
    if no_images:
        tokens.discard("image")
        tokens.discard("figure")
        tokens.discard("photo")
        tokens.discard("illustration")
    if no_charts:
        tokens.discard("chart")
        tokens.discard("diagram")
        tokens.discard("bar")
        tokens.discard("line")
        tokens.discard("donut")
        tokens.discard("kpi")
        tokens.discard("graph")
        tokens.discard("numbers")

    if not tokens:
        tokens.add("default")
    return tokens


def _safe_gold_path(gold_dir: Path, rel: str) -> Path | None:
    if not rel or ".." in rel.replace("\\", "/").split("/"):
        return None
    p = (gold_dir / rel).resolve()
    root = gold_dir.resolve()
    try:
        p.relative_to(root)
    except ValueError:
        return None
    return p if p.is_file() else None


def select_gold(
    gold_dir: Path,
    intent: str,
    *,
    max_items: int = 3,
    max_images: int = 0,
) -> list[Path]:
    index_path = gold_dir / "index.yaml"
    if not index_path.is_file():
        return sorted(gold_dir.glob("*.tex"))[:max_items]

    items = _parse_index(index_path.read_text(encoding="utf-8"))
    tokens = intent_tokens(intent)
    scored: list[tuple[int, dict]] = []
    for it in items:
        tags = set(it.get("tags") or [])
        if it.get("id") == "image_slot" and max_images <= 0:
            continue
        # negative: no_table intent should not boost table gold
        if "no_table" in tokens and "table" in tags and "no_table" not in tags:
            continue
        score = len(tokens & tags)
        if "default" in tags:
            score += 1
        if score > 0:
            scored.append((score, it))
    scored.sort(key=lambda x: (-x[0], x[1].get("id", "")))
    chosen = scored[:max_items] if scored else ([(1, items[0])] if items else [])

    # Always include image_slot when images enabled and intent suggests visuals
    if max_images > 0 and ({"image", "figure", "photo", "illustration"} & tokens):
        for it in items:
            if it.get("id") == "image_slot":
                if all(c[1].get("id") != "image_slot" for c in chosen):
                    chosen = chosen[: max_items - 1] + [(99, it)]
                break

    paths: list[Path] = []
    for _, it in chosen:
        p = _safe_gold_path(gold_dir, it.get("file", ""))
        if p is not None:
            paths.append(p)
    return paths


def format_gold_appendix(paths: list[Path]) -> str:
    if not paths:
        return ""
    chunks = []
    for p in paths:
        body = p.read_text(encoding="utf-8").strip()
        chunks.append(f"### {p.name}\n```latex\n{body}\n```\n")
    return "\n\n## Gold examples (follow style; do not copy unrelated content)\n\n" + "\n".join(chunks)
