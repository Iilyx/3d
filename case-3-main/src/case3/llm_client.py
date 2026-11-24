"""OpenAI-compatible text client (same HTTP shape as bam-bam-bam)."""

from __future__ import annotations

import http.client
import io
import json
import logging
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("case3.llm")

_THINK = re.compile(r"<think>.*?</think>", re.S)
_BAG = threading.local()
_OPENER_LOCK = threading.Lock()
_OPENER_READY = False
_KEY_COOLDOWN_LOCK = threading.Lock()
_KEY_COOLDOWN_UNTIL: dict[str, float] = {}


def clear_key_cooldowns() -> None:
    """Reset shared process-wide API-key cooldowns (primarily for tests)."""
    with _KEY_COOLDOWN_LOCK:
        _KEY_COOLDOWN_UNTIL.clear()


def _mark_key_cooldown(key: str | None, seconds: float = 60.0) -> None:
    k = (key or "").strip()
    if not k:
        return
    until = time.monotonic() + max(1.0, float(seconds))
    with _KEY_COOLDOWN_LOCK:
        prev = _KEY_COOLDOWN_UNTIL.get(k, 0.0)
        if until > prev:
            _KEY_COOLDOWN_UNTIL[k] = until


def _pick_active_key_index(keys: list[str], start: int = 0) -> int:
    if not keys:
        return 0
    now = time.monotonic()
    with _KEY_COOLDOWN_LOCK:
        for offset in range(len(keys)):
            idx = (start + offset) % len(keys)
            if _KEY_COOLDOWN_UNTIL.get(keys[idx], 0.0) <= now:
                return idx
        return min(range(len(keys)), key=lambda i: _KEY_COOLDOWN_UNTIL.get(keys[i], 0.0))


def _remember_sock(sock: socket.socket | None) -> None:
    if sock is None:
        return
    bag = getattr(_BAG, "socks", None)
    if isinstance(bag, list):
        bag.append(sock)


class _AbortHTTPConnection(http.client.HTTPConnection):
    def connect(self) -> None:
        super().connect()
        _remember_sock(self.sock)


class _AbortHTTPSConnection(http.client.HTTPSConnection):
    def connect(self) -> None:
        super().connect()
        _remember_sock(self.sock)


class _AbortHTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req):  # type: ignore[no-untyped-def]
        return self.do_open(_AbortHTTPConnection, req)


class _AbortHTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):  # type: ignore[no-untyped-def]
        kwargs: dict[str, Any] = {"context": getattr(self, "_context", None)}
        if hasattr(self, "_check_hostname"):
            kwargs["check_hostname"] = self._check_hostname
        return self.do_open(_AbortHTTPSConnection, req, **kwargs)


def _ensure_abort_opener() -> None:
    global _OPENER_READY
    with _OPENER_LOCK:
        if _OPENER_READY:
            return
        urllib.request.install_opener(
            urllib.request.build_opener(_AbortHTTPHandler(), _AbortHTTPSHandler())
        )
        _OPENER_READY = True


def _abort_socks(socks: list[socket.socket]) -> None:
    for sock in socks:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass


def _urlopen_until_cancel(req, timeout_s: float, cancel_check, poll_s: float = 0.25):  # type: ignore[no-untyped-def]
    """Open the LLM request. ``cancel_check`` is polled while the socket blocks.

    The check's exception propagates within one poll. The worker thread then
    sees a shut-down socket instead of waiting out ``timeout_s``.
    """
    if cancel_check is None:
        return urllib.request.urlopen(req, timeout=timeout_s)
    _ensure_abort_opener()
    box: dict[str, Any] = {}
    socks: list[socket.socket] = []
    done = threading.Event()

    def _worker() -> None:
        _BAG.socks = socks
        try:
            box["resp"] = urllib.request.urlopen(req, timeout=timeout_s)
        except BaseException as exc:  # noqa: BLE001
            box["exc"] = exc
        finally:
            _BAG.socks = None
            done.set()

    threading.Thread(target=_worker, name="case3-llm-http", daemon=True).start()
    try:
        while not done.wait(poll_s):
            cancel_check()
    except BaseException:
        _abort_socks(socks)
        raise
    if "exc" in box:
        raise box["exc"]
    return box["resp"]


class LLMConfigError(ValueError):
    pass


class LLMError(RuntimeError):
    pass


def _env(*names: str) -> str | None:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def _number(name: str, default: Any, kind: Callable[[str], Any]) -> Any:
    raw = _env(name)
    try:
        return default if raw is None else kind(raw)
    except ValueError as exc:
        raise LLMConfigError(f"{name}={raw!r} is not a number") from exc


def _parse_api_keys(*sources: str | None) -> tuple[str, ...]:
    keys: list[str] = []
    for src in sources:
        if not src:
            continue
        for part in re.split(r"[,;\s]+", src.strip()):
            p = part.strip()
            if p and p not in keys:
                keys.append(p)
    return tuple(keys)


_REASONING = ("off", "low", "medium", "high")


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str | None = None
    api_keys: tuple[str, ...] = ()
    model: str | None = None
    timeout_s: float = 300.0
    max_retries: int = 2
    temperature: float = 0.2
    reasoning: str = "off"
    max_tokens: int = 16384

    def __post_init__(self) -> None:
        if not self.api_keys and self.api_key:
            parsed = _parse_api_keys(self.api_key)
            object.__setattr__(self, "api_keys", parsed)
        elif self.api_keys and not self.api_key:
            object.__setattr__(self, "api_key", self.api_keys[0])

    @property
    def endpoint(self) -> str:
        base = self.base_url.rstrip("/")
        base = base.removesuffix("/v1/chat/completions").removesuffix("/v1")
        return f"{base}/v1/chat/completions"

    @classmethod
    def from_env(cls) -> LLMConfig:
        base = _env("VISION_API_BASE_URL", "CASE3_API_BASE_URL", "INGEST_VISION_API_BASE_URL")
        if base is None:
            raise LLMConfigError(
                "Set VISION_API_BASE_URL in .env (e.g. http://192.168.x.x:8080)"
            )
        # Default off: thinking burns max_tokens and was the #1 truncation cause.
        reasoning = (_env("VISION_REASONING", "CASE3_REASONING") or "off").lower()
        if reasoning not in _REASONING:
            raise LLMConfigError(f"reasoning={reasoning!r}: expected {', '.join(_REASONING)}")
        primary = _env("VISION_API_KEY", "CASE3_API_KEY", "INGEST_VISION_API_KEY")
        fallbacks = _env(
            "VISION_FALLBACK_API_KEYS",
            "VISION_FALLBACK_API_KEY",
            "CASE3_FALLBACK_API_KEYS",
        )
        keys = _parse_api_keys(primary, fallbacks)
        return cls(
            base_url=base,
            api_key=keys[0] if keys else None,
            api_keys=keys,
            model=_env("VISION_MODEL", "CASE3_MODEL", "INGEST_VISION_MODEL"),
            timeout_s=_number("VISION_TIMEOUT_S", 300, float),
            max_retries=_number("VISION_MAX_RETRIES", 2, int),
            temperature=_number("VISION_TEMPERATURE", 0.2, float),
            reasoning=reasoning,
            max_tokens=max(1024, int(_number("VISION_MAX_TOKENS", 16384, int))),
        )


def _as_text(value: Any) -> str:
    if isinstance(value, list):
        return "".join(p.get("text", "") for p in value if isinstance(p, dict))
    return value if isinstance(value, str) else ""


def _after_think(raw: str) -> str:
    text = _THINK.sub("", raw)
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[1]
    return text.strip()


def _has_tex_signal(text: str) -> bool:
    t = text or ""
    low = t.lower()
    return (
        r"\documentclass" in t
        or "```latex" in low
        or "```tex" in low
        or r"\begin{document}" in t
        or "```json" in low
        or bool(re.search(r"\{\s*\"(?:charts|figures|diagrams|slides)\"\s*:", t))
    )


def _usable_assistant_text(raw: str) -> str:
    """Prefer post-think answer; if empty, keep raw when it still has LaTeX/JSON."""
    cleaned = _after_think(raw)
    if cleaned:
        return cleaned
    # Some Qwen builds put the whole answer inside <think>…</think>
    if _has_tex_signal(raw):
        return (raw or "").strip()
    return ""


def _content(data: Any) -> tuple[str, str]:
    """Return (assistant_text, finish_reason)."""
    finish = ""
    try:
        finish = str(data["choices"][0].get("finish_reason") or "")
    except (KeyError, IndexError, TypeError, AttributeError):
        pass
    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"unexpected response: {str(data)[:200]}") from exc
    if not isinstance(message, dict):
        raise LLMError(f"unexpected response: {str(data)[:200]}")

    content_blob = _as_text(message.get("content"))
    got = _usable_assistant_text(content_blob)
    if got:
        return got, finish

    blobs = [
        content_blob,
        _as_text(message.get("reasoning_content")),
        _as_text(message.get("reasoning")),
    ]
    # Last resort: only accept reasoning/unwrapped blobs that actually carry LaTeX or JSON output.
    for blob in blobs:
        if _has_tex_signal(blob):
            return blob.strip(), finish

    hint = (
        "Проверь VISION_API_BASE_URL / модель; VISION_REASONING=off; "
        "на :free при length→empty смени модель "
        "(например google/gemini-2.0-flash-exp:free) и перезапусти API"
    )
    raise LLMError(
        "empty response from Vision API "
        f"(finish_reason={finish!r}). {hint}"
    )


def _http_body(exc: urllib.error.HTTPError) -> str:
    cached = getattr(exc, "_case3_body_txt", None)
    if isinstance(cached, str):
        return cached
    try:
        text = " ".join(exc.read()[:300].decode("utf-8", "replace").split())
        try:
            setattr(exc, "_case3_body_txt", text)
        except Exception:
            pass
        return text
    except (OSError, http.client.HTTPException):
        return ""


def parse_openrouter_afford(body_txt: str) -> int | None:
    """Parse OpenRouter 402 «can only afford N» (not «requested up to N»)."""
    m = re.search(r"afford\s+(\d+)", body_txt or "", flags=re.I)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def credit_clamp_max_tokens(current: int, afford: int, *, margin: int = 64) -> int | None:
    """Return lower max_tokens if afford allows a useful shrink; else None."""
    target = max(1024, int(afford) - int(margin))
    if target < int(current):
        return target
    return None


def context_exceeded(body_txt: str) -> bool:
    """llama-server / local Qwen: prompt + max_tokens > n_ctx → HTTP 500."""
    low = (body_txt or "").lower()
    return "context size has been exceeded" in low or (
        "context" in low and "exceed" in low
    )


def context_shrink_max_tokens(current: int, *, floor: int = 1024) -> int | None:
    """Halve max_tokens for context-exceeded retry; stop at floor."""
    cur = int(current)
    if cur <= floor:
        return None
    nxt = max(floor, cur // 2)
    return nxt if nxt < cur else None


def build_body(
    *,
    system: str,
    user_text: str,
    model: str | None = None,
    temperature: float = 0.2,
    reasoning: str = "off",
    max_tokens: int = 16384,
    base_url: str | None = None,
    stream: bool = False,
    images: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    thinking: dict[str, Any] = (
        {"enable_thinking": False}
        if reasoning == "off"
        else {"enable_thinking": True, "resolved_reasoning_effort": reasoning}
    )
    user_content: str | list[dict[str, Any]] = user_text
    if images:
        parts: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
        for media_id, data_url in images:
            mid = str(media_id or "").strip()
            url = str(data_url or "").strip()
            if not mid or not url:
                continue
            parts.append({"type": "text", "text": f"Image id {mid}."})
            parts.append({"type": "image_url", "image_url": {"url": url}})
        if len(parts) > 1:
            user_content = parts
    body: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        "temperature": temperature,
        "max_tokens": max(16, int(max_tokens)),
    }
    if stream:
        body["stream"] = True
    host = (base_url or "").lower()
    openrouter = "openrouter.ai" in host
    model_l = (model or "").lower()
    if openrouter:
        # MiniMax Flash: thinking object is mandatory — low + exclude when off.
        # Other OpenRouter models (Nemotron, Ling, openrouter/free): disable reasoning
        # explicitly via enabled=False; if a routed model rejects it with HTTP 400
        # ("Reasoning is mandatory"), complete()/stream() strips it cleanly on retry.
        if reasoning == "off":
            if "minimax" in model_l:
                body["reasoning"] = {"effort": "low", "exclude": True}
            else:
                body["reasoning"] = {"enabled": False}
        else:
            effort = reasoning
            if effort not in ("low", "medium", "high", "xhigh", "max", "minimal"):
                effort = "low"
            body["reasoning"] = {"effort": effort, "exclude": False}
    else:
        # Local Qwen / vLLM-style thinking switch.
        body["chat_template_kwargs"] = thinking
    if model:
        body["model"] = model
    return body


class LLMClient:
    def __init__(self, config: LLMConfig, *, sleep: Callable[[float], None] = time.sleep) -> None:
        self.config = config
        self._sleep = sleep
        self.last_finish_reason: str = ""
        self._lock = threading.Lock()
        self.api_keys: list[str] = list(
            config.api_keys or ([config.api_key] if config.api_key else [])
        )
        self._key_index: int = _pick_active_key_index(self.api_keys, 0)
        self._tried_indices: set[int] = {self._key_index} if self.api_keys else set()

    @property
    def current_api_key(self) -> str | None:
        with self._lock:
            if not self.api_keys:
                return self.config.api_key
            return self.api_keys[self._key_index]

    def rotate_key(self, cooldown_s: float = 60.0) -> str | None:
        """Switch to next fallback key; marks failed key cooled down process-wide."""
        with self._lock:
            if not self.api_keys:
                return None
            failed_key = self.api_keys[self._key_index]
            _mark_key_cooldown(failed_key, cooldown_s)
            now = time.monotonic()
            with _KEY_COOLDOWN_LOCK:
                for offset in range(1, len(self.api_keys)):
                    idx = (self._key_index + offset) % len(self.api_keys)
                    if idx in self._tried_indices:
                        continue
                    if _KEY_COOLDOWN_UNTIL.get(self.api_keys[idx], 0.0) <= now:
                        self._key_index = idx
                        self._tried_indices.add(idx)
                        k = self.api_keys[idx]
                        masked = f"...{k[-6:]}" if len(k) >= 6 else "***"
                        log.warning(
                            "Switched LLM API key to fallback [%d/%d]: %s",
                            idx + 1,
                            len(self.api_keys),
                            masked,
                        )
                        return k
                for offset in range(1, len(self.api_keys)):
                    idx = (self._key_index + offset) % len(self.api_keys)
                    if idx not in self._tried_indices:
                        self._key_index = idx
                        self._tried_indices.add(idx)
                        k = self.api_keys[idx]
                        masked = f"...{k[-6:]}" if len(k) >= 6 else "***"
                        log.warning(
                            "Switched LLM API key to fallback [%d/%d]: %s",
                            idx + 1,
                            len(self.api_keys),
                            masked,
                        )
                        return k
        return None

    def _headers(self, key: str | None = None) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        k = key or self.current_api_key
        if k:
            headers["Authorization"] = f"Bearer {k}"
        if "openrouter.ai" in (self.config.base_url or "").lower():
            headers.setdefault("HTTP-Referer", "https://github.com/Borisserz/case-3")
            headers.setdefault("X-Title", "case-3")
        return headers

    def complete(
        self,
        *,
        system: str,
        user_text: str,
        reasoning: str | None = None,
        cancel_check: Callable[[], None] | None = None,
        images: list[tuple[str, str]] | None = None,
    ) -> str:
        r = reasoning or self.config.reasoning
        if r not in _REASONING:
            raise LLMConfigError(f"reasoning={r!r}: expected {', '.join(_REASONING)}")
        body = build_body(
            system=system,
            user_text=user_text,
            model=self.config.model,
            temperature=self.config.temperature,
            reasoning=r,
            max_tokens=self.config.max_tokens,
            base_url=self.config.base_url,
            images=images,
        )
        headers = self._headers()
        max_tokens = int(body.get("max_tokens") or self.config.max_tokens)
        error: Exception | None = None
        # Extra attempts when we shrink max_tokens (OpenRouter 402 / LAN context 500).
        credit_shrinks = 0
        context_shrinks = 0
        reasoning_rejected = False
        attempt = 0
        while attempt <= self.config.max_retries + credit_shrinks + context_shrinks:
            if cancel_check is not None:
                cancel_check()
            if attempt:
                self._sleep(float(min(attempt, 3)))
                if cancel_check is not None:
                    cancel_check()
            body["max_tokens"] = max_tokens
            data = json.dumps(body).encode("utf-8")
            log.info(
                "LLM POST %s model=%s bytes=%d timeout_s=%.0f max_tokens=%d",
                self.config.endpoint,
                self.config.model or "(default)",
                len(data),
                self.config.timeout_s,
                max_tokens,
            )
            req = urllib.request.Request(
                self.config.endpoint, data=data, headers=headers, method="POST"
            )
            try:
                with _urlopen_until_cancel(
                    req, self.config.timeout_s, cancel_check
                ) as resp:
                    text, finish = _content(json.loads(resp.read().decode("utf-8")))
                    self.last_finish_reason = finish
                    log.info(
                        "LLM OK chars=%d finish_reason=%s",
                        len(text),
                        finish or "-",
                    )
                    return text
            except LLMError as exc:
                error = exc
                msg_low = str(exc).lower()
                if (
                    "finish_reason='length'" in msg_low
                    or "empty response" in msg_low
                ) and attempt < self.config.max_retries:
                    nxt_tok = min(16384, max(max_tokens * 2, 6144))
                    log.warning(
                        "LLM empty on length — retrying max_tokens %d → %d",
                        max_tokens,
                        nxt_tok,
                    )
                    max_tokens = nxt_tok
                    if (
                        not reasoning_rejected
                        and "openrouter.ai" in (self.config.base_url or "").lower()
                        and r == "off"
                        and "reasoning" not in body
                    ):
                        body["reasoning"] = {"enabled": False}
                    attempt += 1
                    continue
                raise
            except urllib.error.HTTPError as exc:
                body_txt = _http_body(exc)
                if (
                    exc.code == 400
                    and "reasoning" in body
                    and "reasoning" in body_txt.lower()
                ):
                    low = body_txt.lower()
                    compact = {"effort": "low", "exclude": True}
                    if ("mandatory" in low or "required" in low) and body.get("reasoning") != compact:
                        log.warning(
                            "LLM 400 reasoning mandatory — retrying with compact reasoning: %s",
                            body_txt[:160],
                        )
                        body["reasoning"] = dict(compact)
                        continue
                    log.warning(
                        "LLM 400 reasoning param rejected — retrying without reasoning: %s",
                        body_txt[:160],
                    )
                    reasoning_rejected = True
                    body.pop("reasoning", None)
                    continue
                # Check for rate limit / quota / auth errors that warrant falling back to another key
                is_quota_or_auth_err = (
                    exc.code in (401, 403)
                    or (exc.code == 429)
                    or (exc.code == 402 and "afford" not in body_txt.lower())
                    or ("free-models-per-day" in body_txt.lower())
                    or ("rate-limited upstream" in body_txt.lower())
                )
                if is_quota_or_auth_err:
                    cd = 300.0 if exc.code in (401, 402, 403) else 60.0
                    next_key = self.rotate_key(cd)
                    if next_key is not None:
                        headers = self._headers(next_key)
                        log.warning(
                            "HTTP %d from %s (%s) — retrying with fallback API key",
                            exc.code,
                            self.config.endpoint,
                            body_txt[:100],
                        )
                        credit_shrinks = 0
                        attempt += 1
                        continue

                # Re-clamp every 402 where afford drops — do not stop after first shrink.
                if exc.code == 402 and "afford" in body_txt.lower():
                    afford = parse_openrouter_afford(body_txt)
                    nxt = (
                        credit_clamp_max_tokens(max_tokens, afford)
                        if afford is not None
                        else None
                    )
                    if nxt is not None and credit_shrinks < 4:
                        log.warning(
                            "LLM 402 credit clamp max_tokens %d → %d",
                            max_tokens,
                            nxt,
                        )
                        max_tokens = nxt
                        credit_shrinks += 1
                        attempt += 1
                        continue

                # If multimodal request returned 400 (model doesn't support images or bad image payload),
                # fall back to text-only so the pipeline continues gracefully.
                if exc.code == 400 and isinstance(body.get("messages", [{}])[1].get("content"), list):
                    log.warning(
                        "LLM 400 on multimodal request — falling back to text-only: %s",
                        body_txt[:200],
                    )
                    body["messages"][1]["content"] = user_text
                    attempt += 1
                    continue

                # Local Qwen: prompt + max_tokens > n_ctx → 500 context exceeded.
                if exc.code == 500 and context_exceeded(body_txt):
                    nxt = context_shrink_max_tokens(max_tokens)
                    if nxt is not None and context_shrinks < 4:
                        log.warning(
                            "LLM 500 context exceeded — max_tokens %d → %d",
                            max_tokens,
                            nxt,
                        )
                        max_tokens = nxt
                        context_shrinks += 1
                        attempt += 1
                        continue
                    raise LLMError(
                        "HTTP 500: контекст модели переполнен (prompt + max_tokens). "
                        "В .env поставь VISION_MAX_TOKENS=4096 (или меньше), "
                        "укороти Source, фото/графики=0, перезапусти api.cmd. "
                        f"Ответ сервера: {body_txt}"
                    ) from exc
                if exc.code == 429:
                    if "free-models-per-day" in body_txt or "rate-limited upstream" in body_txt:
                        keys_count = len(self.api_keys) or 1
                        raise LLMError(
                            f"HTTP 429: Исчерпан суточный лимит бесплатных запросов OpenRouter "
                            f"(все ключи исчерпаны: {keys_count}/{keys_count}). "
                            "Для продолжения: 1) пополните баланс на $1–5 на openrouter.ai (это снимет лимит и даст 1000 запросов/день), "
                            "2) создайте новый бесплатный API-ключ OpenRouter и добавьте в .env (можно через запятую в VISION_API_KEY), "
                            "либо 3) переключитесь на Google AI Studio (Gemini) или локальный Qwen."
                        ) from exc
                error = LLMError(
                    f"HTTP {exc.code} from {self.config.endpoint}: {body_txt}"
                )
                if exc.code < 500 and exc.code != 429:
                    raise error from exc
            except TimeoutError as exc:
                error = LLMError(f"timed out after {self.config.timeout_s:.0f}s")
                error.__cause__ = exc
            except (urllib.error.URLError, ConnectionError, http.client.HTTPException) as exc:
                if isinstance(getattr(exc, "reason", None), TimeoutError):
                    error = LLMError(f"timed out after {self.config.timeout_s:.0f}s")
                    error.__cause__ = exc
                else:
                    error = LLMError(f"{type(exc).__name__}: {exc}")
                    error.__cause__ = exc
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise LLMError(f"invalid JSON from {self.config.endpoint}") from exc
            attempt += 1
        raise error or LLMError("request failed")

    def stream(
        self,
        *,
        system: str,
        user_text: str,
        reasoning: str | None = None,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        """Yield content deltas from an OpenAI-compatible SSE chat completion."""
        r = reasoning or self.config.reasoning
        if r not in _REASONING:
            raise LLMConfigError(f"reasoning={r!r}: expected {', '.join(_REASONING)}")
        tok = int(max_tokens) if max_tokens is not None else self.config.max_tokens
        body = build_body(
            system=system,
            user_text=user_text,
            model=self.config.model,
            temperature=self.config.temperature,
            reasoning=r,
            max_tokens=tok,
            base_url=self.config.base_url,
            stream=True,
        )
        attempt = 0
        yielded = 0
        reasoning_rejected = False
        while attempt <= self.config.max_retries:
            if attempt:
                self._sleep(float(min(attempt, 3)))
            self.last_finish_reason = ""
            data = json.dumps(body).encode("utf-8")
            think_buf = ""
            in_think = False

            def _filter_chunk(chunk: str) -> str:
                nonlocal think_buf, in_think
                if not chunk:
                    return ""
                think_buf += chunk
                out: list[str] = []
                while think_buf:
                    if in_think:
                        end = think_buf.find("</think>")
                        if end < 0:
                            if len(think_buf) > 8:
                                think_buf = think_buf[-8:]
                            break
                        think_buf = think_buf[end + len("</think>") :]
                        in_think = False
                    else:
                        start = think_buf.find("<think>")
                        if start < 0:
                            hold = 0
                            for k in range(min(6, len(think_buf)), 0, -1):
                                if "<think>".startswith(think_buf[-k:]):
                                    hold = k
                                    break
                            emit_len = len(think_buf) - hold
                            if emit_len > 0:
                                out.append(think_buf[:emit_len])
                                think_buf = think_buf[emit_len:]
                            break
                        if start > 0:
                            out.append(think_buf[:start])
                        think_buf = think_buf[start + len("<think>") :]
                        in_think = True
                return "".join(out)

            headers = self._headers()
            req = urllib.request.Request(self.config.endpoint, data=data, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.config.timeout_s) as resp:
                    # Prefer line iteration for true streaming; fall back to full read.
                    line_iter: Any
                    if hasattr(resp, "__iter__") and not isinstance(resp, (bytes, str)):
                        line_iter = resp
                    else:
                        line_iter = io.BytesIO(resp.read())

                    for raw_line in line_iter:
                        if isinstance(raw_line, bytes):
                            line = raw_line.decode("utf-8", "replace")
                        else:
                            line = str(raw_line)
                        line = line.strip()
                        if not line or line.startswith(":"):
                            continue
                        if not line.startswith("data:"):
                            continue
                        payload = line[5:].strip()
                        if payload == "[DONE]":
                            break
                        try:
                            obj = json.loads(payload)
                        except json.JSONDecodeError:
                            continue
                        choices = obj.get("choices") or []
                        if not choices:
                            continue
                        delta = choices[0].get("delta") or {}
                        piece = _filter_chunk(_as_text(delta.get("content")))
                        if piece:
                            yielded += len(piece)
                            yield piece
                        fr = choices[0].get("finish_reason")
                        if fr:
                            self.last_finish_reason = str(fr)
                if not in_think and think_buf:
                    yielded += len(think_buf)
                    yield think_buf
                if yielded == 0:
                    if attempt < self.config.max_retries:
                        cur_tok = int(body.get("max_tokens") or tok)
                        nxt_tok = min(16384, max(cur_tok * 2, 6144))
                        log.warning(
                            "Stream empty (finish_reason=%r) — retrying max_tokens %d → %d",
                            self.last_finish_reason,
                            cur_tok,
                            nxt_tok,
                        )
                        body["max_tokens"] = nxt_tok
                        if (
                            not reasoning_rejected
                            and "openrouter.ai" in (self.config.base_url or "").lower()
                            and r == "off"
                            and "reasoning" not in body
                        ):
                            body["reasoning"] = {"enabled": False}
                        attempt += 1
                        continue
                    raise LLMError(
                        "empty stream response from "
                        f"{self.config.endpoint} (finish_reason={self.last_finish_reason!r})"
                    )
                return
            except urllib.error.HTTPError as exc:
                body_txt = _http_body(exc)
                if (
                    exc.code == 400
                    and "reasoning" in body
                    and "reasoning" in body_txt.lower()
                ):
                    low = body_txt.lower()
                    compact = {"effort": "low", "exclude": True}
                    if ("mandatory" in low or "required" in low) and body.get("reasoning") != compact:
                        log.warning(
                            "Stream LLM 400 reasoning mandatory — retrying with compact reasoning: %s",
                            body_txt[:160],
                        )
                        body["reasoning"] = dict(compact)
                        continue
                    log.warning(
                        "Stream LLM 400 reasoning rejected — retrying without reasoning: %s",
                        body_txt[:160],
                    )
                    reasoning_rejected = True
                    body.pop("reasoning", None)
                    continue
                if exc.code in (401, 403, 429) and self.rotate_key() is not None:
                    log.warning(
                        "Stream HTTP %d from %s (%s) — retrying with fallback API key",
                        exc.code,
                        self.config.endpoint,
                        body_txt[:100],
                    )
                    continue
                raise LLMError(
                    f"HTTP {exc.code} from {self.config.endpoint}: {body_txt}"
                ) from exc
            except TimeoutError as exc:
                if yielded > 0 or attempt >= self.config.max_retries:
                    raise LLMError(f"timed out after {self.config.timeout_s:.0f}s") from exc
                attempt += 1
            except (urllib.error.URLError, ConnectionError, http.client.HTTPException) as exc:
                if isinstance(getattr(exc, "reason", None), TimeoutError):
                    if yielded > 0 or attempt >= self.config.max_retries:
                        raise LLMError(f"timed out after {self.config.timeout_s:.0f}s") from exc
                    attempt += 1
                    continue
                if yielded > 0 or attempt >= self.config.max_retries:
                    raise LLMError(f"{type(exc).__name__}: {exc}") from exc
                attempt += 1
