"""Office Image API client: POST /generate + POST /edit (FastAPI wrapper).

Not Kandinsky / OpenAI images — local service e.g. http://192.168.4.101:8000
"""

from __future__ import annotations

import base64
import ipaddress
import json
import logging
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger("case3.image_api")

_MAX_IMAGE_BYTES = 12 * 1024 * 1024


def _env(*names: str, default: str | None = None) -> str | None:
    for n in names:
        v = os.environ.get(n, "").strip()
        if v:
            return v
    return default


def _safe_number(raw: str | None, default: float, kind=float):
    try:
        return kind(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class ImageApiConfig:
    base_url: str
    timeout_s: float
    max_images: int
    width: int
    height: int
    steps: int
    guidance: float
    seed: int
    allow_url_download: bool
    api_key: str | None = None

    @property
    def generate_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/generate"

    @property
    def edit_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/edit"

    @property
    def health_url(self) -> str:
        """Root ping — worker may 404; connection proves process is up."""
        return f"{self.base_url.rstrip('/')}/"

    @classmethod
    def from_env(cls) -> ImageApiConfig:
        base_url = (_env("IMAGE_API_BASE_URL", "KANDINSKY_API_BASE_URL") or "").strip()
        # Win desk often sets IMAGE_API_BASE_URL but forgets IMAGE_MAX_IMAGES.
        # Old default "0" → Liber intent «без фото» and /generate never called.
        # If URL is configured and max unset → default 2 (matches .env.example).
        max_raw = _env("IMAGE_MAX_IMAGES", "KANDINSKY_MAX_IMAGES")
        if max_raw is None:
            max_default = 2 if base_url else 0
        else:
            max_default = int(_safe_number(max_raw, 0, int))
        max_images = max(0, max_default)
        allow_url = (_env("IMAGE_ALLOW_URL_DOWNLOAD", "KANDINSKY_ALLOW_URL_DOWNLOAD", default="0") or "0").lower() in {
            "1",
            "true",
            "yes",
        }
        w, h = 1024, 1024
        size = _env("IMAGE_SIZE", "KANDINSKY_SIZE", default="1024x1024") or "1024x1024"
        if "x" in size.lower():
            try:
                a, b = size.lower().split("x", 1)
                w, h = int(a), int(b)
            except ValueError:
                pass
        w = int(_safe_number(_env("IMAGE_WIDTH", default=str(w)), w, int))
        h = int(_safe_number(_env("IMAGE_HEIGHT", default=str(h)), h, int))
        return cls(
            base_url=base_url,
            timeout_s=_safe_number(_env("IMAGE_TIMEOUT_S", "KANDINSKY_TIMEOUT_S", default="180"), 180.0, float),
            max_images=max_images,
            width=max(64, min(w, 2048)),
            height=max(64, min(h, 2048)),
            steps=int(_safe_number(_env("IMAGE_STEPS", default="4"), 4, int)),
            guidance=_safe_number(_env("IMAGE_GUIDANCE", default="3"), 3.0, float),
            seed=int(_safe_number(_env("IMAGE_SEED", default="0"), 0, int)),
            allow_url_download=allow_url,
            api_key=_env("IMAGE_API_KEY", "KANDINSKY_API_KEY"),
        )


def image_api_configured() -> bool:
    return bool(ImageApiConfig.from_env().base_url)


def max_images_from_env() -> int:
    return ImageApiConfig.from_env().max_images


def probe_image_api(
    *,
    timeout_s: float = 1.5,
    cfg: ImageApiConfig | None = None,
) -> tuple[bool, str | None]:
    """Live ping of Image API (short timeout). Does not block report runs."""
    cfg = cfg or ImageApiConfig.from_env()
    if not cfg.base_url:
        return False, "IMAGE_API_BASE_URL empty"
    url = cfg.health_url
    try:
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.get(url, headers=_headers(cfg))
            if resp.status_code >= 500:
                return False, f"HTTP {resp.status_code}"
            return True, None
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:200]


def _headers(cfg: ImageApiConfig) -> dict[str, str]:
    h: dict[str, str] = {}
    if cfg.api_key:
        h["Authorization"] = f"Bearer {cfg.api_key}"
    return h


def _knobs(cfg: ImageApiConfig, *, negative_prompt: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "width": cfg.width,
        "height": cfg.height,
        "steps": cfg.steps,
        "guidance": cfg.guidance,
        "seed": cfg.seed,
    }
    if negative_prompt:
        # Forward-compat: worker may ignore; prompt also bakes Avoid:
        out["negative_prompt"] = negative_prompt
    return out


def _resolve_pack_id(pack_id: str | None) -> str | None:
    return (pack_id or "").strip() or None


def _outbound_prompt(prompt: str, *, pack_id: str | None) -> str:
    from case3.image_prompt import prepare_image_prompt

    return prepare_image_prompt(
        prompt,
        pack_id=_resolve_pack_id(pack_id),
        bake_avoid=True,
    )


def _is_png(data: bytes) -> bool:
    return data.startswith(b"\x89PNG\r\n\x1a\n")


def _is_jpeg(data: bytes) -> bool:
    return data[:3] == b"\xff\xd8\xff"


def _jpeg_to_png(data: bytes) -> bytes:
    try:
        from io import BytesIO

        from PIL import Image  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "image API returned JPEG; install pillow or configure API for PNG"
        ) from exc
    im = Image.open(BytesIO(data))
    if im.mode not in ("RGB", "RGBA"):
        im = im.convert("RGBA")
    buf = BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def _write_image_bytes(dest: Path, data: bytes) -> None:
    if len(data) > _MAX_IMAGE_BYTES:
        raise RuntimeError(f"image too large: {len(data)} bytes")
    if _is_jpeg(data):
        data = _jpeg_to_png(data)
    if not _is_png(data):
        raise RuntimeError("image is not PNG/JPEG")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)


def _same_api_host(url: str, api_base: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    api = urllib.parse.urlparse(api_base if "://" in api_base else f"http://{api_base}")
    if parsed.username or parsed.password:
        return False
    host = (parsed.hostname or "").lower()
    api_host = (api.hostname or "").lower()
    if not host or not api_host or parsed.scheme not in {"http", "https"}:
        return False
    return host == api_host


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _public_https(url: str) -> bool:
    """Explicit opt-in path: https whose every address is a public unicast."""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    if parsed.username or parsed.password:
        return False
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
    except socket.gaierror:
        return False
    if not infos:
        return False
    for info in infos:
        if _is_blocked_ip(ipaddress.ip_address(info[4][0])):
            return False
    return True


def _download_url(url: str, dest: Path, *, cfg: ImageApiConfig) -> None:
    # Default: only the Image API host (after loopback rewrite).
    # IMAGE_ALLOW_URL_DOWNLOAD=1 additionally allows public https.
    if not (
        _same_api_host(url, cfg.base_url)
        or (cfg.allow_url_download and _public_https(url))
    ):
        raise RuntimeError(
            "API returned url but download blocked "
            "(prefer base64 string; set IMAGE_ALLOW_URL_DOWNLOAD=1 for public https)"
        )
    # No redirect follow → prevents SSRF via 302 to metadata/LAN
    with httpx.Client(timeout=cfg.timeout_s, follow_redirects=False) as client:
        resp = client.get(url)
        if resp.is_redirect:
            raise RuntimeError("image URL redirects are not followed")
        resp.raise_for_status()
        data = resp.content
    if len(data) > _MAX_IMAGE_BYTES:
        raise RuntimeError("image download exceeded size limit")
    _write_image_bytes(dest, data)


def _looks_like_image_path(s: str) -> bool:
    """Relative paths from office wrappers: outputs/foo.png (not base64)."""
    low = s.lower()
    if any(low.endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif")):
        return True
    if "/" in s and not s.startswith("data:"):
        # path-ish: slash + dotted filename (`.` is not in the base64 alphabet)
        return "." in s.rsplit("/", 1)[-1]
    return False


def _join_api_path(base_url: str, path: str) -> str:
    return urllib.parse.urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def _rewrite_loopback_url(url: str, api_base: str) -> str:
    """Map http://127.0.0.1/... from the GPU box to IMAGE_API_BASE_URL host."""
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    if host not in {"127.0.0.1", "localhost", "0.0.0.0", "::1"}:
        return url
    api = urllib.parse.urlparse(api_base if "://" in api_base else f"http://{api_base}")
    if not api.netloc:
        return url
    return urllib.parse.urlunparse(
        (api.scheme or parsed.scheme or "http", api.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
    )


def decode_image_string(payload: Any, *, cfg: ImageApiConfig, dest: Path) -> None:
    """Decode FastAPI `str` (or dict) image response into dest PNG."""
    # JSON object wrappers
    if isinstance(payload, dict):
        for key in ("b64_json", "image", "data", "result", "png", "content", "url", "path"):
            if key in payload:
                return decode_image_string(payload[key], cfg=cfg, dest=dest)
        raise RuntimeError(f"unexpected image object keys: {list(payload)[:8]}")

    if isinstance(payload, (bytes, bytearray)):
        raw = bytes(payload)
        if _is_png(raw) or _is_jpeg(raw):
            _write_image_bytes(dest, raw)
            return
        payload = raw.decode("utf-8", errors="replace")

    if isinstance(payload, list) and payload:
        return decode_image_string(payload[0], cfg=cfg, dest=dest)

    if not isinstance(payload, str):
        raise RuntimeError(f"unexpected image payload type: {type(payload).__name__}")

    s = payload.strip().strip('"').strip("'")
    if not s:
        raise RuntimeError("empty image string")

    # data URL
    if s.startswith("data:image"):
        try:
            b64 = s.split(",", 1)[1]
        except IndexError as exc:
            raise RuntimeError("bad data URL") from exc
        _write_image_bytes(dest, base64.b64decode(b64))
        return

    # Absolute URL
    if s.startswith("http://") or s.startswith("https://"):
        url = _rewrite_loopback_url(s, cfg.base_url) if cfg.base_url else s
        log.info("image download %s", url)
        _download_url(url, dest, cfg=cfg)
        return

    # raw base64 BEFORE path heuristics — JPEG b64 often starts with "/9j/"
    # which would otherwise be mistaken for a site-relative path.
    compact = "".join(s.split())
    if len(compact) >= 64:
        try:
            data = base64.b64decode(compact, validate=False)
        except Exception:
            data = b""
        if len(data) >= 32 and (_is_png(data) or _is_jpeg(data)):
            _write_image_bytes(dest, data)
            return

    # Relative URL / path (join with Image API base) — short refs only
    if cfg.base_url and len(s) < 512 and (s.startswith("/") or _looks_like_image_path(s)):
        url = _join_api_path(cfg.base_url, s)
        log.info("image download %s (from path %r)", url, s[:120])
        _download_url(url, dest, cfg=cfg)
        return

    try:
        data = base64.b64decode(compact, validate=False)
    except Exception as exc:
        snip = s[:80].replace("\n", " ")
        raise RuntimeError(
            f"image string is not base64/data-URL/URL (got {snip!r})"
        ) from exc
    if len(data) < 32:
        raise RuntimeError("decoded image too small")
    _write_image_bytes(dest, data)


def _parse_http_body(resp: httpx.Response) -> Any:
    ctype = (resp.headers.get("content-type") or "").lower()
    raw = resp.content or b""
    if "image/" in ctype or _is_png(raw) or _is_jpeg(raw):
        return raw
    text = raw.decode("utf-8", errors="replace") if raw else (resp.text or "")
    if "application/json" in ctype or (text[:1] in "{\"[") :
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text
    return text


def generate_png(
    cfg: ImageApiConfig,
    prompt: str,
    dest: Path,
    *,
    pack_id: str | None = None,
) -> None:
    """POST /generate — new image from prompt (pack-lock + brand-safe applied)."""
    from case3.image_prompt import brand_safe_negative

    if not cfg.base_url:
        raise RuntimeError("IMAGE_API_BASE_URL is empty")
    cooked = _outbound_prompt(prompt, pack_id=pack_id)
    body = {
        "prompt": cooked,
        **_knobs(cfg, negative_prompt=brand_safe_negative()),
    }
    if not body["prompt"]:
        raise RuntimeError("empty image prompt")
    url = cfg.generate_url
    log.info(
        "image POST %s prompt_len=%d pack=%s",
        url,
        len(body["prompt"]),
        pack_id or "-",
    )
    # connect=5s: fail fast when LAN Image API is down (Win 10061).
    timeout = httpx.Timeout(cfg.timeout_s, connect=5.0)
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=body, headers=_headers(cfg))
            resp.raise_for_status()
            payload = _parse_http_body(resp)
        decode_image_string(payload, cfg=cfg, dest=dest)
    except Exception as exc:
        # Surface target URL — WinError 10061 usually means IMAGE_API_BASE_URL down/wrong
        raise RuntimeError(f"Image API {url}: {exc}") from exc


def _png_bytes_max_side(png_bytes: bytes, max_side: int = 512) -> bytes:
    """Downscale for CF Flux.2 Klein refs (≤512²). No-op if already small / no Pillow."""
    try:
        from io import BytesIO

        from PIL import Image  # type: ignore
    except ImportError:
        return png_bytes
    im = Image.open(BytesIO(png_bytes))
    w, h = im.size
    if max(w, h) <= max_side:
        if im.format == "PNG":
            return png_bytes
        buf = BytesIO()
        im.save(buf, format="PNG")
        return buf.getvalue()
    scale = max_side / float(max(w, h))
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    im = im.convert("RGBA") if im.mode not in ("RGB", "RGBA") else im
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    buf = BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def edit_png(
    cfg: ImageApiConfig,
    prompt: str,
    source_png: Path,
    dest: Path,
    *,
    pack_id: str | None = None,
) -> None:
    """POST /edit — office FastAPI expects multipart; prefer base64 form field.

    Swagger ``image: array[string]`` → form field ``image`` = base64 (not file).
    Fallback: UploadFile-style multipart, then ``images`` plural.
    Same pack-lock + brand-safe path as generate.
    """
    from case3.image_prompt import brand_safe_negative

    if not cfg.base_url:
        raise RuntimeError("IMAGE_API_BASE_URL is empty")
    if not source_png.is_file():
        raise RuntimeError(f"source image missing: {source_png}")
    prompt = _outbound_prompt(prompt, pack_id=pack_id)
    if not prompt:
        raise RuntimeError("empty edit prompt")
    png_bytes = _png_bytes_max_side(source_png.read_bytes(), 512)
    knobs = {
        k: str(v)
        for k, v in _knobs(cfg, negative_prompt=brand_safe_negative()).items()
    }
    b64 = base64.b64encode(png_bytes).decode("ascii")
    url = cfg.edit_url
    log.info(
        "image POST %s (edit) prompt_len=%d pack=%s",
        url,
        len(prompt),
        pack_id or "-",
    )
    errors: list[str] = []

    def _try_decode(resp: httpx.Response, label: str) -> bool:
        try:
            resp.raise_for_status()
            payload = _parse_http_body(resp)
            decode_image_string(payload, cfg=cfg, dest=dest)
            return True
        except Exception as exc:  # noqa: BLE001
            snip = (resp.text or "")[:140].replace("\n", " ")
            errors.append(f"{label}: {exc} body={snip!r}")
            log.debug("image edit attempt (%s) did not succeed: %s body=%s", label, exc, snip)
            return False

    with httpx.Client(timeout=cfg.timeout_s) as client:
        # 1) Multipart file upload under image= (office FastAPI UploadFile / list[UploadFile])
        data1 = {"prompt": prompt, **knobs}
        files1 = {"image": (source_png.name, png_bytes, "image/png")}
        if _try_decode(
            client.post(url, data=data1, files=files1, headers=_headers(cfg)),
            "multipart-file",
        ):
            return
        # 2) JSON body with image array (OpenAPI image: array<string>)
        json2 = {
            "prompt": prompt,
            "image": [b64],
            **_knobs(cfg, negative_prompt=brand_safe_negative()),
        }
        if _try_decode(client.post(url, json=json2, headers=_headers(cfg)), "json-b64-array"):
            return
        # 3) form field image=<base64> (legacy form backends)
        data3 = {"prompt": prompt, "image": b64, **knobs}
        if _try_decode(client.post(url, data=data3, headers=_headers(cfg)), "form-b64"):
            return
        # 4) plural images=
        data4 = {"prompt": prompt, "images": b64, **knobs}
        if _try_decode(client.post(url, data=data4, headers=_headers(cfg)), "form-images"):
            return

    log.warning("Image API %s edit failed across all formats: %s", url, " | ".join(errors[:3]))
    raise RuntimeError(f"Image API {url} edit failed: " + " | ".join(errors[:3]))


def generate_all_figures(
    figures: list[dict[str, Any]],
    figures_dir: Path,
    *,
    cfg: ImageApiConfig | None = None,
    on_progress: Any | None = None,
    pack_id: str | None = None,
    cancel_check: Any | None = None,
) -> dict[str, Any]:
    if cancel_check:
        cancel_check()
    cfg = cfg or ImageApiConfig.from_env()
    figures_dir.mkdir(parents=True, exist_ok=True)
    status: dict[str, Any] = {}
    if cfg.max_images <= 0 or not cfg.base_url:
        return status
    # Uploads already live on disk — only /generate for API-planned slots.
    # Do not slice the mixed list by max_images (uploads would steal the budget).
    upload_n = sum(1 for f in figures if str(f.get("source") or "") == "upload")
    api_budget = max(0, int(cfg.max_images) - upload_n)
    api_figs = [
        f for f in figures if str(f.get("source") or "") != "upload"
    ][:api_budget]
    if not api_figs:
        return status

    # Win desk: dead Image API used to hang ~180s/fig with no log after TeX.
    # Probe first; skip all slots so inject/latex can finish.
    ok_probe, probe_err = probe_image_api(timeout_s=3.0, cfg=cfg)
    if not ok_probe:
        reason = probe_err or "Image API unreachable"
        log.warning("image probe failed — skip %d figures: %s", len(api_figs), reason)
        for fig in api_figs:
            fid = str(fig.get("id") or "")
            if fid:
                status[fid] = {
                    "ok": False,
                    "error": f"Image API probe failed: {reason}"[:300],
                    "kind": "figure",
                }
        return status

    for fig in api_figs:
        if cancel_check:
            cancel_check()
        fid = fig["id"]
        dest = figures_dir / f"{fid}.png"
        log.info("image generate start %s → %s", fid, cfg.generate_url)
        try:
            generate_png(
                cfg,
                str(fig.get("prompt") or ""),
                dest,
                pack_id=pack_id,
            )
            status[fid] = {"ok": True, "path": str(dest), "kind": "figure"}
            log.info("image ok %s → %s", fid, dest)
            if cancel_check:
                cancel_check()
            if on_progress:
                on_progress(fid)
        except (
            httpx.HTTPError,
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            RuntimeError,
            OSError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            status[fid] = {"ok": False, "error": str(exc)[:300], "kind": "figure"}
            log.warning("image failed %s: %s", fid, exc)
            if dest.exists():
                dest.unlink()
    return status
