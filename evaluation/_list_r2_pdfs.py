"""Quick script to list available PDFs in R2 for comparison testing."""
import os
import boto3
from dotenv import load_dotenv

load_dotenv()

s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{os.environ['CLOUDFLARE_ACCOUNT_ID']}.r2.cloudflarestorage.com",
    aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
)
bucket = os.environ.get("R2_BUCKET_NAME", "devchat-pdfs")
pag = s3.get_paginator("list_objects_v2")

# Global input-pdfs
input_pdfs = []
for page in pag.paginate(Bucket=bucket, Prefix="input-pdfs/"):
    for obj in page.get("Contents", []):
        if obj["Key"].endswith(".pdf"):
            input_pdfs.append(obj["Key"])

print(f"input-pdfs/ PDFs ({len(input_pdfs)} total):")
for k in input_pdfs[:20]:
    print(f"  {k}")

# MinerU outputs (to find docs that have been processed)
mineru_jsons = []
for page in pag.paginate(Bucket=bucket, Prefix="outputs/json/"):
    for obj in page.get("Contents", []):
        if obj["Key"].endswith(".json"):
            mineru_jsons.append(obj["Key"])

print(f"\nExisting MinerU JSON outputs ({len(mineru_jsons)} total):")
for k in mineru_jsons[:20]:
    print(f"  {k}")

# MonkeyOCR outputs (to check how many already exist)
mo_jsons = []
for page in pag.paginate(Bucket=bucket, Prefix="outputs/monkeyocr/json/"):
    for obj in page.get("Contents", []):
        if obj["Key"].endswith(".json"):
            mo_jsons.append(obj["Key"])

print(f"\nExisting MonkeyOCR JSON outputs ({len(mo_jsons)} total):")
for k in mo_jsons[:20]:
    print(f"  {k}")

# RAG project PDFs (first 10)
rags_pdfs = []
for page in pag.paginate(Bucket=bucket, Prefix="rags/"):
    for obj in page.get("Contents", []):
        if obj["Key"].endswith(".pdf"):
            rags_pdfs.append(obj["Key"])
    if len(rags_pdfs) >= 20:
        break

print(f"\nrags/ PDFs (first {min(len(rags_pdfs),20)} shown):")
for k in rags_pdfs[:20]:
    print(f"  {k}")
