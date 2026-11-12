#!/usr/bin/env python
"""
Re-index documents from their parser content list, keeping only each document's own evidence.

Reads the content list from R2 (`rags/{project}/outputs/json/{doc_key}.json`), so it does not
need the markdown. The role filter (`src/ingestion/relevance_filter.py`) drops references,
boilerplate, background and other studies' findings before embedding. Each document's existing
chunks are replaced, so roles that are now dropped do not linger.

Usage:
    python scripts/reindex_role_filter.py --project <uuid> --doc-key <key> --dry-run
    python scripts/reindex_role_filter.py --project <uuid> --doc-key <key>
    python scripts/reindex_role_filter.py --project <uuid>
"""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).parent.parent / ".env")

logging.disable(logging.CRITICAL)  # this tool reports through print; the app logger crashes on cp1252

from src.config.settings import settings  # noqa: E402
from src.extraction.store_estimates import DEFAULT_MODEL  # noqa: E402
from src.ingestion.chunking import get_chunker  # noqa: E402
from src.ingestion.embeddings import EmbeddingGenerator  # noqa: E402
from src.ingestion.indexer import ChunkIndexer, doc_key_from  # noqa: E402
from src.ingestion.relevance_filter import documents_from_units, filtered_units  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=settings.default_project_id, help="Project id")
    parser.add_argument("--doc-key", default="", help="One document only (default: all)")
    parser.add_argument("--limit", type=int, default=0, help="Stop after this many documents")
    parser.add_argument("--dry-run", action="store_true", help="Label and chunk, do not write")
    args = parser.parse_args()

    if not args.project:
        sys.exit("Give --project or set DEFAULT_PROJECT_ID")

    indexer = ChunkIndexer(project_id=args.project)
    keys = [doc_key_from(args.doc_key)] if args.doc_key else sorted(indexer.doc_keys())
    if args.limit:
        keys = keys[:args.limit]
    print(f"{len(keys)} documents to re-index in {args.project}")

    chunker = get_chunker("hybrid")
    embedder = None if args.dry_run else EmbeddingGenerator()
    start = time.time()

    for i, key in enumerate(keys, 1):
        try:
            units = await filtered_units(args.project, key, DEFAULT_MODEL, settings.openrouter_api_key)
        except Exception as e:
            print(f"  [{i}/{len(keys)}] {key}: SKIPPED ({type(e).__name__}: {str(e)[:80]})")
            continue
        nodes = chunker.chunk(documents_from_units(units, key))
        print(f"  [{i}/{len(keys)}] {key}: units {len(units)} -> chunks {len(nodes)}")
        if args.dry_run:
            continue
        nodes = embedder.embed_nodes(nodes, show_progress=False)
        indexer.delete_by_document_id(key)
        indexer.index_nodes(nodes)

    print(f"done in {time.time() - start:.0f}s")


if __name__ == "__main__":
    asyncio.run(main())
