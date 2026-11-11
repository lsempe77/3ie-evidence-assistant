"""
Detect findings a paper reports from OTHER studies.

Rule (11 Nov 2026): such findings are never cited, counted or used as evidence, because
nothing is known about the quality of the study behind them. A quote that carries an
author-year citation ("Banerjee et al. (2015) find...", "(Kidd and Bailey, 2017)") is
treated as secondhand and dropped wherever quotes ground a finding or a figure.
"""

from __future__ import annotations

import re

_YEAR = r"(?:19|20)\d{2}[a-z]?"
_NAME = r"[A-Z][A-Za-z'\-]+"
_CITATION = re.compile(
    rf"{_NAME}(?:\s+et\s+al\.?|\s+(?:and|&)\s+{_NAME})?\s*,?\s*\(\s*{_YEAR}"  # Banerjee et al. (2015
    rf"|\(\s*{_NAME}(?:\s+et\s+al\.?|\s+(?:and|&)\s+{_NAME})?\s*,\s*{_YEAR}"   # (Banerjee et al., 2015
)


def cites_other_study(text: str) -> bool:
    """True when the text carries an author-year citation, so it reports another study."""
    return bool(_CITATION.search(str(text or "")))
