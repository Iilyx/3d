"""Save Liber-attached photos and turn them into figure slots (usr_XX)."""

from __future__ import annotations

import logging
import re
from io import BytesIO
from pathlib import Path
from typing import Any

log = logging.getLogger("case3.user_photos")

_MAX_BYTES = 4 * 1024 * 1024
_MAX_PIXELS = 16_000_000
_MAX_COUNT = 5
_NAME_OK = re.compile(r"^[a-zA-Z0-9._ -]{1,120}$")
_NUMBERED = re.compile(r"^((?:\d+[.)]\s*)+)(.+)$")
_PHOTO_HINT = re.compile(
    r"фото|фотк|лог|скрин|интерфейс|экран|схем|диаграм|logo|screen",
    re.IGNORECASE,
)
_FILE_PREFIX = re.compile(r"^(?:файл|file)\s+", re.IGNORECASE)


def clip_photo_files(files: list[Any], *, limit: int = _MAX_COUNT) -> list[Any]:
    """Keep the upload cap in one place. The API used to slice at 2."""
    return list(files)[: max(0, int(limit))]


def captions_from_intent(intent: str, count: int) -> list[str]:
    """Turn a numbered photo list in the user message into captions.

    ``3. 4. 5. фотки интерфейс`` becomes three identical captions.
    A numbered Source with no photo words is left alone.
    """
    n = max(0, int(count))
    if n <= 0:
        return []
    block: list[str] = []
    started = False
    for raw in (intent or "").splitlines()[:40]:
        line = raw.strip()
        if not line:
            if started:
                break
            continue
        m = _NUMBERED.match(line)
        if not m:
            if started:
                break
            continue
        started = True
        text = _FILE_PREFIX.sub("", m.group(2).strip())
        slots = max(1, len(re.findall(r"\d+", m.group(1))))
        for _ in range(slots):
            block.append(text)
            if len(block) >= n:
                break
        if len(block) >= n:
            break
    if not block or not _PHOTO_HINT.search(" ".join(block)):
        return []
    return block[:n]


def split_image_budget(images_budget: int, n_user: int, *, mode: str) -> tuple[int, int]:
    """Return ``(llm_max_images, merge_max_images)``.

    A presentation that already has uploads must not spend the leftover
    budget on generated ``fig_*`` — those frames stole the screenshot slots.
    """
    n = max(0, int(n_user))
    budget = max(0, int(images_budget))
    if n:
        budget = min(8, max(budget, n))
    if (mode or "").strip().lower() == "presentation" and n:
        return 0, n
    return max(0, budget - n), budget


class UserPhotoError(ValueError):
    pass


def _is_png(data: bytes) -> bool:
    return data.startswith(b"\x89PNG\r\n\x1a\n")


def _is_jpeg(data: bytes) -> bool:
    return data[:3] == b"\xff\xd8\xff"


def _pixel_size(data: bytes) -> tuple[int, int]:
    from PIL import Image  # type: ignore

    with Image.open(BytesIO(data)) as im:
        return int(im.size[0]), int(im.size[1])


def bytes_to_png(data: bytes) -> bytes:
    if len(data) > _MAX_BYTES:
        raise UserPhotoError(f"photo too large (>{_MAX_BYTES // (1024 * 1024)} MiB)")
    if not (_is_png(data) or _is_jpeg(data)):
        raise UserPhotoError("photo must be PNG or JPEG")
    try:
        width, height = _pixel_size(data)
    except UserPhotoError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise UserPhotoError("photo must be PNG or JPEG") from exc
    if width < 1 or height < 1 or width * height > _MAX_PIXELS:
        raise UserPhotoError(
            f"photo is too many pixels ({width}×{height}, max 16 MP)"
        )
    if _is_png(data):
        return data
    if _is_jpeg(data):
        try:
            from PIL import Image  # type: ignore
        except ImportError as exc:
            raise UserPhotoError("JPEG needs pillow — pip install pillow") from exc
        im = Image.open(BytesIO(data))
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA")
        buf = BytesIO()
        im.save(buf, format="PNG")
        out = buf.getvalue()
        if len(out) > _MAX_BYTES:
            raise UserPhotoError("converted PNG too large")
        return out
    raise UserPhotoError("photo must be PNG or JPEG")


def save_user_photos(
    upload_dir: Path,
    items: list[tuple[str, bytes]],
    *,
    captions: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Write PNGs to upload_dir/user_photos/ and return figure metas (source=upload)."""
    if len(items) > _MAX_COUNT:
        raise UserPhotoError(f"at most {_MAX_COUNT} photos")
    dest_dir = upload_dir / "user_photos"
    dest_dir.mkdir(parents=True, exist_ok=True)
    caps = list(captions or [])
    out: list[dict[str, Any]] = []
    for i, (filename, raw) in enumerate(items, start=1):
        name = Path(filename or f"photo_{i}.png").name
        if not _NAME_OK.match(name):
            name = f"photo_{i}.png"
        png = bytes_to_png(raw)
        fid = f"usr_{i:02d}"
        path = dest_dir / f"{fid}.png"
        path.write_bytes(png)
        cap = (caps[i - 1] if i - 1 < len(caps) else "").strip() or f"Фото {i}"
        out.append(
            {
                "id": fid,
                "caption": cap,
                "prompt": f"user upload: {name}",
                "width": r"0.85\textwidth",
                "source": "upload",
                "path": str(path),
            }
        )
        log.info("user photo %s ← %s (%d bytes)", fid, name, len(png))
    return out


def materialize_user_figures(
    figures: list[dict[str, Any]],
    figs_dir: Path,
) -> dict[str, Any]:
    """Copy upload-sourced figures into figs_dir; return media status entries."""
    figs_dir.mkdir(parents=True, exist_ok=True)
    status: dict[str, Any] = {}
    for fig in figures:
        if str(fig.get("source") or "") != "upload":
            continue
        fid = str(fig.get("id") or "")
        src = Path(str(fig.get("path") or ""))
        if not fid or not src.is_file():
            status[fid or "?"] = {
                "ok": False,
                "error": "missing upload path",
                "kind": "figure",
            }
            continue
        dest = figs_dir / f"{fid}.png"
        dest.write_bytes(src.read_bytes())
        status[fid] = {"ok": True, "path": str(dest), "kind": "figure", "source": "upload"}
    return status


def merge_user_figures(
    llm_figures: list[dict[str, Any]],
    user_figures: list[dict[str, Any]],
    *,
    max_images: int,
) -> list[dict[str, Any]]:
    """User uploads first; then LLM figures that fit remaining budget."""
    budget = max(0, int(max_images))
    if budget <= 0:
        return []
    users = [dict(u) for u in user_figures[:budget]]
    llm_by_id = {
        str(f.get("id") or "").strip(): f
        for f in (llm_figures or [])
        if isinstance(f, dict) and str(f.get("id") or "").strip()
    }
    for u in users:
        uid = str(u.get("id") or "").strip()
        if uid in llm_by_id:
            llm_fig = llm_by_id[uid]
            llm_cap = str(llm_fig.get("caption") or "").strip()
            cur_cap = str(u.get("caption") or "").strip()
            is_llm_generic = bool(re.fullmatch(r"(?i)фото\s*\d*", llm_cap))
            is_cur_generic = not cur_cap or bool(re.fullmatch(r"(?i)фото\s*\d*", cur_cap))
            if llm_cap and (not is_llm_generic or is_cur_generic):
                u["caption"] = llm_cap
            if llm_fig.get("width"):
                u["width"] = llm_fig["width"]

    user_caps = {str(u.get("caption") or "").strip().lower() for u in users}
    rest = budget - len(users)
    llm = [f for f in (llm_figures or []) if str(f.get("source") or "") != "upload"]
    # avoid id clashes with usr_*
    llm = [f for f in llm if not str(f.get("id") or "").startswith("usr_")]
    cleaned_llm: list[dict[str, Any]] = []
    for idx, f in enumerate(llm[:rest], start=1):
        fc = dict(f)
        cap = str(fc.get("caption") or "").strip()
        if cap and (
            re.fullmatch(r"(?i)фото\s*\d*", cap)
            or (cap.lower() in user_caps and len(cap) <= 10)
        ):
            fc["caption"] = f"Иллюстрация {idx}"
        cleaned_llm.append(fc)
    return users + cleaned_llm


def _image_path_to_data_url(path: Path, *, max_edge: int = 768) -> str | None:
    try:
        from PIL import Image
    except ImportError:
        log.warning("vision skipped: pillow missing")
        return None
    try:
        im = Image.open(path)
        im = im.convert("RGB")
        im.thumbnail((max_edge, max_edge))
        buf = BytesIO()
        im.save(buf, format="JPEG", quality=80, optimize=True)
    except (OSError, ValueError) as exc:
        log.warning("vision skip %s: %s", path.name, exc)
        return None
    import base64

    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def user_photos_to_vision_images(
    user_figures: list[dict[str, Any]],
    *,
    limit: int = 5,
    max_edge: int = 768,
) -> list[tuple[str, str]]:
    """Convert user figure image files into resized JPEG data URLs for vision LLMs.

    Returns [(fid, 'data:image/jpeg;base64,...'), ...]
    """
    out: list[tuple[str, str]] = []
    for fig in user_figures[:limit]:
        fid = str(fig.get("id") or "").strip()
        path_str = str(fig.get("path") or "").strip()
        if not fid or not path_str:
            continue
        p = Path(path_str)
        if not p.is_file():
            continue
        data_url = _image_path_to_data_url(p, max_edge=max_edge)
        if data_url:
            out.append((fid, data_url))
    return out


def _insert_user_slot_block(tex: str, block: str) -> str:
    """Prefer first section body; else after \\maketitle; else before \\end{document}."""
    # After first \section{...} line — beside early prose, not an appendix dump.
    sec = re.search(r"(\\section\*?\{[^}]*\}\s*)", tex)
    if sec:
        at = sec.end()
        return tex[:at] + "\n" + block + "\n" + tex[at:]
    mt = re.search(r"(\\maketitle\s*)", tex)
    if mt:
        at = mt.end()
        return tex[:at] + "\n" + block + "\n" + tex[at:]
    marker = r"\end{document}"
    idx = tex.rfind(marker)
    if idx == -1:
        return tex.rstrip() + "\n\n" + block
    return tex[:idx] + "\n" + block + "\n" + tex[idx:]


def deduplicate_slots_in_tex(tex: str) -> str:
    """Ensure each %CASE3_FIG:id%, %CASE3_CHART:id%, %CASE3_DIAG:id% appears at most once."""
    if not tex:
        return tex or ""
    seen: set[str] = set()

    def _repl(m: re.Match[str]) -> str:
        tag = m.group(1).lower()
        if tag in seen:
            return ""
        seen.add(tag)
        return m.group(0)

    return re.sub(
        r"(?m)^[ \t]*%CASE3_(?:FIG|CHART|DIAG):([a-z][a-z0-9_]{0,31})%[^\n]*\r?\n?",
        _repl,
        tex,
    )


def ensure_user_slots_in_tex(tex: str, user_figures: list[dict[str, Any]]) -> str:
    """If LLM omitted %CASE3_FIG:usr_XX%, inject slots near early body prose.
    Guarantees no duplicate slots exist in the returned text.
    """
    if not tex:
        return tex or ""
    tex = deduplicate_slots_in_tex(tex)
    if not user_figures:
        return tex
    missing = [
        f
        for f in user_figures
        if f"%CASE3_FIG:{f['id']}%" not in tex and f"figures/{f['id']}.png" not in tex
    ]
    if not missing:
        return tex
    block = "\n".join(f"%CASE3_FIG:{f['id']}%" for f in missing) + "\n"
    res = _insert_user_slot_block(tex, block)
    return deduplicate_slots_in_tex(res)
