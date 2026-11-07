"""Check RAG project MinerU outputs in R2."""
import os, json
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
rag_id = "0816e8d3-ab23-417c-bf3f-e45531411c73"
pag = s3.get_paginator("list_objects_v2")

for prefix in [
    f"rags/{rag_id}/outputs/json/",
    f"rags/{rag_id}/outputs/md/",
]:
    found = []
    for page in pag.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            found.append(obj["Key"])
    print(f"\n{prefix}  ({len(found)} total):")
    for k in found[:5]:
        print(f"  {k}")

# Also peek at one JSON to see its structure
prefix = f"rags/{rag_id}/outputs/json/"
keys = []
for page in pag.paginate(Bucket=bucket, Prefix=prefix):
    for obj in page.get("Contents", []):
        if obj["Key"].endswith(".json"):
            keys.append(obj["Key"])
    if keys:
        break

if keys:
    resp = s3.get_object(Bucket=bucket, Key=keys[0])
    data = json.loads(resp["Body"].read())
    print(f"\nSample JSON keys for {keys[0]}:")
    print(list(data.keys()))
    print(f"doc_id: {data.get('doc_id')}")
    print(f"source_key: {data.get('source_key')}")
    print(f"content chars: {len(data.get('content',''))}")
    print(f"tables: {len(data.get('tables', []))}")
