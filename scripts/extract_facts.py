"""
Read every processed document of a project once and store its study facts (roadmap N6
step 3): programme, women as main recipients, cost per beneficiary, transfer value,
benefit-cost ratios and headline effects, each figure with a verbatim quote.

    python scripts/extract_facts.py --project-id <uuid> [--only <doc_key>] [--skip-done]

Then groups the collection's programme names into distinct programmes. About one US
cent per document with Haiku 5.5.
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

from src.extraction.store_estimates import DEFAULT_MODEL  # noqa: E402
from src.extraction.programme_groups import group_programmes  # noqa: E402
from src.extraction.store_facts import extract_and_store_facts  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id", required=True)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--only", help="one document key")
    ap.add_argument("--skip-done", action="store_true", help="skip documents that already have facts")
    args = ap.parse_args()
    totals = asyncio.run(extract_and_store_facts(
        args.project_id, doc_keys=[args.only] if args.only else None, model=args.model,
        skip_done=args.skip_done, log=lambda m: print(m, flush=True)))
    print(json.dumps(totals))
    # Name variants of one programme across documents become one programme
    print(json.dumps(asyncio.run(group_programmes(args.project_id, log=lambda m: print(m, flush=True)))))


if __name__ == "__main__":
    main()
