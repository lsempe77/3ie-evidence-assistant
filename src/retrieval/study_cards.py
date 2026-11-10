"""
Study cards: one short, embedded text per document, for ranking whole studies
(roadmap N1, 10 November 2026).

Ranking passages one by one let a few long papers fill the candidate pool, so broad
questions reached 10 to 52 of the 86 included studies held in the graduation
collection. A card carries what decides whether a study is relevant: title, design,
countries, sectors, intervention, and the opening text (title page and abstract).

Build or refresh the cards of a collection:
    python -m src.retrieval.study_cards <project-id>
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.vectorstore.chunk_store import ChunkStore

OPENING_CHUNKS = 4          # chunks 0-3: title page, abstract, start of introduction
OPENING_CHARS = 1800
EMBED_BATCH = 96
EMBED_MODEL = "embed-v4.0"


def _cohere():
    import os

    import cohere

    key = os.environ.get("COHERE_API_KEY")  # set in Modal; the API reads it from settings
    if not key:
        from src.config.settings import settings

        key = settings.cohere_api_key
    return cohere.ClientV2(api_key=key)


def embed_documents(texts: List[str]) -> List[List[float]]:
    co = _cohere()
    out: List[List[float]] = []
    for i in range(0, len(texts), EMBED_BATCH):
        resp = co.embed(texts=texts[i:i + EMBED_BATCH], model=EMBED_MODEL,
                        input_type="search_document", embedding_types=["float"])
        out.extend(resp.embeddings.float_)
    return out


def embed_query(text: str) -> List[float]:
    """Query embedding with the Cohere SDK directly (the LlamaIndex wrapper costs ~27 s to import)."""
    resp = _cohere().embed(texts=[text], model=EMBED_MODEL, input_type="search_query", embedding_types=["float"])
    return resp.embeddings.float_[0]


def _joined(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value if v)
    return str(value or "")


def card_text(meta: Dict[str, Any], opening: str) -> str:
    """The text that represents one study when ranking studies for a question."""
    lines = [str(meta.get("title") or "Untitled")]
    for label, key in (("Authors", "authors"), ("Year", "year"), ("Design", "study_design"),
                       ("Countries", "countries"), ("Sectors", "sectors"),
                       ("Intervention", "intervention_type")):
        value = _joined(meta.get(key))
        if value and value != "unknown":
            lines.append(f"{label}: {value}")
    abstract = str(meta.get("abstract") or "").strip()
    body = abstract if len(abstract) > 200 else opening
    return "\n".join(lines) + "\n\n" + body.strip()[:OPENING_CHARS]


def build_study_cards(project_id: str, store: Optional[ChunkStore] = None) -> int:
    """Build (or rebuild) the cards of every document with chunks in a project."""
    store = store or ChunkStore()
    chunks = store.opening_chunks(project_id, max_index=OPENING_CHUNKS)
    by_doc: Dict[str, List[Dict[str, Any]]] = {}
    for c in chunks:
        by_doc.setdefault(c["doc_key"], []).append(c)

    docs = []
    for doc_key, rows in by_doc.items():
        rows.sort(key=lambda r: r["chunk_index"])
        meta = rows[0].get("metadata") or {}
        opening = "\n".join(r["content"] for r in rows)
        docs.append({"doc_key": doc_key, "document_id": rows[0].get("document_id"),
                     "card_text": card_text(meta, opening)})
    if not docs:
        return 0
    vectors = embed_documents([d["card_text"] for d in docs])
    now = datetime.now(timezone.utc).isoformat()
    for d, v in zip(docs, vectors):
        d["embedding"], d["updated_at"] = v, now
    return store.upsert_study_cards(project_id, docs)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m src.retrieval.study_cards <project-id>")
    print(f"{build_study_cards(sys.argv[1])} study cards written")
