"""
Drop the paragraphs that are not a document's own evidence before they are embedded.

Units are the parser's text, title and table items, the same `content_list` the usage study
labelled, so kept text stays verbatim with its page and can still be quoted and highlighted.
The keep and drop rule is `relevance_labels.filter_units`. Labels are cached per document so a
re-index is deterministic and the model is not asked twice for the same document.

Fail-open: if a labelling run mostly fails (every unit left unlabelled), the document's units
are all kept, so a model outage never empties a document from the index.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from llama_index.core.schema import Document

from src.extraction.relevance_labels import filter_units, label_units, units_from_content
from src.utils.logging import get_logger

logger = get_logger(__name__)

# Above this share of unlabelled units the labelling is treated as failed and nothing is dropped.
MAX_UNLABELLED_SHARE = 0.5
CACHE_DIR = Path(os.environ.get("RELEVANCE_LABEL_CACHE", ".cache/relevance_labels"))


def load_content_list(project_id: str, doc_key: str) -> List[Dict[str, Any]]:
    """The parser's content list for one document, from R2."""
    from src.extraction.store_estimates import _r2

    bucket = os.environ.get("R2_BUCKET_NAME", "devchat-pdfs")
    obj = _r2().get_object(Bucket=bucket, Key=f"rags/{project_id}/outputs/json/{doc_key}.json")
    return json.loads(obj["Body"].read()).get("content_list") or []


def _cache_path(cache_dir: Path, project_id: str, doc_key: str) -> Path:
    return cache_dir / f"{project_id}__{doc_key[:80]}.json"


async def filtered_units(
    project_id: str,
    doc_key: str,
    model: str,
    api_key: str,
    cache_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """This document's own evidence units, in document order, with the table rule applied."""
    units = units_from_content(load_content_list(project_id, doc_key))
    if not units:
        return []

    cache_dir = cache_dir or CACHE_DIR
    cache = _cache_path(cache_dir, project_id, doc_key)
    labels: Optional[List[str]] = None
    if cache.exists():
        try:
            cached = json.loads(cache.read_text(encoding="utf-8"))
            if isinstance(cached, list) and len(cached) == len(units):
                labels = [str(x) for x in cached]
        except (ValueError, OSError):
            labels = None

    if labels is None:
        labels = await label_units(units, model, api_key)
        if sum(1 for x in labels if x == "unlabelled") / len(labels) > MAX_UNLABELLED_SHARE:
            logger.warning(f"Relevance labels failed for {doc_key}; keeping all {len(units)} units")
            return units
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(labels, ensure_ascii=False), encoding="utf-8")

    kept = filter_units(units, labels)
    logger.info(f"{doc_key}: kept {len(kept)} of {len(units)} units")
    return kept


def documents_from_units(units: Sequence[Dict[str, Any]], doc_key: str) -> List[Document]:
    """One LlamaIndex Document per kept unit, carrying the page so highlighting still works."""
    return [
        Document(
            text=unit["text"],
            metadata={
                "doc_id": doc_key,
                "pdf_name": doc_key,
                "page_start": unit.get("page"),
                "page_end": unit.get("page"),
                "kind": unit.get("kind"),
            },
            doc_id=doc_key,
        )
        for unit in units
    ]
