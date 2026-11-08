"""
Parser pilot: Docling against the existing MinerU output on the same papers.

Method follows the TVET parser bake-off (Desktop/TVET/pipeline/bakeoff_metrics.py,
October 2026): with no hand-built gold set, numeric fidelity is scored against each
PDF's own text layer, read with PyMuPDF. For a born-digital PDF that text layer is the
publisher's content, so the numbers in it are a fair proxy for "the numbers in the
document". It contains page numbers and years that a parser may rightly drop, so
absolute recall understates every parser; the comparison between parsers is what counts.

Metrics per paper and parser:
  decimal recall     share of decimal numbers in the text layer found in the output (multiset)
  any-number recall  the same for all numbers
  text ratio         output characters / text-layer characters
  tables             tables the parser reported
  seconds per page   Docling only (the MinerU output was produced in January 2026)

Docling runs on Modal (parse_pdf_docling, CPU). MinerU output is read from R2.

    python evaluation/parser_pilot.py --n 5
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import tempfile
from collections import Counter
from datetime import date
from pathlib import Path

import boto3
import fitz  # PyMuPDF
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

OLD_PROJECT = "rags/0816e8d3-ab23-417c-bf3f-e45531411c73"
MODAL_APP = "evidence-assistant-mineru"

NUMBER = re.compile(r"(?<![\w.])[-−–]?\d+(?:,\d{3})*(?:\.\d+)?(?![\w])")


def normalise(token: str) -> str:
    return token.replace("−", "-").replace("–", "-").replace(",", "")


def numbers(text: str) -> tuple[Counter, Counter]:
    tokens = [normalise(t) for t in NUMBER.findall(text)]
    return Counter(t for t in tokens if "." in t), Counter(tokens)


def recall(reference: Counter, candidate: Counter) -> float:
    total = sum(reference.values())
    return sum(min(n, candidate[k]) for k, n in reference.items()) / total if total else float("nan")


def r2():
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID") or os.environ.get("R2_ACCOUNT_ID")
    endpoint = os.environ.get("R2_ENDPOINT_URL") or f"https://{account}.r2.cloudflarestorage.com"
    return boto3.client("s3", endpoint_url=endpoint, region_name="auto",
                        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
                        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"])


def pick(objects: list, n: int) -> list:
    """Spread the sample across file sizes: small, medium and large papers."""
    objects = sorted(objects, key=lambda o: o["Size"])
    if n >= len(objects):
        return objects
    step = (len(objects) - 1) / (n - 1) if n > 1 else 0
    return [objects[round(i * step)] for i in range(n)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--source-prefix", default=f"{OLD_PROJECT}/input-pdfs/")
    ap.add_argument("--mineru-md-prefix", default=f"{OLD_PROJECT}/outputs/md/")
    ap.add_argument("--out", default=str(ROOT / "evaluation" / "results" / f"parser_pilot_{date.today()}"))
    args = ap.parse_args()

    import modal

    bucket = os.environ.get("R2_BUCKET_NAME", "devchat-pdfs")
    s3 = r2()
    pdfs = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=args.source_prefix):
        pdfs += [o for o in page.get("Contents", []) if o["Key"].lower().endswith(".pdf")]
    sample = pick(pdfs, args.n)
    keys = [o["Key"] for o in sample]
    print(f"Sample: {len(keys)} PDFs ({sum(o['Size'] for o in sample) / 1e6:.1f} MB)")

    parse = modal.Function.from_name(MODAL_APP, "parse_pdf_docling")
    docling_results = dict(zip(keys, parse.map(keys, return_exceptions=True)))

    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for key in keys:
            doc_id = Path(key).stem
            local = Path(tmp) / "doc.pdf"
            s3.download_file(bucket, key, str(local))
            with fitz.open(local) as pdf:
                pages = pdf.page_count
                layer = "\n".join(p.get_text() for p in pdf)
            ref_dec, ref_all = numbers(layer)

            outputs = {}
            try:
                outputs["mineru"] = s3.get_object(Bucket=bucket, Key=f"{args.mineru_md_prefix}{doc_id}.md")["Body"].read().decode("utf-8")
            except Exception:
                outputs["mineru"] = None
            d = docling_results[key]
            outputs["docling"] = d.get("content") if isinstance(d, dict) and d.get("success") else None

            for parser, text in outputs.items():
                if text is None:
                    rows.append({"doc_id": doc_id, "parser": parser, "pages": pages, "error": "no output"})
                    continue
                dec, alln = numbers(text)
                if parser == "docling":
                    tables = len(d.get("tables", []))
                    secs_page = round(d.get("seconds", 0) / max(pages, 1), 1)
                else:
                    tables = text.count("<table")
                    secs_page = ""
                rows.append({
                    "doc_id": doc_id, "parser": parser, "pages": pages,
                    "decimal_recall": round(recall(ref_dec, dec), 3),
                    "any_number_recall": round(recall(ref_all, alln), 3),
                    "text_ratio": round(len(text) / max(len(layer), 1), 2),
                    "tables": tables, "seconds_per_page": secs_page, "error": "",
                })
            print(f"  {doc_id[:60]}: done")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = ["doc_id", "parser", "pages", "decimal_recall", "any_number_recall", "text_ratio",
              "tables", "seconds_per_page", "error"]
    with open(out.with_suffix(".csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    def mean(parser, field):
        vals = [r[field] for r in rows if r["parser"] == parser and isinstance(r.get(field), (int, float))]
        return round(sum(vals) / len(vals), 3) if vals else None

    lines = [f"# Parser pilot, {date.today()}", "",
             f"{len(keys)} graduation-corpus papers, Docling (Modal, CPU) vs MinerU (January 2026 output).",
             "Recall is measured against each PDF's own text layer (see evaluation/parser_pilot.py).", "",
             "| Parser | Decimal recall | Any-number recall | Text ratio | Tables (total) |",
             "| --- | --- | --- | --- | --- |"]
    for parser in ("docling", "mineru"):
        total_tables = sum(r.get("tables", 0) or 0 for r in rows if r["parser"] == parser)
        lines.append(f"| {parser} | {mean(parser, 'decimal_recall')} | {mean(parser, 'any_number_recall')} | "
                     f"{mean(parser, 'text_ratio')} | {total_tables} |")
    lines += ["", "Per paper: see the CSV next to this file."]
    out.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
