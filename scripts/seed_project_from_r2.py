"""
Seed a project with PDFs that are already in R2 (for example the graduation corpus
from the old project), then let the normal pipeline process them.

For each PDF under --source-prefix it:
  1. copies the file inside R2 to rags/<project>/input-pdfs/<doc_id>.pdf (server-side copy),
  2. writes a `documents` row with status 'pending', exactly as an upload through the app would.
Then trigger processing from the app ("Process documents") or with:
    python -m modal run infrastructure/modal_mineru.py --action rag --project-id <project>

Processing runs MinerU on Modal (page-aware chunks, so citations keep their page numbers),
then contextual prefixes (OpenRouter) and embeddings (Cohere). Nothing here calls a model.

    python scripts/seed_project_from_r2.py --project-id <uuid> \
        --source-prefix rags/0816e8d3-ab23-417c-bf3f-e45531411c73/input-pdfs/ --dry-run
    python scripts/seed_project_from_r2.py --project-id <uuid> --source-prefix ... [--limit 5]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import boto3
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

from src.auth import get_supabase_client  # noqa: E402


def r2_client():
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or os.environ.get("R2_ACCOUNT_ID")
    endpoint = os.environ.get("R2_ENDPOINT_URL") or f"https://{account}.r2.cloudflarestorage.com"
    return boto3.client("s3", endpoint_url=endpoint, region_name="auto",
                        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--project-id", required=True, help="Target project (must already exist)")
    parser.add_argument("--source-prefix", required=True, help="R2 prefix holding the source PDFs")
    parser.add_argument("--limit", type=int, default=0, help="Seed at most this many PDFs (0 = all)")
    parser.add_argument("--dry-run", action="store_true", help="List what would be copied; change nothing")
    args = parser.parse_args()

    bucket = os.environ.get("R2_BUCKET_NAME", "devchat-pdfs")
    s3 = r2_client()
    supabase = get_supabase_client()

    project = supabase.table("rag_projects").select("id, name").eq("id", args.project_id).execute()
    if not project.data:
        print(f"Project {args.project_id} not found", file=sys.stderr)
        return 1

    sources = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=args.source_prefix):
        sources += [o for o in page.get("Contents", []) if o["Key"].lower().endswith(".pdf")]
    if args.limit:
        sources = sources[:args.limit]

    total_mb = sum(o["Size"] for o in sources) / 1e6
    print(f"{len(sources)} PDFs ({total_mb:.0f} MB) -> project '{project.data[0]['name']}'")
    if args.dry_run:
        for o in sources[:10]:
            print("  ", o["Key"].rsplit("/", 1)[-1])
        return 0

    for i, obj in enumerate(sources, 1):
        filename = obj["Key"].rsplit("/", 1)[-1]
        doc_id = filename.rsplit(".", 1)[0]  # keep the existing '<hash>_<name>' document key
        dest = f"rags/{args.project_id}/input-pdfs/{filename}"
        s3.copy_object(Bucket=bucket, Key=dest, CopySource={"Bucket": bucket, "Key": obj["Key"]})
        supabase.table("documents").upsert({
            "rag_project_id": args.project_id,
            "filename": doc_id,
            "original_filename": filename,
            "file_size_bytes": obj["Size"],
            "mime_type": "application/pdf",
            "status": "pending",
            "r2_input_key": dest,
            "import_source": "upload",
            "metadata": {"content_hash": doc_id.split("_", 1)[0], "seeded_from": obj["Key"]},
        }, on_conflict="filename,rag_project_id").execute()
        print(f"  [{i}/{len(sources)}] {filename}")

    print("Done. Trigger processing from the app or with modal run ... --action rag --project-id", args.project_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
