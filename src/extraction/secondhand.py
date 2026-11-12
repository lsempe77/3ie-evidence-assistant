"""
Detect findings a paper reports from OTHER studies.

Rule (11 Nov 2026): such findings are never cited, counted or used as evidence, because
nothing is known about the quality of the study behind them. A quote that carries an
author-year citation ("Banerjee et al. (2015) find...", "(Kidd and Bailey, 2017)") is
treated as secondhand and dropped wherever quotes ground a finding or a figure. Prose
attributions without a year ("previous studies find", "the literature shows") are caught too,
by pairing a subject with a reporting verb in the next few words.
"""

from __future__ import annotations

import re

_YEAR = r"(?:19|20)\d{2}[a-z]?"
_NAME = r"[A-Z][A-Za-z'\-]+"
_CITATION = re.compile(
    rf"{_NAME}(?:\s+et\s+al\.?|\s+(?:and|&)\s+{_NAME})?\s*,?\s*\(\s*{_YEAR}"  # Banerjee et al. (2015
    rf"|\(\s*{_NAME}(?:\s+et\s+al\.?|\s+(?:and|&)\s+{_NAME})?\s*,\s*{_YEAR}"   # (Banerjee et al., 2015
)

# A subject that names other work, then a reporting verb soon after, so an own result that
# merely mentions prior work in passing ("consistent with prior research") is not caught.
_OTHER_WORK = re.compile(
    r"\b(?:previous|prior|earlier|other|existing|related|recent|several|many|some)\s+studies\b"
    r"|\bstudies\b|\bresearchers?\b"
    r"|\b(?:previous|prior|earlier|existing|recent|other)\s+(?:research|work|evidence)\b"
    r"|\bthe\s+literature\b|\bliterature\s+review\b|\bsystematic\s+reviews?\b"
    r"|\bmeta-?analys(?:is|es)\b"
    r"|\b(?:earlier|previous|prior|other|existing)\s+evaluations?\b",
    re.I,
)
_REPORTS = re.compile(
    r"\b(?:found|find|finds|shows?|shown|demonstrated|suggests?|suggested|reports?|reported"
    r"|concludes?|concluded|indicates?|indicated)\b",
    re.I,
)
_WINDOW = 60


def cites_other_study(text: str) -> bool:
    """True when the text reports another study: an author-year citation, or a prose attribution."""
    t = str(text or "")
    if _CITATION.search(t):
        return True
    for match in _OTHER_WORK.finditer(t):
        if _REPORTS.search(t[match.end():match.end() + _WINDOW]):
            return True
    return False
