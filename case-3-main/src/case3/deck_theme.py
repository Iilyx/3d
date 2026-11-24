"""Deck theme packs — Liber presentation skins (deck-only; not report palettes)."""

from __future__ import annotations

from case3.color_util import norm_hex

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PACK_IDS = (
    "atelier",
    "board",
    "signal",
    "relay",
    "pastel",
    "ink",
    "voltage",
    "studio",
    "botanical",
)

_PACK_CACHE: dict[str, dict[str, Any]] | None = None


def _packs_dir() -> Path:
    return Path(__file__).resolve().parent / "deck_themes"


def _load_packs() -> dict[str, dict[str, Any]]:
    global _PACK_CACHE
    if _PACK_CACHE is not None:
        return _PACK_CACHE
    out: dict[str, dict[str, Any]] = {}
    root = _packs_dir()
    if root.is_dir():
        for path in sorted(root.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            pid = str(data.get("id") or path.stem).strip().lower()
            if pid:
                out[pid] = data
    _PACK_CACHE = out
    return out


def normalize_pack_id(raw: str | None) -> str:
    key = (raw or "atelier").strip().lower()
    if key in ("pastel", "split_pastel", "qbr"):
        key = "relay"
    if key in ("relay_ink", "investor_ink", "ice_blue", "northstar_ink"):
        key = "ink"
    if key in ("creative_voltage", "flowspace", "feedback"):
        key = "voltage"
    if key in ("workshop_studio", "facilitate"):
        key = "studio"
    if key in ("vesper", "dark_botanical", "verdara"):
        key = "botanical"
    if key in ("northstar", "board_northstar"):
        key = "board"
    packs = _load_packs()
    if key in packs:
        return key
    if key in PACK_IDS and key in packs:
        return key
    return "atelier" if "atelier" in packs else next(iter(packs), "atelier")


_DARK_PACK_IDS = frozenset({"botanical", "signal", "ink", "voltage"})


def is_dark_pack(style: dict[str, Any] | None) -> bool:
    """True for dark deck packs / motif atmosphere (HTML twin + native PPTX)."""
    if not isinstance(style, dict):
        return False
    if str(style.get("pack_id") or "") in _DARK_PACK_IDS:
        return True
    motif = style.get("motif") if isinstance(style.get("motif"), dict) else {}
    return str(motif.get("atmosphere") or "") == "dark"




@dataclass(frozen=True)
class ThemeTokens:
    pack_id: str
    label: str
    colors: dict[str, str]
    fonts: dict[str, str]
    chart_series: tuple[str, ...]
    table: dict[str, str]
    brand_mark: str
    motif: dict[str, Any]

    def css_vars(self) -> str:
        c = self.colors
        parts = [
            f"--deck-primary:{c.get('primary', '#2E4208')}",
            f"--deck-accent:{c.get('accent', '#4F6B14')}",
            f"--deck-ink:{c.get('ink', '#14161a')}",
            f"--deck-ink-2:{c.get('ink2', '#2c3028')}",
            f"--deck-muted:{c.get('muted', '#6A7160')}",
            f"--deck-paper:{c.get('paper', '#f0ede4')}",
            f"--deck-sheet:{c.get('sheet', '#fffcf7')}",
            f"--deck-rule:{c.get('rule', '#e6e2d8')}",
            f"--deck-foil:{c.get('foil', '#b8a36a')}",
            f"--deck-bg:{c.get('background', c.get('sheet', '#fffcf7'))}",
            f"--deck-text:{c.get('text', c.get('ink', '#14161a'))}",
            f"--deck-panel:{c.get('panel', c.get('paper', '#f0ede4'))}",
        ]
        split = self.motif.get("split")
        if isinstance(split, (int, float)) and not isinstance(split, bool):
            parts.append(f"--deck-split:{float(split)}")
        return ";".join(parts)

    def as_dict(self) -> dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "label": self.label,
            "colors": dict(self.colors),
            "fonts": dict(self.fonts),
            "chart_series": list(self.chart_series),
            "table": dict(self.table),
            "brand_mark": self.brand_mark,
            "motif": dict(self.motif),
        }


def resolve_deck_theme(
    pack_id: str | None = None,
    *,
    style_settings: dict[str, Any] | None = None,
) -> ThemeTokens:
    """Resolve a theme pack with optional UI overrides (hex / fonts)."""
    packs = _load_packs()
    pid = normalize_pack_id(pack_id)
    raw = packs.get(pid) or packs.get("atelier") or {}
    colors_in = dict(raw.get("colors") or {})
    fonts_in = dict(raw.get("fonts") or {})
    table_in = dict(raw.get("table") or {})
    series = [
        norm_hex(str(x), "#2E4208")
        for x in (raw.get("chart_series") or ["#2E4208", "#4F6B14"])
    ]

    settings = style_settings or {}
    # Map Julius-style UI keys onto pack colors.
    key_map = {
        "primary": "primary",
        "accent": "accent",
        "background": "background",
        "text": "text",
        "ink": "ink",
        "paper": "paper",
        "sheet": "sheet",
    }
    for ui_key, color_key in key_map.items():
        if ui_key in settings and settings[ui_key]:
            colors_in[color_key] = norm_hex(
                str(settings[ui_key]), colors_in.get(color_key, "#14161A")
            )
    # Keep background/sheet/text aliases in sync when overridden.
    if "background" in settings and settings["background"]:
        bg = norm_hex(str(settings["background"]), colors_in.get("sheet", "#FFFCF7"))
        colors_in["background"] = bg
        colors_in["sheet"] = bg
    if "text" in settings and settings["text"]:
        tx = norm_hex(str(settings["text"]), colors_in.get("ink", "#14161A"))
        colors_in["text"] = tx
        colors_in["ink"] = tx

    if settings.get("fontTitle"):
        fonts_in["title"] = str(settings["fontTitle"]).strip() or fonts_in.get(
            "title", "Calibri"
        )
    if settings.get("fontBody"):
        fonts_in["body"] = str(settings["fontBody"]).strip() or fonts_in.get(
            "body", "Calibri"
        )

    colors = {
        "primary": norm_hex(colors_in.get("primary"), "#2E4208"),
        "accent": norm_hex(colors_in.get("accent"), "#4F6B14"),
        "ink": norm_hex(colors_in.get("ink"), "#14161A"),
        "ink2": norm_hex(colors_in.get("ink2"), "#2C3028"),
        "muted": norm_hex(colors_in.get("muted"), "#6A7160"),
        "paper": norm_hex(colors_in.get("paper"), "#F0EDE4"),
        "sheet": norm_hex(colors_in.get("sheet"), "#FFFCF7"),
        "rule": norm_hex(colors_in.get("rule"), "#E6E2D8"),
        "foil": norm_hex(colors_in.get("foil"), "#B8A36A"),
        "background": norm_hex(
            colors_in.get("background") or colors_in.get("sheet"), "#FFFCF7"
        ),
        "text": norm_hex(colors_in.get("text") or colors_in.get("ink"), "#14161A"),
        "panel": norm_hex(
            colors_in.get("panel") or colors_in.get("paper"),
            colors_in.get("paper") or "#F0EDE4",
        ),
    }
    fonts = {
        # Title default Georgia (serif packs); body/fallback stay Calibri Office-safe.
        "title": str(fonts_in.get("title") or "Georgia"),
        "body": str(fonts_in.get("body") or "Calibri"),
        "fallback_pptx": str(fonts_in.get("fallback_pptx") or "Calibri"),
    }
    table = {
        "header_fill": norm_hex(table_in.get("header_fill"), colors["primary"]),
        "header_ink": norm_hex(table_in.get("header_ink"), colors["sheet"]),
        "grid": norm_hex(table_in.get("grid"), colors["rule"]),
    }
    if table_in.get("body_fill"):
        table["body_fill"] = norm_hex(str(table_in.get("body_fill")), colors["sheet"])
    motif_in = raw.get("motif") if isinstance(raw.get("motif"), dict) else {}
    motif: dict[str, Any] = {}
    # Split titles only when the pack motif declares them (relay/pastel).
    # Do not infer split from colors.panel — every craft pack has panel fills.
    if "split" in motif_in:
        try:
            motif["split"] = max(0.35, min(0.8, float(motif_in["split"])))
        except (TypeError, ValueError):
            motif["split"] = 0.55
    panels_raw = motif_in.get("panels")
    if isinstance(panels_raw, list) and panels_raw:
        motif["panels"] = [
            norm_hex(str(x), colors["panel"]) for x in panels_raw[:8]
        ]
    if motif_in.get("atmosphere"):
        motif["atmosphere"] = str(motif_in.get("atmosphere")).strip().lower()
    if "hero_bleed" in motif_in:
        motif["hero_bleed"] = bool(motif_in.get("hero_bleed"))
    if "foil_cards" in motif_in:
        motif["foil_cards"] = bool(motif_in.get("foil_cards"))
    if motif_in.get("card_fill"):
        motif["card_fill"] = norm_hex(str(motif_in.get("card_fill")), colors["paper"])
    return ThemeTokens(
        pack_id=pid,
        label=str(raw.get("label") or pid.title()),
        colors=colors,
        fonts=fonts,
        chart_series=tuple(series),
        table=table,
        brand_mark=str(raw.get("brand_mark") or ""),
        motif=motif,
    )


def list_public_packs() -> list[dict[str, Any]]:
    """UI catalog: id, label, swatches."""
    out: list[dict[str, Any]] = []
    packs = _load_packs()
    for pid in (
        "atelier",
        "board",
        "signal",
        "relay",
        "ink",
        "voltage",
        "studio",
        "botanical",
    ):
        raw = packs.get(pid)
        if not raw:
            continue
        tok = resolve_deck_theme(pid)
        out.append(
            {
                "id": pid,
                "label": tok.label,
                "swatches": [
                    tok.colors["primary"],
                    tok.colors["accent"],
                    tok.colors["background"],
                    tok.colors["text"],
                ],
            }
        )
    return out
