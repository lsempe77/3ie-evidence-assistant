"""
3ie Evidence Assistant - choose which passages an answer is written from.

The reranker scores passages, but a user asks for a number of *studies*. Taking the
top N passages lets one long paper fill every slot, so an answer can rest on two
studies in a collection of a hundred. This module keeps the best passages per study
and then the best studies.

Measured on 9 Nov 2026 (poverty graduation collection, 97 papers, one question):
Cohere rerank-v3.5 scores topped out at 0.66, and a 0.5 cut-off kept 6 studies,
0.3 kept 30 and 0.2 kept 42. Scores are not calibrated probabilities, so the
default floor is low and the study cap does the narrowing.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, TypeVar

DEFAULT_MIN_SCORE = 0.2
DEFAULT_PASSAGES_PER_STUDY = 3

T = TypeVar("T")


def select_by_study(
    results: Sequence[T],
    max_studies: int,
    passages_per_study: int = DEFAULT_PASSAGES_PER_STUDY,
    min_score: Optional[float] = None,
) -> List[T]:
    """
    Keep up to `passages_per_study` passages from each of the best `max_studies` studies.

    `results` must be sorted best first and expose `.score` and `.study_id`
    (as RetrievalResult does). Studies are ranked by their best passage. The output
    is sorted best first. Passages below `min_score` are dropped before anything else.
    """
    if max_studies <= 0 or passages_per_study <= 0:
        return []

    by_study: Dict[str, List[T]] = {}
    order: List[str] = []
    for r in results:
        if min_score is not None and getattr(r, "score", 0.0) < min_score:
            continue
        key = getattr(r, "study_id", None) or f"_unknown_{id(r)}"
        if key not in by_study:
            if len(order) >= max_studies:
                continue  # a new study, but the study cap is reached
            by_study[key] = []
            order.append(key)
        if len(by_study[key]) < passages_per_study:
            by_study[key].append(r)

    chosen = [r for key in order for r in by_study[key]]
    chosen.sort(key=lambda r: getattr(r, "score", 0.0), reverse=True)
    return chosen
