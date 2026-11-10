"""
Score the table estimate extractor (src/extraction/table_estimates.py) against the
graduation review's hand extraction (20 estimates, 3 studies), per model.

    python evaluation/extraction_test.py --om-qex ../../pipelines/8w-sr/OM_QEX \
        --models anthropic/claude-haiku-5.5,anthropic/claude-sonnet-5.5

Reads each study's saved Docling output from R2. Bar for a full run (roadmap N6):
at least 18 of 20 found with the right SE, and no descriptive table returned as results.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evaluation"))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from check_estimates_vs_human import check, human_estimates  # noqa: E402
from run_benchmark import openrouter_usage  # noqa: E402
from src.extraction.table_estimates import extract_document  # noqa: E402

PROJECT = "7efdc60e-e863-480c-929e-616574725e5f"
DOCS = {  # EPPI ID -> document in the graduation collection
    "121294984": "61ddcec5e910_PDFs_of_included_programs_121294984",
    "121498842": "3d1065d6b553_PDFs_of_included_programs_121498842_translated_into_English",
    "121058364": "ed8331ab9500_PDFs_of_included_programs_121058364",
}


def load_content_list(doc: str) -> list:
    import boto3

    s3 = boto3.client("s3", endpoint_url=f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
                      aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"], aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"])
    bucket = os.environ["R2_BUCKET_NAME"]
    key = f"rags/{PROJECT}/outputs/json/{doc}.json"
    return json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read()).get("content_list") or []


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--om-qex", required=True)
    ap.add_argument("--models", required=True)
    args = ap.parse_args()
    human = list(human_estimates(Path(args.om_qex)))
    key = os.environ["OPENROUTER_API_KEY"]
    contents = {eppi: load_content_list(doc) for eppi, doc in DOCS.items()}
    report = {}
    for model in args.models.split(","):
        before, t0 = openrouter_usage(key), time.time()
        machine, tables, outputs = {}, {}, {}
        for eppi, content in contents.items():
            out = await extract_document(content, model, key)
            outputs[eppi] = out
            machine[eppi] = [e for e in out["estimates"] if e["grounded"]]
            tables[eppi] = out["tables"]
        spend = openrouter_usage(key)
        found, se_ok, se_total, missing = check(human, machine)
        all_est = sum(len(o["estimates"]) for o in outputs.values())
        grounded = sum(len(v) for v in machine.values())
        report[model] = {
            "found": f"{found}/{len(human)}", "se_right": f"{se_ok}/{se_total}",
            "estimates": all_est, "grounded": grounded,
            "results_tables": {e: sum(t["results_table"] for t in tables[e]) for e in tables},
            "tables": {e: len(tables[e]) for e in tables},
            "table_errors": sum(1 for e in tables for t in tables[e] if t["error"]),
            "seconds": round(time.time() - t0, 1),
            "spend_usd": round(spend - before, 4) if before is not None and spend is not None else None,
            "missing": missing,
        }
        print(f"\n{model}: found {found}/{len(human)}, SE right {se_ok}/{se_total}, "
              f"{grounded}/{all_est} estimates grounded, {report[model]['seconds']}s, ${report[model]['spend_usd']}")
        for m in missing:
            print("   missing:", m)
        short = model.split("/")[-1].replace(".", "-")
        out_dir = ROOT / "evaluation/results"
        (out_dir / f"extraction_{short}_{date.today().isoformat()}.json").write_text(
            json.dumps(outputs, indent=1, ensure_ascii=False), encoding="utf-8")
    (ROOT / "evaluation/results" / f"extraction_test_{date.today().isoformat()}.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
