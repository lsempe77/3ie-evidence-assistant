"""
Re-derive document metadata from the parser output already saved in R2, without
parsing or embedding again, and write it to the documents row and every chunk.

Used after a fix to metadata resolution (infrastructure/modal_lib/metadata.py).
Run with:
    modal run infrastructure/modal_mineru.py --action refresh-metadata --project-id <uuid>
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Optional

from .config import app, docling_image, r2_secret, supabase_secret, openrouter_secret
from .chunks import get_store
from .metadata import build_design_excerpt, classify_study_design_llm, resolve_metadata
from .utils import get_bucket_name, get_r2_client

# Bibliographic fields are taken from the new resolution unless a person set them.
BIBLIOGRAPHIC_FIELDS = (
    "title", "authors", "year", "doi", "journal", "publisher", "volume", "issue", "pages",
    "item_type", "cited_by_count", "is_open_access", "sdgs", "keywords",
    "metadata_source", "metadata_confidence", "needs_review",
)
DOMAIN_FIELDS = ("countries", "author_countries", "sectors", "study_type", "intervention_type")
PROTECTED_SOURCES = ("user", "bibliography_import")
RECLASSIFY_BELOW = 0.5  # study design confidence under which the design is classified again


def _supabase():
    from supabase import create_client

    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


@app.function(
    image=docling_image,
    secrets=[r2_secret, supabase_secret, openrouter_secret],
    timeout=600,
    retries=1,
    max_containers=8,
)
def refresh_document_metadata(project_id: str, document_id: str, reclassify: str = "weak") -> dict:
    """Refresh one document. `reclassify`: "weak" (unknown or low confidence), "all" or "none"."""
    client = _supabase()
    row = (client.table("documents").select("id, filename, metadata")
           .eq("id", document_id).single().execute().data)
    doc_id = row["filename"]
    old = row.get("metadata") or {}

    key = f"rags/{project_id}/outputs/json/{doc_id}.json"
    try:
        saved = json.loads(get_r2_client().get_object(Bucket=get_bucket_name(), Key=key)["Body"].read())
    except Exception as e:
        return {"doc_id": doc_id, "error": f"no saved parser output at {key}: {e}"}
    content = saved.get("content") or ""

    new = resolve_metadata(
        content=content,
        title=saved.get("title"),
        authors=saved.get("authors"),
        year=saved.get("year"),
        pdf_filename=old.get("pdf_name") or doc_id,
    )

    fields = DOMAIN_FIELDS if old.get("metadata_source") in PROTECTED_SOURCES else DOMAIN_FIELDS + BIBLIOGRAPHIC_FIELDS
    patch = {f: new.get(f) for f in fields if f in new}

    old_design = old.get("study_design") or "unknown"
    weak = old_design == "unknown" or float(old.get("study_design_confidence") or 0) < RECLASSIFY_BELOW
    if reclassify == "all" or (reclassify == "weak" and weak):
        design = asyncio.run(classify_study_design_llm(
            title=patch.get("title") or old.get("title") or "",
            abstract_or_content=build_design_excerpt(content, new.get("abstract") or saved.get("abstract")),
            api_key=os.environ.get("OPENROUTER_API_KEY", ""),
        ))
        if design.get("study_design") and not str(design.get("study_design_reasoning", "")).startswith("Classification error"):
            patch.update(design)
    patch["metadata_refreshed_at"] = datetime.now().isoformat()

    client.table("documents").update({
        "metadata": {**old, **patch, **({"abstract": new["abstract"]} if new.get("abstract") else {})},
        "updated_at": datetime.now().isoformat(),
    }).eq("id", document_id).execute()
    chunks_updated = get_store().merge_metadata(project_id, doc_id, patch)

    return {
        "doc_id": doc_id,
        "old_title": old.get("title"),
        "new_title": patch.get("title", old.get("title")),
        "source": patch.get("metadata_source", old.get("metadata_source")),
        "old_countries": old.get("countries"),
        "countries": patch.get("countries"),
        "old_design": old_design,
        "design": patch.get("study_design", old_design),
        "chunks_updated": chunks_updated,
    }


@app.function(image=docling_image, secrets=[supabase_secret], timeout=3600)
def refresh_project_metadata(project_id: str, reclassify: str = "weak",
                             only_doc: Optional[str] = None) -> list:
    """Refresh every completed document of a project (or one, by filename)."""
    query = (_supabase().table("documents").select("id, filename")
             .eq("rag_project_id", project_id).eq("status", "completed"))
    if only_doc:
        query = query.eq("filename", only_doc)
    docs = query.execute().data or []
    print(f"Refreshing metadata for {len(docs)} documents (reclassify={reclassify})")
    results = []
    for result in refresh_document_metadata.starmap(
        [(project_id, d["id"], reclassify) for d in docs], return_exceptions=True
    ):
        results.append(result if isinstance(result, dict) else {"error": str(result)})
    return results
