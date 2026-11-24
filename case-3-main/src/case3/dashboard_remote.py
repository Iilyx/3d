"""Read a Stimulsoft viewer service: /viewer stays open, GET /shot returns the files."""

from __future__ import annotations

import base64
import binascii
import io
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import httpx

from case3.dashboard_source import DashboardSourceError, dashboard_title


class DashboardRemoteError(Exception):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


@dataclass(frozen=True)
class ShotFile:
    name: str
    ext: str
    data: bytes


def service_base() -> str:
    raw = (os.environ.get("DASHBOARD_SERVICE_URL") or "http://127.0.0.1:8040").strip()
    return raw.rstrip("/") or "http://127.0.0.1:8040"


def public_service_base() -> str:
    """Browser-facing Stimulsoft URL (for iframe src when backend runs in Docker)."""
    raw = (
        os.environ.get("DASHBOARD_PUBLIC_URL")
        or os.environ.get("DASHBOARD_SERVICE_URL")
        or "http://127.0.0.1:8040"
    ).strip()
    return raw.rstrip("/") or "http://127.0.0.1:8040"


def viewer_url() -> str:
    return f"{public_service_base()}/viewer"


def _ext(item: dict) -> str:
    kind = str(item.get("kind") or "").lower()
    name = str(item.get("name") or "")
    if kind in {"png", "pdf"}:
        return kind
    if name.lower().endswith(".pdf"):
        return "pdf"
    return "png"


def _safe_name(name: str) -> str:
    base = Path(str(name or "")).name
    if not base or base in {".", ".."} or base != str(name):
        return ""
    return base


def _items(payload: dict) -> list[dict]:
    found: list[dict] = []
    png = payload.get("png")
    if isinstance(png, dict):
        found.append(png)
    for item in payload.get("pdfs") or []:
        if isinstance(item, dict):
            found.append(item)
    return found


def _read_local(path: str) -> bytes | None:
    """Same machine as the viewer: his JSON path is a real file."""
    try:
        file = Path(path)
        if not file.is_file():
            return None
        size = file.stat().st_size
        if size <= 0 or size > 40 * 1024 * 1024:
            return None
        return file.read_bytes()
    except OSError:
        return None


def files_from_shot(payload: dict, fetch_named) -> list[ShotFile]:
    """Bytes from /shot. A disk path on another machine is not a file."""
    files: list[ShotFile] = []
    for item in _items(payload):
        name = str(item.get("name") or "dashboard").strip() or "dashboard"
        ext = _ext(item)
        data: bytes | None = None
        encoded = item.get("data_b64")
        if isinstance(encoded, str) and encoded.strip():
            try:
                data = base64.b64decode(encoded, validate=False)
            except (binascii.Error, ValueError) as exc:
                raise DashboardRemoteError(
                    f"{name}: битый data_b64",
                    "bad_b64",
                ) from exc
        else:
            raw_path = item.get("path")
            if isinstance(raw_path, str) and raw_path.strip():
                data = _read_local(raw_path.strip())
            if not data:
                safe = _safe_name(name)
                data = fetch_named(safe) if safe else None
            if not data:
                shown = raw_path.strip() if isinstance(raw_path, str) else name
                raise DashboardRemoteError(
                    f"Сервис вернул путь {shown}, но этого файла нет на компьютере, "
                    f"где запущен Liber. API должен стоять на той же машине, что и его сервис.",
                    "no_bytes",
                )
        if not data:
            raise DashboardRemoteError(f"{name}: пустой файл", "no_bytes")
        files.append(ShotFile(name=name, ext=ext, data=data))
    return files


def join_pdfs(parts: list[bytes]) -> bytes | None:
    """One PDF for parse_dashboard, the same slot the settings drop uses."""
    blobs = [part for part in parts if part]
    if not blobs:
        return None
    if len(blobs) == 1:
        return blobs[0]
    import pypdfium2 as pdfium

    out = pdfium.PdfDocument.new()
    opened = []
    try:
        for raw in blobs:
            src = pdfium.PdfDocument(raw)
            opened.append(src)
            out.import_pages(src)
        sink = io.BytesIO()
        out.save(sink)
        return sink.getvalue()
    finally:
        for src in opened:
            src.close()
        out.close()


def capture_documents(payload: dict, fetch_named, parse) -> list[dict]:
    """One markdown: PNG and every table PDF go through parse_dashboard together."""
    if not isinstance(payload, dict) or not payload.get("ok"):
        detail = ""
        if isinstance(payload, dict):
            detail = str(payload.get("error") or "")
        raise DashboardRemoteError(detail or "снимок не удался", "shot_failed")
    files = files_from_shot(payload, fetch_named)
    pngs = [item for item in files if item.ext == "png"]
    pdfs = [item for item in files if item.ext == "pdf"]
    png = pngs[0].data if pngs else None
    pdf = join_pdfs([item.data for item in pdfs])
    if png is None and pdf is None:
        raise DashboardRemoteError("в снимке нет PNG и PDF", "empty")
    try:
        result = parse(png=png, pdf=pdf)
    except DashboardSourceError as exc:
        raise DashboardRemoteError(exc.message, exc.code) from exc
    source_name = pngs[0].name if pngs else pdfs[0].name
    title = dashboard_title(result.markdown)
    return [
        {
            "name": title or source_name,
            "markdown": result.markdown,
            "warnings": list(getattr(result, "warnings", []) or []),
        }
    ]


def fetch_shot_payload(
    base: str,
    client: httpx.Client,
    *,
    mrt: str = "",
) -> dict:
    url = f"{base.rstrip('/')}/shot"
    name = (mrt or "").strip()
    if name:
        url = f"{url}?mrt={quote(name)}"
    response = client.get(url)
    try:
        body = response.json()
    except ValueError as exc:
        raise DashboardRemoteError("сервис снимка вернул не JSON", "bad_shot") from exc
    if not isinstance(body, dict):
        raise DashboardRemoteError("сервис снимка вернул не объект", "bad_shot")
    return body


_ASK_BITS = (
    "дашборд",
    "фильтр",
    "стимул",
    "январ",
    "феврал",
    "март",
    "апрел",
    "мая",
    "июн",
    "июл",
    "август",
    "сентябр",
    "октябр",
    "ноябр",
    "декабр",
)


def might_ask_dashboard(text: str) -> bool:
    low = (text or "").casefold().replace("ё", "е")
    return any(re.search(rf"(?<![0-9a-zа-я]){re.escape(bit)}", low) for bit in _ASK_BITS)


def _norm(value: object) -> str:
    return str(value or "").strip().casefold().replace("ё", "е")


_EXPLICIT_DASHBOARD_OPEN = re.compile(
    r"(?:открой|покажи|загрузи|выведи|подтяни)\s+(?:мне\s+)?(?:дашборд|стимул\w*|экран|витрин\w*)"
    r"|(?:дашборд|стимул\w*)\s+(?:открой|покажи)",
    re.IGNORECASE,
)


def _phrase_has(phrase: str, needle: object) -> bool:
    left = _norm(phrase)
    right = _norm(needle)
    if not left or not right:
        return False
    if right.isdigit():
        if re.search(rf"(?<!\d){re.escape(right)}(?!\d)", left):
            return True
        if len(right) >= 4 and re.search(rf"(?<!\d){re.escape(right[-2:])}(?!\d)", left):
            return True
        return False
    if right in left:
        return True
    digits = "".join(ch for ch in right if ch.isdigit())
    if len(digits) >= 4 and re.search(rf"(?<!\d){re.escape(digits[-2:])}(?!\d)", left):
        return True
    from case3.chat_memory import _stem

    right_words = [w for w in re.findall(r"[а-яa-z0-9]{3,}", right) if not w.isdigit()]
    if right_words:
        left_stems = {_stem(w) for w in re.findall(r"[а-яa-z0-9]{3,}", left)}
        if all(_stem(w) in left_stems for w in right_words):
            return True
    return False


def _json_object(raw: str) -> dict:
    text = (raw or "").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        body = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}
    return body if isinstance(body, dict) else {}


def _choice_pairs(field: dict) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for choice in field.get("choices") or []:
        if isinstance(choice, dict):
            key = str(choice.get("key") if choice.get("key") is not None else "").strip()
            label = str(
                choice.get("value") if choice.get("value") is not None else key
            ).strip()
            pairs.append((key, label))
        elif choice is not None:
            text = str(choice).strip()
            pairs.append((text, text))
    return pairs


def _open_value(raw: object) -> object:
    """Choice keys go to /open. A plain integer stays a number; 0000000 stays text."""
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float) and raw.is_integer():
        return int(raw)
    if isinstance(raw, (list, dict)):
        return raw
    text = str(raw if raw is not None else "").strip()
    if re.fullmatch(r"-?(?:0|[1-9]\d*)", text):
        return int(text)
    return text


def _value_for_open(field: dict, value: object) -> object:
    """Catalog value or label → the choice key /open expects."""
    pairs = _choice_pairs(field)
    wanted = _norm(value)
    if pairs and wanted:
        for key, label in pairs:
            if wanted in {_norm(key), _norm(label)}:
                return _open_value(key if key != "" else label)
    return _open_value(value)


def _validate_filter_map(catalog: dict, phrase: str, wanted: object) -> dict[str, object]:
    """Keep only catalog filters whose chosen value or label appears in phrase."""
    if not isinstance(wanted, dict):
        return {}
    fields = [item for item in (catalog.get("filters") or []) if isinstance(item, dict)]
    by_name: dict[str, dict] = {}
    for field in fields:
        for label in (field.get("name"), field.get("alias")):
            key = _norm(label)
            if key:
                by_name[key] = field
    picked: dict[str, object] = {}
    for key, value in wanted.items():
        field = by_name.get(_norm(key))
        if field is None:
            continue
        name = str(field.get("name") or key).strip()
        pairs = _choice_pairs(field)
        if pairs:
            wanted_norm = _norm(value)
            match = next(
                (
                    pair
                    for pair in pairs
                    if wanted_norm and wanted_norm in {_norm(pair[0]), _norm(pair[1])}
                ),
                None,
            )
            if match is None:
                continue
            if not (_phrase_has(phrase, match[1]) or _phrase_has(phrase, match[0])):
                continue
            picked[name] = _open_value(match[0] if match[0] != "" else match[1])
            continue
        if _phrase_has(phrase, value):
            picked[name] = _open_value(value)
    return picked


def filters_from_model(catalog: dict, phrase: str, raw: str) -> dict[str, object]:
    """Keep only catalog filters the sentence actually names."""
    body = _json_object(raw)
    if not body.get("pull"):
        return {}
    return _validate_filter_map(catalog, phrase, body.get("filters"))


def validated_catalog_result(catalog: dict, phrase: str) -> dict[str, object]:
    """Adopt pre-filled POST /filters result entries only if grounded in phrase."""
    return _validate_filter_map(catalog, phrase, catalog.get("result"))


def catalog_result_filters(catalog: dict) -> dict[str, object]:
    """Adopt all non-empty POST /filters result parameters for POST /open."""
    raw = catalog.get("result")
    if not isinstance(raw, dict):
        return {}
    fields = [item for item in (catalog.get("filters") or []) if isinstance(item, dict)]
    by_name: dict[str, dict] = {}
    for field in fields:
        for label in (field.get("name"), field.get("alias")):
            key = _norm(label)
            if key:
                by_name[key] = field
    picked: dict[str, object] = {}
    for key, value in raw.items():
        if value in (None, ""):
            continue
        field = by_name.get(_norm(key))
        if field is not None:
            name = str(field.get("name") or key).strip()
            if name:
                picked[name] = _value_for_open(field, value)
        else:
            name = str(key or "").strip()
            if name:
                picked[name] = _open_value(value)
    return picked


def open_payload(filters: dict[str, object]) -> dict[str, object]:
    return {"filters": dict(filters)}


def defaults_from_catalog(catalog: dict) -> dict[str, object]:
    """Each filter's current value, already the key GET /filters published."""
    picked: dict[str, object] = {}
    for field in catalog.get("filters") or []:
        if not isinstance(field, dict):
            continue
        name = str(field.get("name") or "").strip()
        if not name or field.get("value") in (None, ""):
            continue
        picked[name] = _value_for_open(field, field.get("value"))
    return picked


def phrase_names_choice(phrase: str, catalog: dict) -> bool:
    for field in catalog.get("filters") or []:
        if not isinstance(field, dict):
            continue
        for key, label in _choice_pairs(field):
            if _phrase_has(phrase, label) or _phrase_has(phrase, key):
                return True
    return False


def catalog_file() -> Path:
    raw = (os.environ.get("DASHBOARD_FILTERS_FILE") or "").strip()
    if raw:
        return Path(raw)
    from case3 import run_store

    return Path(run_store.ROOT) / "local" / "dashboard_filters.json"


def read_filter_catalog(path: Path | None = None) -> dict | None:
    """Full filter list dropped on the work machine. Missing file means ask /filters."""
    file = path or catalog_file()
    if not file.is_file():
        return None
    try:
        body = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DashboardRemoteError(
            f"не читается {file.name}: нужен JSON каталога фильтров",
            "filters",
        ) from exc
    if isinstance(body, list):
        body = {"filters": body}
    if not isinstance(body, dict) or not isinstance(body.get("filters"), list):
        raise DashboardRemoteError(
            f"{file.name}: нужен объект с полем filters",
            "filters",
        )
    return body


def fetch_dashboards(base: str, client) -> list[dict[str, str]]:
    """GET /dashboards. Each row is one .mrt in the service dashboards folder."""
    root = base.rstrip("/")
    response = client.get(f"{root}/dashboards")
    status = int(getattr(response, "status_code", 500) or 500)
    try:
        body = response.json()
    except Exception as exc:
        raise DashboardRemoteError("сервис не вернул список дашбордов", "dashboards") from exc
    rows = body.get("dashboards") if isinstance(body, dict) else None
    from_mrt_only = False
    if not isinstance(rows, list) and isinstance(body, dict) and isinstance(body.get("mrt"), list):
        from_mrt_only = True
        rows = [
            {"name": str(m).strip(), "title": Path(str(m).strip()).stem}
            for m in body["mrt"]
            if isinstance(m, str) and m.strip()
        ]
    if status >= 400 or not isinstance(rows, list):
        raise DashboardRemoteError("нет списка дашбордов", "dashboards")
    out: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = str(row.get("name") or row.get("mrt") or "").strip()
        if not name.lower().endswith(".mrt"):
            continue
        title = str(row.get("title") or Path(name).stem).strip() or Path(name).stem
        item = {"name": name, "title": title}
        preview = Path(str(row.get("preview") or "")).name
        same = Path(preview).stem == Path(name).stem
        if same and preview.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            item["preview"] = preview
        elif from_mrt_only and hasattr(client, "head"):
            try:
                probe = client.head(f"{root}/dashboards/preview?mrt={quote(name)}")
                if int(getattr(probe, "status_code", 500) or 500) == 200:
                    item["preview"] = f"{Path(name).stem}.png"
            except Exception:
                pass
        out.append(item)
    return out


def fetch_dashboard_preview(base: str, mrt: str, client) -> tuple[bytes, str]:
    """The picture stored beside this .mrt. Empty when that file has none."""
    name = Path(mrt or "").name
    if not name.lower().endswith(".mrt"):
        raise DashboardRemoteError("не выбрано имя дашборда", "preview")
    response = client.get(f"{base.rstrip('/')}/dashboards/preview?mrt={quote(name)}")
    status = int(getattr(response, "status_code", 500) or 500)
    content = getattr(response, "content", b"") or b""
    if status == 404 or not content:
        raise DashboardRemoteError("нет снимка", "preview")
    if status >= 400:
        raise DashboardRemoteError("сервис не отдал снимок", "preview")
    header = ""
    headers = getattr(response, "headers", None)
    if headers is not None:
        header = str(headers.get("content-type") or "")
    media = header.split(";", 1)[0].strip().lower() or "image/png"
    if media not in {"image/png", "image/jpeg", "image/webp"}:
        media = "image/png"
    return content, media


def _parse_json_dict(response) -> dict | None:
    if response is None:
        return None
    try:
        data = response.json()
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def fetch_filter_catalog(
    base: str,
    client,
    mrt: str = "",
    *,
    question: str = "",
) -> dict:
    """POST /filters (with fallback to {} / GET) to read filters or pick .mrt + fill result."""
    root = base.rstrip("/")
    name = (mrt or "").strip()
    q = (question or "").strip()
    response = None
    body: dict | None = None
    if hasattr(client, "post"):
        payload: dict[str, object] = {}
        if q:
            payload["question"] = q
        if name:
            payload["mrt"] = name
        response = client.post(
            f"{root}/filters",
            json=payload,
            headers={"Accept": "application/json"},
        )
        status = int(getattr(response, "status_code", 500) or 500)
        body = _parse_json_dict(response)
        # If question pick/LLM failed on viewer side (not stripped .mrt 422), retry catalog without question
        if q and status != 422 and (status >= 400 or body is None or body.get("error")):
            fallback_payload: dict[str, object] = {"mrt": name} if name else {}
            retry = client.post(
                f"{root}/filters",
                json=fallback_payload,
                headers={"Accept": "application/json"},
            )
            retry_status = int(getattr(retry, "status_code", 500) or 500)
            retry_body = _parse_json_dict(retry)
            if retry_status < 400 and isinstance(retry_body, dict) and isinstance(
                retry_body.get("filters"), list
            ):
                response = retry
                body = retry_body
                status = retry_status
        if status in {404, 405} or body is None or "filters" not in body:
            response = None
            body = None
    if response is None and hasattr(client, "get"):
        url = f"{root}/filters"
        if name:
            url = f"{url}?mrt={quote(name)}"
        response = client.get(url)
        body = _parse_json_dict(response)
    status = int(getattr(response, "status_code", 500) or 500)
    if body is None:
        raise DashboardRemoteError("сервис фильтров вернул не JSON", "filters")
    if (
        status >= 400
        or body.get("error")
        or not isinstance(body.get("filters"), list)
    ):
        detail = str(body.get("error") or "")
        raise DashboardRemoteError(detail or "нет списка фильтров", "filters")
    return body


def post_open_filters(
    base: str,
    filters: dict[str, object],
    client,
    mrt: str = "",
) -> str:
    """POST /open raises the filtered dashboard. open=0 keeps a second OS window shut."""
    root = base.rstrip("/")
    payload = open_payload(filters)
    name = (mrt or "").strip()
    if name:
        payload["mrt"] = name
    response = client.post(
        f"{root}/open?open=0",
        json=payload,
        headers={"Accept": "application/json"},
    )
    status = int(getattr(response, "status_code", 500) or 500)
    if status >= 400:
        raise DashboardRemoteError("сервис не принял фильтры", "open")
    opened = ""
    try:
        body = response.json()
    except Exception:
        body = None
    if isinstance(body, dict):
        rel = str(body.get("path") or "").strip()
        if rel.startswith("/"):
            pub = (os.environ.get("DASHBOARD_PUBLIC_URL") or "").strip().rstrip("/")
            opened = f"{pub or root}{rel}"
        else:
            opened = str(body.get("url") or "").strip()
    pub_fallback = (os.environ.get("DASHBOARD_PUBLIC_URL") or "").strip().rstrip("/") or root
    return opened or f"{pub_fallback}/open"


def open_named_dashboard(base: str, mrt: str, client) -> dict:
    """GET /filters for this file, then POST /open with those values and the mrt name."""
    name = (mrt or "").strip()
    if not name:
        raise DashboardRemoteError("не выбрано имя дашборда", "mrt")
    catalog = fetch_filter_catalog(base, client, name)
    opened_as = str(catalog.get("mrt") or name).strip() or name
    filters = defaults_from_catalog(catalog)
    viewer = post_open_filters(base, filters, client, mrt=opened_as)
    return {"mrt": opened_as, "filters": filters, "viewer": viewer}


def finish_dashboard_phrase(plan: dict, base: str, client) -> dict:
    """POST the filter body, then the iframe loads the /open page that POST raised."""
    if not plan.get("pull"):
        return plan
    filters = plan.get("filters")
    if not isinstance(filters, dict):
        return plan
    mrt = str(plan.get("mrt") or "").strip()
    if not filters and not mrt:
        return plan
    return {**plan, "viewer": post_open_filters(base, filters, client, mrt=mrt)}


_SAY_SYSTEM = (
    "Одной фразой по-русски скажи, что открываешь дашборд по этой просьбе. "
    "Назови период, если он есть в просьбе. Без JSON и без кавычек."
)


def spoken_line(raw: object) -> str:
    """One chat sentence. JSON and a blank model stay empty."""
    text = " ".join(str(raw or "").split())
    if not text or text[0] in "[{":
        return ""
    if len(text) > 320:
        text = text[:317].rstrip() + "…"
    return text


def _say_from_model(raw: str) -> str:
    return spoken_line(_json_object(raw).get("say"))


def _reply_from_filters(filters: dict[str, object], catalog: dict) -> str:
    """Last resort when the model returned no sentence."""
    fields = [item for item in (catalog.get("filters") or []) if isinstance(item, dict)]
    by_name = {str(field.get("name") or ""): field for field in fields}
    labels: list[str] = []
    for name, value in filters.items():
        field = by_name.get(str(name))
        if field is None:
            continue
        wanted = _norm(value)
        label = ""
        for key, choice in _choice_pairs(field):
            if wanted and wanted in {_norm(key), _norm(choice)}:
                label = choice or key
                break
        if label and _norm(label) not in {"все", "0000000", "cumulative"}:
            labels.append(label)
    if not labels:
        return "Открываю дашборд по текущим фильтрам."
    return "Открываю дашборд: " + ", ".join(labels[:4]) + "."


def plan_dashboard_phrase(text: str, catalog: dict, complete) -> dict:
    """Open with GET /filters values. A named choice overrides only that field.

    The chat line is the model's sentence, not a fixed opener.
    """
    if not might_ask_dashboard(text):
        return {"pull": False}
    base_filters = defaults_from_catalog(catalog)
    result_overlay = catalog_result_filters(catalog)
    overlay: dict[str, object] = {}
    say = ""
    named = phrase_names_choice(text, catalog)
    dash_obj = catalog.get("dashboard") if isinstance(catalog.get("dashboard"), dict) else {}
    picked_mrt = str(catalog.get("mrt") or dash_obj.get("mrt") or "").strip()
    if base_filters or named or result_overlay:
        from case3.prompts import load as load_prompt

        raw = str(
            complete(
                system=load_prompt("dashboard_filters"),
                user_text=(
                    text.strip()
                    + "\n\nКаталог:\n"
                    + json.dumps(catalog, ensure_ascii=False)
                ),
            )
            or ""
        )
        say = _say_from_model(raw)
        model_pull = bool(_json_object(raw).get("pull"))
        if not model_pull:
            if not ((base_filters or result_overlay) and _EXPLICIT_DASHBOARD_OPEN.search(text or "")):
                return {"pull": False}
        elif named:
            overlay = filters_from_model(catalog, text, raw)
    filters = {**base_filters, **overlay, **result_overlay}
    explicit_plain_open = bool(picked_mrt and _EXPLICIT_DASHBOARD_OPEN.search(text or ""))
    if not filters and not explicit_plain_open:
        return {
            "pull": False,
            "asked": True,
            "reply": "В фразе нет фильтра, который есть в дашборде. Назови период как в отчёте.",
        }
    if not say:
        say = spoken_line(
            complete(system=_SAY_SYSTEM, user_text=text.strip())
        )
    if not say:
        say = _reply_from_filters(filters, catalog)
    out: dict[str, object] = {
        "pull": True,
        "filters": filters,
        "viewer": f"{public_service_base()}/open",
        "reply": say,
    }
    if picked_mrt:
        out["mrt"] = picked_mrt
    return out


def fetch_export(base: str, name: str, client: httpx.Client) -> bytes | None:
    safe = _safe_name(name)
    if not safe:
        return None
    response = client.get(f"{base}/exports/{quote(safe)}")
    if response.status_code != 200 or not response.content:
        return None
    return bytes(response.content)
