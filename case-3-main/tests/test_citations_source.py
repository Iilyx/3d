"""C2: footnotes/cites only when Source has explicit refs."""

from __future__ import annotations

from case3.citations import extract_source_refs, source_allows_citations
from case3.tex_preamble import strip_invented_cites


def test_no_refs_means_no_citations() -> None:
    src = "Выручка выросла на 12%. NPS 51."
    assert extract_source_refs(src) == []
    assert source_allows_citations(src) is False


def test_url_in_source_allows_citations() -> None:
    src = "См. отчёт https://example.com/q3 и методику."
    refs = extract_source_refs(src)
    assert any("example.com" in r for r in refs)
    assert source_allows_citations(src) is True


def test_see_phrase_allows() -> None:
    src = "Показатели по методике (см. Росстат, 2024)."
    assert source_allows_citations(src) is True


def test_strip_invented_cite_keys() -> None:
    tex = r"Рост~\cite{invented2024} и факт."
    out = strip_invented_cites(tex, allowed_keys=set())
    assert r"\cite{invented2024}" not in out
    assert "Рост" in out


def test_keep_footnote_with_url() -> None:
    tex = r"Данные\footnote{https://example.com/a}."
    out = strip_invented_cites(tex, allowed_keys=set())
    assert r"\footnote{https://example.com/a}" in out
