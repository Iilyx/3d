"""Safe post-LLM table rule cleanup (no invented cells/numbers)."""

from __future__ import annotations

import re

# Collapse repeated \\hline (LLM often doubles mid-table rules).
_MULTI_HLINE = re.compile(r"(?:\\hline\s*){2,}")
_TOPRULE_HLINE = re.compile(r"\\toprule\s*\\hline")
_HLINE_BOTTOMRULE = re.compile(r"\\hline\s*\\bottomrule")
_MIDRULE_HLINE = re.compile(r"\\midrule\s*\\hline")
_HLINE_MIDRULE = re.compile(r"\\hline\s*\\midrule")


def harden_table_rules(tex: str) -> str:
    """Strip redundant horizontal rules; keep booktabs semantics when present."""
    out = tex or ""
    out = _MULTI_HLINE.sub(r"\\hline\n", out)
    out = _TOPRULE_HLINE.sub(r"\\toprule\n", out)
    out = _HLINE_BOTTOMRULE.sub(r"\\bottomrule\n", out)
    out = _MIDRULE_HLINE.sub(r"\\midrule\n", out)
    out = _HLINE_MIDRULE.sub(r"\\midrule\n", out)
    return out
