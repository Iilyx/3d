"""Post-pandoc: replace cht_* PNG drawings with native Word OOXML charts."""

from __future__ import annotations

from case3.color_util import hex_to_rgb as _hex_to_rgb_tuple

import json
import logging
import re
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from pptx.dml.color import RGBColor

from case3.slides_chart_data import (
    NATIVE_CHART_TYPES,
    attach_series_ir,
    normalize_series_ir,
    series_from_figures_json,
)
from case3.slides_pptx_charts import add_native_chart

log = logging.getLogger("case3.docx_charts")

_CHT_IN_DESCR = re.compile(
    r"(?:docx_media/)?figures/(cht_\d+)\.png|(cht_\d+)\.png",
    re.I,
)
_DRAWING = re.compile(r"<w:drawing>.*?</w:drawing>", re.S)
_RID = re.compile(r'Id="(rId\d+)"')
_EMBED = re.compile(r'r:embed="(rId\d+)"')


def _hex_to_rgb(hx: str) -> RGBColor | None:
    rgb = _hex_to_rgb_tuple(hx)
    if rgb is None:
        return None
    return RGBColor(*rgb)


def _series_colors(hexes: list[str] | None) -> list[RGBColor]:
    out: list[RGBColor] = []
    for hx in hexes or []:
        rgb = _hex_to_rgb(str(hx))
        if rgb is not None:
            out.append(rgb)
    if not out:
        out = [RGBColor(0x2E, 0x42, 0x08), RGBColor(0x4F, 0x6B, 0x14)]
    return out


def _load_figures(
    *,
    figures: dict[str, Any] | None,
    figures_path: Path | None,
) -> dict[str, Any]:
    if isinstance(figures, dict):
        return figures
    if figures_path and Path(figures_path).is_file():
        try:
            data = json.loads(Path(figures_path).read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def _chart_series_for_id(figures: dict[str, Any], cid: str) -> dict[str, Any] | None:
    ir = series_from_figures_json(figures, cid)
    if ir:
        return ir
    for ch in figures.get("charts") or []:
        if not isinstance(ch, dict):
            continue
        if str(ch.get("id") or "") != cid:
            continue
        attach_series_ir(ch)
        return normalize_series_ir(ch.get("series"), default_type=str(ch.get("type") or "bar"))
    return None


def _chart_xml_word_safe(chart_xml: bytes) -> bytes:
    """Drop c:externalData so Word opens without pptx-style xlsx package embed.

    MS Word often refuses DOCX when chart points at a python-pptx Excel package
    embedding. Cached strCache/numCache stay — Word still shows the chart and
    recreates a workbook on edit (editable native chart).
    """
    text = chart_xml.decode("utf-8")
    text = re.sub(
        r"<c:externalData\b[^>]*>.*?</c:externalData>",
        "",
        text,
        flags=re.S,
    )
    text = re.sub(r"<c:externalData\b[^/]*/>", "", text)
    return text.encode("utf-8")


def _build_chart_package(
    series_ir: dict[str, Any],
    *,
    series_hexes: list[str] | None,
) -> bytes:
    """Return Word-safe chart1.xml bytes (caches only, no xlsx embed).

    Builds via python-pptx in-memory (BytesIO) — no throwaway .pptx on disk,
    so a full Windows desk does not fail mid-replace and leave PNG charts.
    """
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    ok = add_native_chart(
        slide,
        series_ir,
        left=Inches(0.5),
        top=Inches(0.5),
        width=Inches(9),
        height=Inches(5),
        series_colors=_series_colors(series_hexes),
    )
    if not ok:
        raise RuntimeError("add_native_chart failed")

    buf = BytesIO()
    prs.save(buf)
    buf.seek(0)
    with zipfile.ZipFile(buf) as zf:
        chart_xml = zf.read("ppt/charts/chart1.xml")
    return _chart_xml_word_safe(chart_xml)


def prune_replaced_chart_pngs(media_root: Path | str, chart_ids: list[str]) -> int:
    """Delete replaced cht_*.png under docx_media (and nested figures/)."""
    root = Path(media_root)
    if not root.is_dir() or not chart_ids:
        return 0
    removed = 0
    for cid in chart_ids:
        stem = str(cid or "").strip()
        if not stem.startswith("cht_"):
            continue
        for p in root.rglob(f"{stem}.png"):
            try:
                p.unlink()
                removed += 1
                log.info("pruned replaced chart PNG %s", p)
            except OSError as exc:
                log.warning("could not prune %s: %s", p, exc)
    return removed


def _next_rid(rels_xml: str) -> int:
    nums = [int(m.group(1)) for m in re.finditer(r'Id="rId(\d+)"', rels_xml)]
    return (max(nums) if nums else 0) + 1


def _chart_drawing_xml(*, rid: str, extent_cx: str, extent_cy: str, doc_pr_id: str) -> str:
    # Namespaces on graphic/chart — Word is stricter than LibreOffice.
    return (
        f"<w:drawing>"
        f'<wp:inline distT="0" distB="0" distL="0" distR="0" '
        f'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
        f'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        f'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f'<wp:extent cx="{extent_cx}" cy="{extent_cy}"/>'
        f'<wp:effectExtent l="0" t="0" r="0" b="0"/>'
        f'<wp:docPr id="{doc_pr_id}" name="Chart"/>'
        f"<wp:cNvGraphicFramePr>"
        f'<a:graphicFrameLocks noChangeAspect="1"/>'
        f"</wp:cNvGraphicFramePr>"
        f"<a:graphic>"
        f'<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/chart">'
        f'<c:chart xmlns:c="http://schemas.openxmlformats.org/drawingml/2006/chart" '
        f'r:id="{rid}"/>'
        f"</a:graphicData>"
        f"</a:graphic>"
        f"</wp:inline>"
        f"</w:drawing>"
    )


def _extract_extent(drawing: str) -> tuple[str, str]:
    m = re.search(r'<wp:extent\s+cx="(\d+)"\s+cy="(\d+)"', drawing)
    if m:
        return m.group(1), m.group(2)
    return "5486400", "3200400"


def _extract_docpr_id(drawing: str) -> str:
    m = re.search(r'<wp:docPr[^>]*\bid="(\d+)"', drawing)
    return m.group(1) if m else "100"


def _match_cht_id(drawing: str) -> str | None:
    for m in _CHT_IN_DESCR.finditer(drawing):
        return m.group(1) or m.group(2)
    return None


def _suppress_chart_title(chart_xml: bytes) -> bytes:
    """Hide OOXML auto-title so pandoc caption is the only title (no duplicate)."""
    text = chart_xml.decode("utf-8")
    text = re.sub(
        r"<c:autoTitleDeleted\b[^/]*/>",
        '<c:autoTitleDeleted val="1"/>',
        text,
        count=1,
    )
    text = re.sub(r"<c:title>.*?</c:title>", "", text, count=1, flags=re.S)
    return text.encode("utf-8")


def _rels_target_for_rid(rels_xml: str, rid: str) -> str | None:
    m = re.search(
        rf'<Relationship\b[^>]*\bId="{re.escape(rid)}"[^>]*\bTarget="([^"]+)"',
        rels_xml,
    )
    if m:
        return m.group(1)
    m = re.search(
        rf'<Relationship\b[^>]*\bTarget="([^"]+)"[^>]*\bId="{re.escape(rid)}"',
        rels_xml,
    )
    return m.group(1) if m else None


def _drop_relationship(rels_xml: str, rid: str) -> str:
    return re.sub(
        rf'<Relationship\b[^>]*\bId="{re.escape(rid)}"[^>]*/>',
        "",
        rels_xml,
        count=1,
    )


def replace_docx_native_charts(
    docx_path: Path | str,
    *,
    figures: dict[str, Any] | None = None,
    figures_path: Path | str | None = None,
    series_hexes: list[str] | None = None,
) -> list[str]:
    """Replace eligible cht_* picture drawings with native charts. Return replaced ids."""
    path = Path(docx_path)
    fj = _load_figures(
        figures=figures,
        figures_path=Path(figures_path) if figures_path else None,
    )
    # Ensure series IR present
    for ch in fj.get("charts") or []:
        if isinstance(ch, dict):
            attach_series_ir(ch)

    with zipfile.ZipFile(path, "r") as zf:
        names = set(zf.namelist())
        if "word/document.xml" not in names or "word/_rels/document.xml.rels" not in names:
            return []
        document = zf.read("word/document.xml").decode("utf-8")
        rels = zf.read("word/_rels/document.xml.rels").decode("utf-8")
        content_types = zf.read("[Content_Types].xml").decode("utf-8")
        other_files = {
            n: zf.read(n)
            for n in names
            if n
            not in (
                "word/document.xml",
                "word/_rels/document.xml.rels",
                "[Content_Types].xml",
            )
        }

    drawings = list(_DRAWING.finditer(document))
    if not drawings:
        return []

    replaced: list[str] = []
    new_parts: dict[str, bytes] = {}
    drop_media: set[str] = set()
    rid_n = _next_rid(rels)
    chart_n = 1
    # Existing chart overrides count
    while f"word/charts/chart{chart_n}.xml" in names or f"word/charts/chart{chart_n}.xml" in new_parts:
        chart_n += 1

    # Process from end so string offsets stay valid
    for match in reversed(drawings):
        drawing = match.group(0)
        cid = _match_cht_id(drawing)
        if not cid:
            continue
        series_ir = _chart_series_for_id(fj, cid)
        if not series_ir:
            continue
        ctype = str(series_ir.get("type") or "").lower()
        if ctype not in NATIVE_CHART_TYPES:
            continue
        try:
            chart_xml = _build_chart_package(series_ir, series_hexes=series_hexes)
            chart_xml = _suppress_chart_title(chart_xml)
        except Exception as exc:  # noqa: BLE001
            log.warning("docx native chart build failed %s: %s", cid, exc)
            continue

        # Drop old PNG relationship + media part for this drawing.
        emb = _EMBED.search(drawing)
        if emb:
            old_rid = emb.group(1)
            target = _rels_target_for_rid(rels, old_rid)
            rels = _drop_relationship(rels, old_rid)
            if target:
                media_part = (
                    target
                    if target.startswith("word/")
                    else f"word/{target.lstrip('./')}"
                )
                drop_media.add(media_part)
                # Also common form word/media/...
                if not media_part.startswith("word/"):
                    drop_media.add(f"word/{media_part}")

        chart_part = f"word/charts/chart{chart_n}.xml"
        rels_part = f"word/charts/_rels/chart{chart_n}.xml.rels"
        chart_rid = f"rId{rid_n}"
        rid_n += 1

        # Cache-only chart: empty rels (no xlsx package — Word-safe).
        empty_rels = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            "</Relationships>"
        )
        new_parts[chart_part] = chart_xml
        new_parts[rels_part] = empty_rels.encode("utf-8")

        # document → chart relationship
        rels = rels.replace(
            "</Relationships>",
            f'<Relationship Id="{chart_rid}" '
            f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/chart" '
            f'Target="charts/chart{chart_n}.xml"/>'
            "</Relationships>",
            1,
        )

        override = (
            f'<Override PartName="/{chart_part}" '
            f'ContentType="application/vnd.openxmlformats-officedocument.drawingml.chart+xml"/>'
        )
        if override not in content_types:
            content_types = content_types.replace(
                "</Types>",
                override + "</Types>",
                1,
            )

        cx, cy = _extract_extent(drawing)
        doc_pr_id = _extract_docpr_id(drawing)
        new_drawing = _chart_drawing_xml(
            rid=chart_rid, extent_cx=cx, extent_cy=cy, doc_pr_id=doc_pr_id
        )
        document = document[: match.start()] + new_drawing + document[match.end() :]
        replaced.append(cid)
        chart_n += 1
        log.info("docx native chart %s → %s", cid, chart_part)

    if not replaced:
        return []

    # Rewrite zip (omit dropped media)
    out_buf_files = {
        n: data for n, data in other_files.items() if n not in drop_media
    }
    for media_part in drop_media:
        if media_part in out_buf_files:
            del out_buf_files[media_part]
        log.info("docx dropped replaced PNG %s", media_part)
    out_buf_files["word/document.xml"] = document.encode("utf-8")
    out_buf_files["word/_rels/document.xml.rels"] = rels.encode("utf-8")
    out_buf_files["[Content_Types].xml"] = content_types.encode("utf-8")
    out_buf_files.update(new_parts)

    tmp = path.with_suffix(path.suffix + ".native.tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in sorted(out_buf_files.items()):
            zf.writestr(name, data)
    tmp.replace(path)
    return list(reversed(replaced))  # chronological order


def try_replace_docx_native_charts(
    docx_path: Path | str,
    *,
    figures: dict[str, Any] | None = None,
    figures_path: Path | str | None = None,
    series_hexes: list[str] | None = None,
) -> list[str]:
    """Best-effort; never raise into render."""
    try:
        return replace_docx_native_charts(
            docx_path,
            figures=figures,
            figures_path=figures_path,
            series_hexes=series_hexes,
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("docx native charts skipped: %s", exc)
        return []


def palette_hexes_for_report(palette_id: str | None) -> list[str]:
    """Report palette → hex ladder for native charts."""
    from case3.chart_style import _PALETTES, normalize_palette_id

    pid = normalize_palette_id(palette_id or "atelier")
    if pid in _PALETTES:
        p = _PALETTES[pid]
        return [str(p["primary"]), *[str(a) for a in p["accents"]]]
    return ["#2E4208", "#4F6B14", "#7A9A28", "#B8D45A", "#D5DEC0"]
