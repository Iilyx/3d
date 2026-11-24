"""Compile .tex → PDF (primary) / DOCX (secondary) via Docker image case-3:tex."""

from __future__ import annotations

from case3.paths import repo_root

import logging
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Callable

from case3.inject import (
    rewrite_media_includegraphics_paths,
    strip_missing_media_includes,
)
from case3.procutil import run_captured
from case3.tex_preamble import (
    TexStructureError,
    assert_tex_structure,
    ensure_document_preamble,
    strip_orphan_slots,
)

log = logging.getLogger("case3.render")

IMAGE = os.environ.get("CASE3_IMAGE", "case-3:tex")


class RenderError(RuntimeError):
    """LaTeX/Docker failed; optional path to saved .log."""

    def __init__(self, message: str, *, log_path: Path | None = None) -> None:
        super().__init__(message)
        self.log_path = log_path


# latexmk / pandoc can be slow; without a timeout Win desks hang forever with no meta bump.
_DOCKER_TIMEOUT_S = 900.0
_DOCKER_PROBE_TIMEOUT_S = 45.0


def _use_local_tex() -> bool:
    """Run latexmk/pandoc directly inside the backend container instead of Docker-in-Docker."""
    val = (os.environ.get("CASE3_TEX_LOCAL") or "").strip().lower()
    if val in {"1", "true", "yes", "on"}:
        return True
    if val in {"0", "false", "no", "off"}:
        return False
    if Path("/.dockerenv").exists() and shutil.which("latexmk") and shutil.which("pandoc"):
        return True
    return False


def _docker_run(workdir: Path, *cmd: str) -> None:
    if _use_local_tex():
        env = dict(os.environ)
        env["HOME"] = str(workdir.resolve())
        env["XDG_CACHE_HOME"] = str((workdir / ".cache").resolve())
        log.info("exec (local tex): %s", " ".join(cmd))
        try:
            run_captured(
                list(cmd),
                cwd=workdir.resolve(),
                env=env,
                check=True,
                timeout=_DOCKER_TIMEOUT_S,
            )
            return
        except subprocess.TimeoutExpired as exc:
            raise RenderError(
                f"{' '.join(cmd[:2])} timed out after {_DOCKER_TIMEOUT_S:.0f}s"
            ) from exc
        except subprocess.CalledProcessError as exc:
            tail = ((exc.stderr or "") + "\n" + (exc.stdout or ""))[-2000:]
            raise RenderError(
                f"{' '.join(cmd[:2])} failed (exit {exc.returncode}): {tail.strip()}"
            ) from exc

    if os.name == "nt":
        args = [
            "docker",
            "run",
            "--rm",
            "--net=none",
            "-e",
            "HOME=/work",
            "-e",
            "XDG_CACHE_HOME=/work/.cache",
            "-v",
            f"{workdir.resolve().as_posix()}:/work",
            "-w",
            "/work",
            IMAGE,
            *cmd,
        ]
    else:
        args = [
            "docker",
            "run",
            "--rm",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "--net=none",
            "-e",
            "HOME=/work",
            "-e",
            "XDG_CACHE_HOME=/work/.cache",
            "-v",
            f"{workdir.resolve().as_posix()}:/work",
            "-w",
            "/work",
            IMAGE,
            *cmd,
        ]
    log.info("exec: %s", " ".join(args))
    try:
        # encoding=utf-8: Win cp1251 locale crashes on Cyrillic TeX/docker logs.
        run_captured(
            args,
            check=True,
            timeout=_DOCKER_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        raise RenderError(
            f"docker {' '.join(cmd[:2])} timed out after {_DOCKER_TIMEOUT_S:.0f}s "
            "(Docker Desktop hung?)"
        ) from exc
    except subprocess.CalledProcessError as exc:
        tail = ((exc.stderr or "") + "\n" + (exc.stdout or ""))[-2000:]
        raise RenderError(
            f"docker {' '.join(cmd[:2])} failed (exit {exc.returncode}): {tail.strip()}"
        ) from exc


def ensure_image() -> None:
    """Retry lookup — Docker daemon can flap under parallel load."""
    if _use_local_tex():
        missing = [tool for tool in ("latexmk", "pandoc") if not shutil.which(tool)]
        if missing:
            raise RenderError(f"Local TeX mode enabled, but missing binaries: {', '.join(missing)}")
        return
    import time

    last = None
    for attempt in range(4):
        # `docker images -q` is more reliable than `image inspect` on some hosts.
        try:
            r = run_captured(
                ["docker", "images", "-q", IMAGE],
                timeout=_DOCKER_PROBE_TIMEOUT_S,
            )
        except subprocess.TimeoutExpired as exc:
            raise RenderError(
                f"docker images timed out after {_DOCKER_PROBE_TIMEOUT_S:.0f}s — "
                "start Docker Desktop"
            ) from exc
        if r.returncode == 0 and (r.stdout or "").strip():
            return
        last = r
        time.sleep(0.35 * (attempt + 1))
    detail = ""
    if last is not None:
        detail = f" ({(last.stderr or last.stdout or '')[:120].strip()})"
    raise RenderError(
        f"Docker image {IMAGE!r} missing. Run: scripts\\setup.cmd{detail}"
    )


_DOCKER_WARMED = False


def warmup_docker(*, background: bool = True) -> bool:
    """Warm up the Docker container (docker run --rm case-3:tex true) to prevent cold start."""
    global _DOCKER_WARMED

    def _do_warmup() -> bool:
        global _DOCKER_WARMED
        if _use_local_tex():
            _DOCKER_WARMED = True
            return True
        try:
            ensure_image()
            r = run_captured(["docker", "run", "--rm", IMAGE, "true"], timeout=45.0)
            if r.returncode == 0:
                _DOCKER_WARMED = True
                log.info("Docker container %s warmed up successfully", IMAGE)
                return True
            log.warning("Docker warmup non-zero exit %d: %s", r.returncode, r.stderr)
            return False
        except Exception as exc:  # noqa: BLE001
            log.info("Docker warmup skipped/failed: %s", exc)
            return False

    if background:
        threading.Thread(target=_do_warmup, name="case3-docker-warmup", daemon=True).start()
        return True
    return _do_warmup()


def is_docker_warmed() -> bool:
    return _DOCKER_WARMED


def _save_tex_logs(work: Path, stem: str, log_dir: Path | None) -> Path | None:
    if log_dir is None:
        return None
    log_dir.mkdir(parents=True, exist_ok=True)
    saved = None
    for name in (f"{stem}.log", f"{stem}.blg", "texput.log"):
        src = work / name
        if src.is_file():
            dest = log_dir / name
            shutil.copy2(src, dest)
            saved = dest
            log.info("saved TeX log → %s", dest)
    return saved


def prepare_tex_source(tex_path: Path) -> str:
    """Harden .tex on disk before Docker: structure, slots, preamble."""
    raw = tex_path.read_text(encoding="utf-8")
    try:
        assert_tex_structure(raw)
    except TexStructureError as exc:
        raise RenderError(str(exc)) from exc
    hardened = ensure_document_preamble(strip_orphan_slots(raw))
    if hardened != raw:
        tex_path.write_text(hardened, encoding="utf-8")
        log.info("hardened TeX preamble/slots → %s", tex_path)
    return hardened


def _reference_docx(project_root: Path | None) -> Path | None:
    """Liber print-style Word template, if present."""
    roots: list[Path] = []
    if project_root is not None:
        roots.append(project_root.resolve())
    # case3/render.py → src/case3 → src → repo
    roots.append(repo_root())
    for root in roots:
        cand = root / "assets" / "docx" / "reference.docx"
        if cand.is_file():
            return cand
    return None


def render_tex(
    tex_path: Path,
    *,
    out_dir: Path,
    formats: set[str],
    extra_dirs: list[Path] | None = None,
    log_dir: Path | None = None,
    force: bool = False,
    project_root: Path | None = None,
    on_format: Callable[[str], None] | None = None,
) -> dict[str, Path]:
    ensure_image()
    tex_path = tex_path.resolve()
    prepare_tex_source(tex_path)
    stem = tex_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Path] = {}
    ref_docx = _reference_docx(project_root)

    with tempfile.TemporaryDirectory(prefix="case3-") as tmp:
        work = Path(tmp)
        (work / ".cache").mkdir()
        shutil.copy2(tex_path, work / tex_path.name)
        for d in extra_dirs or []:
            if d.is_dir():
                dest = work / d.name
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(d, dest)
        if ref_docx is not None:
            shutil.copy2(ref_docx, work / "reference.docx")

        # Soft-fail: rewrite bare fig_/cht_/dia_ paths, drop includes for missing
        # PNGs so latexmk does not Division-by-0.
        work_tex = work / tex_path.name
        raw_work = work_tex.read_text(encoding="utf-8")
        cleaned = rewrite_media_includegraphics_paths(raw_work)
        cleaned = strip_missing_media_includes(cleaned, work)
        if cleaned != raw_work:
            work_tex.write_text(cleaned, encoding="utf-8")
            log.warning(
                "render: rewrote/stripped media includegraphics before latexmk (%s)",
                work_tex.name,
            )

        # PDF is the primary, reliable artifact.
        if "pdf" in formats:
            if on_format:
                on_format("pdf")
            try:
                latexmk_cmd = [
                    "latexmk",
                    "-xelatex",
                    "-interaction=nonstopmode",
                    "-synctex=1",
                ]
                # Chart edits keep the same .tex + same PNG paths — force
                # re-read figures so the last restyle lands in the PDF.
                if force:
                    latexmk_cmd.append("-g")
                latexmk_cmd.append(tex_path.name)
                _docker_run(
                    work,
                    *latexmk_cmd,
                )
            except RenderError as exc:
                saved = _save_tex_logs(work, stem, log_dir)
                raise RenderError(str(exc), log_path=saved) from exc

            pdf_src = work / f"{stem}.pdf"
            if not pdf_src.is_file():
                saved = _save_tex_logs(work, stem, log_dir)
                raise RenderError("latexmk did not produce PDF", log_path=saved)
            _save_tex_logs(work, stem, log_dir)
            pdf_dst = out_dir / f"{stem}.pdf"
            shutil.copy2(pdf_src, pdf_dst)
            results["pdf"] = pdf_dst
            log.info("wrote %s", pdf_dst)

        # DOCX via pandoc + optional Liber reference.docx styles.
        if "docx" in formats:
            if on_format:
                on_format("docx")
            media_dir = "docx_media"
            from case3.tex_preamble import tex_for_pandoc

            pandoc_name = f"{stem}.pandoc.tex"
            pandoc_tex = work / pandoc_name
            pandoc_tex.write_text(
                tex_for_pandoc((work / tex_path.name).read_text(encoding="utf-8")),
                encoding="utf-8",
            )
            pandoc_cmd = [
                "pandoc",
                pandoc_name,
                "-f",
                "latex",
                "-t",
                "docx",
            ]
            if (work / "reference.docx").is_file():
                pandoc_cmd.extend(["--reference-doc=reference.docx"])
            pandoc_cmd.extend(
                [
                    f"--extract-media=./{media_dir}",
                    "-o",
                    f"{stem}.docx",
                ]
            )
            try:
                _docker_run(work, *pandoc_cmd)
            except RenderError as exc:
                raise RenderError(str(exc), log_path=None) from exc
            docx_src = work / f"{stem}.docx"
            if not docx_src.is_file():
                raise RenderError("pandoc did not produce DOCX")
            docx_dst = out_dir / f"{stem}.docx"
            shutil.copy2(docx_src, docx_dst)
            # Keep pandoc original — Word rejects some post-mutated OOXML.
            from case3.docx_validate import docx_package_ok

            docx_backup = work / f"{stem}.docx.pre_mut"
            shutil.copy2(docx_dst, docx_backup)

            def _restore_if_broken(step: str) -> None:
                if docx_package_ok(docx_dst):
                    return
                log.warning("DOCX broken after %s — restoring pandoc original", step)
                shutil.copy2(docx_backup, docx_dst)

            # D5: bold header row + numeric align (soft-fail if no python-docx).
            from case3.docx_polish import try_polish_docx

            polished = try_polish_docx(docx_dst)
            _restore_if_broken("polish")
            # C7: itemize/enumerate → Liber List Bullet / List Number (soft-fail).
            from case3.docx_lists import try_fix_docx_lists

            lists_ok = try_fix_docx_lists(docx_dst)
            _restore_if_broken("lists")
            # Native OOXML charts (editable in Word). Cache-only chart XML —
            # no pptx xlsx package embed (that broke MS Word open). Opt-out:
            # CASE3_DOCX_NATIVE_CHARTS=0
            native_ids: list[str] = []
            import os as _os

            native_off = (_os.environ.get("CASE3_DOCX_NATIVE_CHARTS") or "1").strip().lower() in {
                "0",
                "false",
                "no",
                "off",
            }
            if not native_off:
                try:
                    import json as _json

                    from case3.docx_charts import (
                        palette_hexes_for_report,
                        try_replace_docx_native_charts,
                    )

                    palette = "atelier"
                    meta_p = out_dir / "meta.json"
                    if meta_p.is_file():
                        try:
                            meta = _json.loads(meta_p.read_text(encoding="utf-8"))
                            if isinstance(meta, dict) and meta.get("chart_palette"):
                                palette = str(meta.get("chart_palette") or palette)
                        except (OSError, _json.JSONDecodeError, TypeError):
                            pass
                    fj = out_dir / "figures.json"
                    if not fj.is_file():
                        fj = work / "figures.json"
                    native_ids = try_replace_docx_native_charts(
                        docx_dst,
                        figures_path=fj if fj.is_file() else None,
                        series_hexes=palette_hexes_for_report(palette),
                    )
                    if native_ids and not docx_package_ok(docx_dst):
                        log.warning(
                            "DOCX broken after native_charts — restoring pandoc original"
                        )
                        shutil.copy2(docx_backup, docx_dst)
                        native_ids = []
                    # Stamp meta so Liber/status can show native vs PNG honestly.
                    if meta_p.is_file() and native_ids:
                        try:
                            from case3.run_meta import update_meta

                            update_meta(
                                out_dir,
                                lambda m: m.__setitem__(
                                    "docx_native_charts", list(native_ids)
                                ),
                                logs_dir=log_dir,
                            )
                        except (OSError, _json.JSONDecodeError, TypeError):
                            pass
                except Exception as exc:  # noqa: BLE001 — never break DOCX
                    log.warning("docx native charts hook failed: %s", exc)
                    shutil.copy2(docx_backup, docx_dst)
                    native_ids = []
            try:
                from case3.docx_polish import orient_wide_tables

                orient_wide_tables(docx_dst)
                _restore_if_broken("landscape")
            except Exception as exc:  # noqa: BLE001 — never break DOCX
                log.warning("docx landscape hook failed: %s", exc)
                shutil.copy2(docx_backup, docx_dst)
            results["docx"] = docx_dst
            media_src = work / media_dir
            if native_ids and media_src.is_dir():
                from case3.docx_charts import prune_replaced_chart_pngs

                prune_replaced_chart_pngs(media_src, native_ids)
            if media_src.is_dir() and any(media_src.rglob("*")):
                media_dst = out_dir / media_dir
                if media_dst.exists():
                    shutil.rmtree(media_dst)
                shutil.copytree(media_src, media_dst)
                if native_ids:
                    from case3.docx_charts import prune_replaced_chart_pngs

                    prune_replaced_chart_pngs(media_dst, native_ids)
            log.info(
                "wrote %s%s%s%s%s",
                docx_dst,
                " (reference.docx)" if ref_docx else " (pandoc default)",
                " +polish" if polished else "",
                " +lists" if lists_ok else "",
                f" +native_charts={native_ids}" if native_ids else "",
            )

    return results
