#!/usr/bin/env python3
"""
PDF Parser Comparison: MinerU vs MonkeyOCR
==========================================
Runs both parsers on a set of PDFs (via Modal) and compares their outputs
side-by-side on quality metrics.

Usage
-----
# Auto-select N PDFs from R2 input-pdfs and run comparison
python -m evaluation.compare_parsers --n 5

# Compare specific PDFs (by R2 key)
python -m evaluation.compare_parsers --pdfs "input-pdfs/121058356.pdf" "input-pdfs/121058359.pdf"

# Re-run MonkeyOCR even if output already exists
python -m evaluation.compare_parsers --n 5 --force

# Skip Modal submission (just compare already-processed outputs in R2)
python -m evaluation.compare_parsers --n 10 --read-only

# Save full comparison JSON
python -m evaluation.compare_parsers --n 5 --output evaluation/parser_comparison_results.json

Metrics compared
----------------
- Content length (chars)
- Table count (valid HTML/markdown tables)
- Heading count (# lines)
- Numeric density (decimal numbers per 1000 chars)
- SE density (parenthesised numbers per 1000 chars)
- Section coverage (Abstract, Results, Discussion, Conclusion)
- Processing time (seconds, from JSON metadata)
"""

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional

import boto3
from dotenv import load_dotenv

load_dotenv()


# Default RAG project that has 92 processed documents
DEFAULT_PROJECT_ID = "0816e8d3-ab23-417c-bf3f-e45531411c73"


# ============================================================================
# R2 helpers
# ============================================================================

def get_r2_client():
    account_id = os.environ["CLOUDFLARE_ACCOUNT_ID"]
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def get_bucket() -> str:
    return os.environ.get("R2_BUCKET_NAME", "devchat-pdfs")


def list_input_pdfs(s3, bucket: str, n: int, project_id: Optional[str] = None) -> list[str]:
    """List up to n PDF keys.

    If project_id is given, lists from rags/{project_id}/input-pdfs/.
    Otherwise falls back to global input-pdfs/.
    """
    prefix = (
        f"rags/{project_id}/input-pdfs/" if project_id
        else "input-pdfs/"
    )
    paginator = s3.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".pdf"):
                keys.append(obj["Key"])
                if len(keys) >= n:
                    return keys
    return keys


def mineru_json_key(pdf_key: str, project_id: Optional[str] = None) -> str:
    """Derive the R2 key for MinerU JSON output.

    - RAG project: rags/{project_id}/outputs/json/{doc_id}.json
    - Global:      outputs/json/{doc_id}.json
    """
    doc_id = Path(pdf_key).stem
    if project_id:
        return f"rags/{project_id}/outputs/json/{doc_id}.json"
    return f"outputs/json/{doc_id}.json"


def monkeyocr_json_key(pdf_key: str) -> str:
    """MonkeyOCR outputs always land in the global outputs/monkeyocr/ namespace."""
    doc_id = Path(pdf_key).stem
    return f"outputs/monkeyocr/json/{doc_id}.json"


def object_exists(s3, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def download_json(s3, bucket: str, key: str) -> Optional[dict]:
    try:
        resp = s3.get_object(Bucket=bucket, Key=key)
        return json.loads(resp["Body"].read().decode("utf-8"))
    except Exception:
        return None


# ============================================================================
# Metrics extraction
# ============================================================================

def count_tables(data: dict) -> int:
    """Count tables from structured list or content string."""
    # Prefer the tables field (list of table dicts)
    tables = data.get("tables", [])
    if isinstance(tables, list):
        return len(tables)
    # Fallback: count HTML/markdown tables in content
    content = data.get("content", "")
    html = len(re.findall(r"<table", content, re.IGNORECASE))
    md = len(re.findall(r"^\|.+\|", content, re.MULTILINE))
    return html or md


def count_headings(content: str) -> int:
    return len(re.findall(r"^#{1,6}\s+\S", content, re.MULTILINE))


def numeric_density(content: str) -> float:
    """Decimal numbers (potential coefficients) per 1000 chars."""
    if not content:
        return 0.0
    nums = re.findall(r"-?\d+\.\d{2,}", content)
    return round(len(nums) / max(len(content), 1) * 1000, 2)


def se_density(content: str) -> float:
    """Parenthesised numbers (potential SEs) per 1000 chars."""
    if not content:
        return 0.0
    ses = re.findall(r"\(\d+\.\d+\)", content)
    return round(len(ses) / max(len(content), 1) * 1000, 2)


SECTION_KEYWORDS = ["abstract", "introduction", "results", "discussion", "conclusion", "methodology", "methods"]


def section_coverage(content: str) -> dict[str, bool]:
    lower = content.lower()
    return {sec: bool(re.search(rf"\b{sec}\b", lower)) for sec in SECTION_KEYWORDS}


def section_score(content: str) -> int:
    """Count how many standard sections are present."""
    return sum(section_coverage(content).values())


@dataclass
class ParserMetrics:
    parser: str
    doc_id: str
    exists: bool = False
    content_chars: int = 0
    table_count: int = 0
    heading_count: int = 0
    numeric_density: float = 0.0
    se_density: float = 0.0
    section_score: int = 0
    sections_found: list[str] = field(default_factory=list)
    page_count: int = 0
    processing_time_s: Optional[float] = None
    title_detected: Optional[str] = None
    year_detected: Optional[int] = None
    error: Optional[str] = None

    def score(self) -> float:
        """Simple quality score (higher = better) for ranking."""
        if not self.exists:
            return 0.0
        return (
            min(self.content_chars / 1000, 100)   # up to 100 pts for content volume
            + self.table_count * 5                  # 5 pts per table
            + self.heading_count * 2                # 2 pts per heading
            + self.numeric_density * 10             # 10x numeric density
            + self.se_density * 15                  # bonus for SE extraction
            + self.section_score * 3                # 3 pts per section found
        )


def compute_metrics(parser: str, doc_id: str, data: Optional[dict]) -> ParserMetrics:
    if data is None:
        return ParserMetrics(parser=parser, doc_id=doc_id, exists=False)

    content = data.get("content", "") or ""
    sections = section_coverage(content)

    return ParserMetrics(
        parser=parser,
        doc_id=doc_id,
        exists=True,
        content_chars=len(content),
        table_count=count_tables(data),
        heading_count=count_headings(content),
        numeric_density=numeric_density(content),
        se_density=se_density(content),
        section_score=section_score(content),
        sections_found=[s for s, found in sections.items() if found],
        page_count=data.get("page_count", 0) or 0,
        processing_time_s=data.get("elapsed_seconds"),
        title_detected=data.get("title"),
        year_detected=data.get("year"),
    )


# ============================================================================
# Comparison display
# ============================================================================

def _bar(value: float, max_val: float, width: int = 20) -> str:
    if max_val == 0:
        return "░" * width
    filled = int(round(value / max_val * width))
    return "█" * filled + "░" * (width - filled)


def print_comparison(mineru: ParserMetrics, monkeyocr: ParserMetrics) -> None:
    mu_score = mineru.score()
    mo_score = monkeyocr.score()
    winner = "MinerU" if mu_score >= mo_score else "MonkeyOCR"

    print(f"\n{'='*70}")
    print(f"  📄  {mineru.doc_id}")
    print(f"{'='*70}")

    rows = [
        ("Exists",             str(mineru.exists),              str(monkeyocr.exists)),
        ("Content (chars)",    f"{mineru.content_chars:,}",     f"{monkeyocr.content_chars:,}"),
        ("Tables",             str(mineru.table_count),         str(monkeyocr.table_count)),
        ("Headings (#)",       str(mineru.heading_count),       str(monkeyocr.heading_count)),
        ("Page count",         str(mineru.page_count),          str(monkeyocr.page_count)),
        ("Numeric density",    f"{mineru.numeric_density:.2f}",  f"{monkeyocr.numeric_density:.2f}"),
        ("SE density",         f"{mineru.se_density:.2f}",       f"{monkeyocr.se_density:.2f}"),
        ("Section score",      f"{mineru.section_score}/7",      f"{monkeyocr.section_score}/7"),
        ("Sections found",     ", ".join(mineru.sections_found) or "—",
                               ", ".join(monkeyocr.sections_found) or "—"),
        ("Title",              (mineru.title_detected or "—")[:40],
                               (monkeyocr.title_detected or "—")[:40]),
        ("Year",               str(mineru.year_detected or "—"), str(monkeyocr.year_detected or "—")),
        ("Proc. time (s)",     f"{mineru.processing_time_s:.1f}" if mineru.processing_time_s else "—",
                               f"{monkeyocr.processing_time_s:.1f}" if monkeyocr.processing_time_s else "—"),
        ("Quality score",      f"{mu_score:.1f}",               f"{mo_score:.1f}"),
    ]

    col_label = 22
    col_val   = 24

    header = f"  {'Metric':<{col_label}} {'MinerU':^{col_val}} {'MonkeyOCR':^{col_val}}"
    print(header)
    print(f"  {'-'*(col_label + col_val*2 + 2)}")
    for label, mu_val, mo_val in rows:
        mu_marker = " ✓" if label == "Quality score" and winner == "MinerU" else ""
        mo_marker = " ✓" if label == "Quality score" and winner == "MonkeyOCR" else ""
        print(f"  {label:<{col_label}} {mu_val+mu_marker:<{col_val}} {mo_val+mo_marker:<{col_val}}")

    print(f"\n  🏆  Winner: {winner}  (MinerU={mu_score:.1f}, MonkeyOCR={mo_score:.1f})")


def print_summary(results: list[dict]) -> None:
    docs = [r for r in results if r["mineru"].exists or r["monkeyocr"].exists]
    if not docs:
        print("\nNo results to summarise.")
        return

    mu_wins = sum(1 for r in docs if r["mineru"].score() >= r["monkeyocr"].score())
    mo_wins = len(docs) - mu_wins

    def mean(values):
        v = [x for x in values if x is not None]
        return sum(v) / len(v) if v else None

    mu_chars    = mean([r["mineru"].content_chars for r in docs if r["mineru"].exists])
    mo_chars    = mean([r["monkeyocr"].content_chars for r in docs if r["monkeyocr"].exists])
    mu_tables   = mean([r["mineru"].table_count for r in docs if r["mineru"].exists])
    mo_tables   = mean([r["monkeyocr"].table_count for r in docs if r["monkeyocr"].exists])
    mu_numd     = mean([r["mineru"].numeric_density for r in docs if r["mineru"].exists])
    mo_numd     = mean([r["monkeyocr"].numeric_density for r in docs if r["monkeyocr"].exists])
    mu_secs     = mean([r["mineru"].section_score for r in docs if r["mineru"].exists])
    mo_secs     = mean([r["monkeyocr"].section_score for r in docs if r["monkeyocr"].exists])

    print(f"\n{'='*70}")
    print(f"  SUMMARY ({len(docs)} PDFs)")
    print(f"{'='*70}")
    print(f"  Wins:             MinerU {mu_wins}  vs  MonkeyOCR {mo_wins}")
    print(f"  Avg content:      MinerU {mu_chars:,.0f} chars"
          f"  vs  MonkeyOCR {mo_chars:,.0f} chars" if mu_chars and mo_chars else "")
    print(f"  Avg tables:       MinerU {mu_tables:.1f}  vs  MonkeyOCR {mo_tables:.1f}"
          if mu_tables is not None and mo_tables is not None else "")
    print(f"  Avg numeric dens: MinerU {mu_numd:.2f}  vs  MonkeyOCR {mo_numd:.2f}"
          if mu_numd is not None and mo_numd is not None else "")
    print(f"  Avg section cov:  MinerU {mu_secs:.1f}/7  vs  MonkeyOCR {mo_secs:.1f}/7"
          if mu_secs is not None and mo_secs is not None else "")
    print()


# ============================================================================
# Modal submission
# ============================================================================

def submit_monkeyocr_jobs(pdf_keys: list[str], force: bool) -> dict[str, dict]:
    """
    Submit MonkeyOCR jobs on Modal and wait for results.
    Returns {pdf_key: result_dict}.
    """
    try:
        import modal
    except ImportError:
        print("  ⚠️  modal not installed — skipping MonkeyOCR submission")
        return {}

    print(f"\n🚀  Submitting {len(pdf_keys)} PDF(s) to Modal (MonkeyOCR)...")

    try:
        # Import the deployed function (Modal 1.x uses from_name instead of lookup)
        process_fn = modal.Function.from_name("devchat-mineru", "process_pdf_monkeyocr")
    except Exception as e:
        print(f"  ⚠️  Could not reach Modal function: {e}")
        print("     Make sure you have run:  modal deploy infrastructure/modal_mineru.py")
        return {}

    # Spawn all jobs in parallel then gather
    calls = {}
    for key in pdf_keys:
        try:
            call = process_fn.spawn(
                pdf_key=key,
                force_reprocess=force,
                index_to_qdrant=False,
            )
            calls[key] = call
            print(f"  ↑  Spawned: {key}")
        except Exception as e:
            print(f"  ⚠️  Failed to spawn {key}: {e}")

    results = {}
    for key, call in calls.items():
        doc_id = Path(key).stem
        print(f"  ⌛  Waiting for {doc_id}...", end="", flush=True)
        try:
            result = call.get(timeout=2400)
            print(f" ✓  ({result.get('elapsed_seconds', 0):.0f}s)")
            results[key] = result
        except Exception as e:
            print(f" ✗  {e}")
            results[key] = {"success": False, "error": str(e)}

    return results


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Compare MinerU vs MonkeyOCR on a set of PDFs")
    parser.add_argument("--pdfs",       nargs="+", metavar="KEY",
                        help="R2 PDF keys (e.g. rags/{project_id}/input-pdfs/paper.pdf)")
    parser.add_argument("--n",           type=int, default=5,
                        help="Auto-select N PDFs (default 5)")
    parser.add_argument("--project-id",  default=DEFAULT_PROJECT_ID, metavar="UUID",
                        help=f"RAG project ID (default: {DEFAULT_PROJECT_ID[:8]}...)")
    parser.add_argument("--global",      dest="use_global", action="store_true",
                        help="Use global input-pdfs/ instead of a RAG project")
    parser.add_argument("--force",       action="store_true",
                        help="Force MonkeyOCR re-processing even if output exists")
    parser.add_argument("--read-only",   action="store_true",
                        help="Skip Modal submission; only compare existing R2 outputs")
    parser.add_argument("--output",      metavar="PATH",
                        default="evaluation/parser_comparison_results.json",
                        help="Save full results JSON to this path")
    args = parser.parse_args()

    s3     = get_r2_client()
    bucket = get_bucket()

    # ----------------------------------------------------------------
    # 1. Resolve PDF list
    # ----------------------------------------------------------------
    project_id = None if args.use_global else args.project_id

    if args.pdfs:
        pdf_keys = args.pdfs
        print(f"Using {len(pdf_keys)} user-specified PDF(s)")
    else:
        source_desc = (
            f"global input-pdfs/" if project_id is None
            else f"RAG project {project_id[:8]}..."
        )
        print(f"Auto-selecting {args.n} PDFs from {source_desc}...")
        pdf_keys = list_input_pdfs(s3, bucket, args.n, project_id)
        if not pdf_keys:
            print("\u274c  No PDFs found in R2")
            sys.exit(1)
        print(f"Found: {[Path(k).name for k in pdf_keys]}")

    # ----------------------------------------------------------------
    # 2. Submit MonkeyOCR jobs (unless read-only)
    # ----------------------------------------------------------------
    if not args.read_only:
        # Only submit PDFs that don't already have MonkeyOCR output
        needs_processing = []
        for key in pdf_keys:
            doc_id  = Path(key).stem
            mo_key  = f"outputs/monkeyocr/json/{doc_id}.json"
            if args.force or not object_exists(s3, bucket, mo_key):
                needs_processing.append(key)
            else:
                print(f"  ✓  MonkeyOCR output already exists: {doc_id}")

        if needs_processing:
            submit_monkeyocr_jobs(needs_processing, force=args.force)
        else:
            print("  All MonkeyOCR outputs already in R2 — skipping submission")
    else:
        print("Read-only mode: skipping Modal submission")

    # ----------------------------------------------------------------
    # 3. Download & compare
    # ----------------------------------------------------------------
    print(f"\n📥  Downloading outputs from R2...")
    all_results = []

    for pdf_key in pdf_keys:
        doc_id = Path(pdf_key).stem

        mu_json_key = mineru_json_key(pdf_key, project_id)
        mo_json_key = monkeyocr_json_key(pdf_key)

        mu_data = download_json(s3, bucket, mu_json_key)
        mo_data = download_json(s3, bucket, mo_json_key)

        if mu_data is None:
            print(f"  ⚠️  MinerU output not found for {doc_id}  ({mu_json_key})")
        if mo_data is None:
            print(f"  ⚠️  MonkeyOCR output not found for {doc_id}  ({mo_json_key})")

        mu_metrics = compute_metrics("mineru",    doc_id, mu_data)
        mo_metrics = compute_metrics("monkeyocr", doc_id, mo_data)

        print_comparison(mu_metrics, mo_metrics)

        all_results.append({
            "doc_id":    doc_id,
            "pdf_key":   pdf_key,
            "mineru":    mu_metrics,
            "monkeyocr": mo_metrics,
            "winner":    "mineru" if mu_metrics.score() >= mo_metrics.score() else "monkeyocr",
        })

    # ----------------------------------------------------------------
    # 4. Summary
    # ----------------------------------------------------------------
    print_summary(all_results)

    # ----------------------------------------------------------------
    # 5. Save JSON
    # ----------------------------------------------------------------
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    serialisable = []
    for r in all_results:
        serialisable.append({
            "doc_id":    r["doc_id"],
            "pdf_key":   r["pdf_key"],
            "winner":    r["winner"],
            "mineru":    asdict(r["mineru"]),
            "monkeyocr": asdict(r["monkeyocr"]),
        })

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(serialisable, f, indent=2, ensure_ascii=False)

    print(f"✅  Full results saved to {out_path}")


if __name__ == "__main__":
    main()
