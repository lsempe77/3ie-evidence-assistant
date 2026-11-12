"""
Keep the reader's supporting quote verbatim, so a citation always points at real text.

The reader sometimes reformats its quote: it reflows a table row, joins two sentences with an
ellipsis, or inserts its own words ("not shown"). That breaks citations and PDF highlighting,
which search the paper for the quote text. `verify_quote` returns the quote itself when it does
appear in the passages (ignoring whitespace and case), otherwise the passage sentence it matches
best, otherwise nothing, so a fabricated or heavily rewritten quote is never passed through.
"""

from __future__ import annotations

import re

_MIN_QUOTE_CHARS = 20
_MIN_OVERLAP = 0.6  # share of the quote's content words that a sentence must contain to stand in

_STOP = {
    "the", "and", "for", "are", "was", "were", "with", "that", "this", "from", "not", "but",
    "had", "has", "have", "they", "their", "than", "then", "also", "into", "over", "under",
    "between", "among", "which", "when", "where", "while", "there", "these", "those", "other",
}


def _flat(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _content_words(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in _STOP}


def _leading_words(text: str, count: int = 6) -> list:
    return [w for w in re.findall(r"[a-z0-9]+", _flat(text).lower())
            if len(w) > 2 and w not in _STOP][:count]


def _sentences(text: str) -> list:
    flat = _flat(text)
    return [s.strip() for s in re.split(r"(?<=[.;:])\s+(?=[A-Z0-9(])", flat) if len(s.strip()) >= _MIN_QUOTE_CHARS]


def verify_quote(quote: object, passages: str) -> str:
    """A verbatim span of `passages` that supports the quote, or "" if none is close enough.

    A replacement sentence must contain at least half of the quote's opening words, so a quote
    that was rewritten cannot be swapped for a different sentence that merely shares vocabulary.
    """
    text = _flat(quote)
    if len(text) < _MIN_QUOTE_CHARS:
        return ""
    if text.lower() in _flat(passages).lower():
        return text

    target = _content_words(text)
    if not target:
        return ""
    leading = _leading_words(text)
    needed = max(2, len(leading) // 2)
    best, best_score = "", 0.0
    for sentence in _sentences(passages):
        words = _content_words(sentence)
        if sum(1 for w in leading if w in words) < needed:
            continue
        score = len(target & words) / len(target)
        if score > best_score:
            best, best_score = sentence, score
    return best if best_score >= _MIN_OVERLAP else ""
