"""
Extract effect estimates from every processed document of a project into
effect_estimates (roadmap N6 step 2), from the Docling output saved in R2.

    python scripts/extract_estimates.py --project-id <uuid> [--model anthropic/claude-haiku-5.5]
                                        [--only <doc_key>] [--skip-done]

Only rows whose cells were found verbatim in the table are stored, with their
embeddings. Rows of this source for a document are replaced on each run. The work is
done by src/extraction/store_estimates.py, which the Modal pipeline also calls.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from src.extraction.store_estimates import DEFAULT_MODEL, extract_and_store  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--only", help="one document key")
    ap.add_argument("--skip-done", action="store_true", help="skip documents that already have rows of this source")
    args = ap.parse_args()
    totals = asyncio.run(extract_and_store(
        args.project_id, doc_keys=[args.only] if args.only else None, model=args.model,
        skip_done=args.skip_done, log=lambda m: print(m, flush=True)))
    print(json.dumps(totals))


if __name__ == "__main__":
    main()
