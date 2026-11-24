"""Regenerate or img2img-edit one figure PNG in an existing run, then rebuild docs."""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any, Literal

from case3.image_api import ImageApiConfig, edit_png, generate_png
from case3.image_prompt import ImagePromptError, ensure_english_image_prompt
from case3.render import RenderError
from case3.run_rebuild import rebuild_run_docs
from case3.tex_safe import escape_tex_text

log = logging.getLogger("case3.figure_edit")

EditMode = Literal["generate", "edit"]


class FigureEditError(RuntimeError):
    pass


def patch_figure_caption_in_tex(tex: str, figure_id: str, caption: str) -> str:
    """Replace \\caption{…} for a figure identified by \\label{fig|chart|dia:ID}."""
    caption = (caption or "").strip()
    if not caption or not figure_id:
        return tex
    esc = escape_tex_text(caption)
    fid = re.escape(figure_id)
    # caption immediately before \label{fig|chart|dia:id}
    pat = re.compile(
        rf"(\\caption\{{)([^{{}}]*)(\}}\s*\\label\{{(?:fig|chart|dia):{fid}\}})"
    )
    if pat.search(tex):
        return pat.sub(rf"\g<1>{esc}\g<3>", tex, count=1)
    # caption after includegraphics{…/id.png}
    pat2 = re.compile(
        rf"(\\includegraphics(?:\[[^\]]*\])?\{{(?:figures/)?{fid}\.png\}}\s*"
        rf"\\caption\{{)([^{{}}]*)(\}})",
        re.S,
    )
    if pat2.search(tex):
        return pat2.sub(rf"\g<1>{esc}\g<3>", tex, count=1)
    return tex


def delete_figure_in_tex(tex: str, figure_id: str) -> str:
    """Remove a figure environment, includegraphics line, or slot matching figure_id."""
    if not tex or not figure_id:
        return tex
    fid = re.escape(figure_id)

    # 1. Enclosing \begin{figure}...\end{figure} containing figure_id
    pos = 0
    while True:
        idx = tex.find(figure_id, pos)
        if idx == -1:
            break
        begin = tex.rfind(r"\begin{figure}", 0, idx)
        end_before = tex.rfind(r"\end{figure}", 0, idx)
        if begin != -1 and begin >= end_before:
            end = tex.find(r"\end{figure}", idx)
            if end != -1:
                end_pos = end + len(r"\end{figure}")
                while end_pos < len(tex) and tex[end_pos] in " \t\r\n":
                    end_pos += 1
                tex = tex[:begin] + tex[end_pos:]
                return tex
        pos = idx + len(figure_id)

    # 2. Standalone slot: %CASE3_(FIG|CHART|DIAG):figure_id%
    slot_pat = re.compile(rf"[ \t]*%CASE3_(?:FIG|CHART|DIAG):{fid}%\n?", re.I)
    if slot_pat.search(tex):
        return slot_pat.sub("", tex, count=1)

    # 3. Standalone \includegraphics line
    inc_pat = re.compile(
        rf"[ \t]*\\includegraphics(?:\[[^\]]*\])?\{{(?:figures/)?{fid}\.png\}}\n?",
        re.I,
    )
    if inc_pat.search(tex):
        return inc_pat.sub("", tex, count=1)

    return tex


def edit_figure_in_run(
    out_dir: Path,
    figure_id: str,
    *,
    mode: EditMode,
    prompt: str,
    caption: str | None = None,
    formats: set[str] | None = None,
    cfg: ImageApiConfig | None = None,
) -> dict[str, Any]:
    out_dir = out_dir.resolve()
    cfg = cfg or ImageApiConfig.from_env()
    if not cfg.base_url:
        raise FigureEditError("IMAGE_API_BASE_URL пуст — укажи URL офисного Image API")
    prompt = (prompt or "").strip()
    if not prompt:
        raise FigureEditError("нужен текст промпта")
    if mode not in ("generate", "edit"):
        raise FigureEditError("mode must be generate|edit")
    if figure_id.startswith("cht_"):
        raise FigureEditError("это график — используйте правку charts, не figures")
    try:
        prompt = ensure_english_image_prompt(prompt)
    except ImagePromptError as exc:
        raise FigureEditError(str(exc)) from exc

    caption_new = (caption or "").strip()

    from case3.run_undo import capture_before_edit

    capture_before_edit(out_dir, kind="figure", target=figure_id)

    figs_dir = out_dir / "figures"
    dest = figs_dir / f"{figure_id}.png"
    figs_dir.mkdir(parents=True, exist_ok=True)

    # Update figures.json prompt when present
    fj_path = out_dir / "figures.json"
    fj: dict[str, Any] = {}
    fj_bak: str | None = None
    if fj_path.is_file():
        try:
            fj_bak = fj_path.read_text(encoding="utf-8")
            fj = json.loads(fj_bak)
        except (OSError, json.JSONDecodeError):
            fj = {}
    figures = list(fj.get("figures") or [])
    idx = next(
        (i for i, f in enumerate(figures) if isinstance(f, dict) and f.get("id") == figure_id),
        -1,
    )

    bak: bytes | None = dest.read_bytes() if dest.is_file() else None
    meta_path = out_dir / "meta.json"
    meta_bak: str | None = meta_path.read_text(encoding="utf-8") if meta_path.is_file() else None
    texs = sorted(out_dir.glob("*.tex"))
    tex_bak: str | None = None
    if texs and texs[0].is_file():
        tex_bak = texs[0].read_text(encoding="utf-8")

    pack_id: str | None = None
    if meta_path.is_file():
        try:
            m0 = json.loads(meta_path.read_text(encoding="utf-8"))
            pack_id = (
                str(m0.get("image_style_pack") or m0.get("slides_theme_pack") or "")
                or str(m0.get("chart_palette") or "")
                or None
            )
        except (OSError, json.JSONDecodeError):
            pack_id = None

    try:
        if mode == "generate":
            generate_png(cfg, prompt, dest, pack_id=pack_id)
        else:
            if bak is None:
                raise FigureEditError(
                    f"нет исходного PNG для правки ({figure_id}.png) — сначала сгенерируйте"
                )
            tmp = dest.with_suffix(".edit.png")
            edit_png(cfg, prompt, dest, tmp, pack_id=pack_id)
            tmp.replace(dest)
    except FigureEditError:
        raise
    except Exception as exc:  # noqa: BLE001
        if bak is not None:
            dest.write_bytes(bak)
        raise FigureEditError(f"image API failed: {exc}") from exc

    if idx >= 0:
        fig = dict(figures[idx])
        fig["prompt"] = prompt
        if caption_new:
            fig["caption"] = caption_new
        figures[idx] = fig
        fj["figures"] = figures
        fj_path.write_text(json.dumps(fj, ensure_ascii=False, indent=2), encoding="utf-8")
    elif caption_new or prompt:
        # figure missing from json — still ok for PNG-only runs
        pass

    if caption_new and texs:
        patched = patch_figure_caption_in_tex(
            texs[0].read_text(encoding="utf-8"), figure_id, caption_new
        )
        texs[0].write_text(patched, encoding="utf-8")

    from case3.run_events import write_meta_atomic
    from case3.run_meta import update_meta

    def _mut_fig_edit(m: dict[str, Any]) -> None:
        med = dict(m.get("media_status") or {})
        med[figure_id] = {"ok": True, "path": str(dest), "kind": "figure"}
        m["media_status"] = med
        m["last_figure_edit"] = {
            "id": figure_id,
            "mode": mode,
            "prompt": prompt[:500],
            "caption": (caption_new or "")[:300] or None,
            "ts": int(time.time()),
        }

    meta = update_meta(out_dir, _mut_fig_edit)
    media = dict(meta.get("media_status") or {})

    try:
        artifacts = rebuild_run_docs(out_dir, formats=formats)
    except FileNotFoundError as exc:
        raise FigureEditError(str(exc)) from exc
    except RenderError as exc:
        if bak is not None:
            dest.write_bytes(bak)
        if fj_bak is not None:
            fj_path.write_text(fj_bak, encoding="utf-8")
        if meta_bak is not None:
            write_meta_atomic(meta_path, meta_bak)
        if tex_bak is not None:
            texs[0].write_text(tex_bak, encoding="utf-8")
        from case3.run_undo import clear_undo

        clear_undo(out_dir)
        raise FigureEditError(f"document rebuild failed: {exc}") from exc

    # If a deck already exists, refresh PPTX/twin so edited photo lands in slides.
    from case3.deck_refresh import refresh_deck_from_ir

    refresh_deck_from_ir(out_dir)

    v = int(dest.stat().st_mtime)
    from case3.run_undo import undo_meta

    return {
        "figure_id": figure_id,
        "mode": mode,
        "prompt": prompt,
        "caption": caption_new or None,
        "media_status": media,
        "artifacts": {k: str(p) for k, p in artifacts.items()},
        "version": v,
        "undo": undo_meta(out_dir),
    }


def delete_figure_in_run(
    out_dir: Path,
    figure_id: str,
    *,
    formats: set[str] | None = None,
) -> dict[str, Any]:
    """Delete a figure/chart from LaTeX, figures.json, and meta.json."""
    out_dir = out_dir.resolve()
    from case3.run_undo import capture_before_edit

    capture_before_edit(out_dir, kind="figure_delete", target=figure_id)

    # 1. Patch TeX file
    tex_path = None
    for cand in ("report.tex", "main.tex", f"{out_dir.name}.tex"):
        p = out_dir / cand
        if p.is_file():
            tex_path = p
            break
    if not tex_path:
        tex_files = list(out_dir.glob("*.tex"))
        if tex_files:
            tex_path = tex_files[0]

    if tex_path and tex_path.is_file():
        old_tex = tex_path.read_text(encoding="utf-8")
        new_tex = delete_figure_in_tex(old_tex, figure_id)
        if new_tex != old_tex:
            tex_path.write_text(new_tex, encoding="utf-8")

    # 2. Update figures.json
    fj_path = out_dir / "figures.json"
    if fj_path.is_file():
        try:
            fj = json.loads(fj_path.read_text(encoding="utf-8"))
            for key in ("figures", "charts", "diagrams"):
                if key in fj and isinstance(fj[key], list):
                    fj[key] = [
                        item
                        for item in fj[key]
                        if not (isinstance(item, dict) and item.get("id") == figure_id)
                    ]
            fj_path.write_text(
                json.dumps(fj, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    # 3. Update meta.json and remove PNG + deck references
    fig_png = out_dir / "figures" / f"{figure_id}.png"
    try:
        fig_png.unlink(missing_ok=True)
    except OSError:
        pass

    deck_json_path = out_dir / "slides" / "deck.json"
    if deck_json_path.is_file():
        try:
            deck_data = json.loads(deck_json_path.read_text(encoding="utf-8"))
            if isinstance(deck_data, dict) and isinstance(deck_data.get("slides"), list):
                changed_deck = False
                for sl in deck_data["slides"]:
                    if not isinstance(sl, dict):
                        continue
                    if sl.get("chart_id") == figure_id or sl.get("media_id") == figure_id:
                        changed_deck = True
                        sl.pop("chart_id", None)
                        sl.pop("media_id", None)
                        if sl.get("layout") in ("chart_hero", "chart_split", "media_hero", "media_split"):
                            sl["layout"] = "bullets"
                            if not sl.get("bullets"):
                                sl["bullets"] = [str(sl.get("caption") or sl.get("title") or "Тезис")]
                if changed_deck:
                    deck_json_path.write_text(
                        json.dumps(deck_data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
        except Exception:
            pass

    from case3.run_meta import update_meta

    media: dict[str, Any] = {}

    def _mut_del(m: dict[str, Any]) -> None:
        nonlocal media
        media = dict(m.get("media_status") or {})
        media[figure_id] = {"ok": False, "deleted": True}
        m["media_status"] = media
        m["last_figure_delete"] = {"id": figure_id, "ts": int(time.time())}

    update_meta(out_dir, _mut_del)

    # 4. Rebuild documents (soft-fail)
    fmts = formats if formats is not None else {"none"}
    artifacts: dict[str, Any] = {}
    try:
        artifacts = rebuild_run_docs(out_dir, formats=fmts)
    except Exception as exc:
        log.warning("delete_figure_in_run rebuild failed: %s", exc)

    from case3.deck_refresh import refresh_deck_from_ir

    refresh_deck_from_ir(out_dir)

    from case3.run_undo import undo_meta

    return {
        "figure_id": figure_id,
        "mode": "delete",
        "media_status": media,
        "artifacts": {k: str(p) for k, p in artifacts.items()},
        "undo": undo_meta(out_dir),
    }
