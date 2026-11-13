import os, sys, json
sys.path.insert(0, '.')
from dotenv import load_dotenv; load_dotenv()
import boto3

bucket = os.environ['R2_BUCKET_NAME']
s3 = boto3.client(
    's3',
    endpoint_url='https://' + os.environ['R2_ACCOUNT_ID'] + '.r2.cloudflarestorage.com',
    aws_access_key_id=os.environ['R2_ACCESS_KEY_ID'],
    aws_secret_access_key=os.environ['R2_SECRET_ACCESS_KEY'],
)

resp = s3.list_objects_v2(Bucket=bucket, Prefix='outputs/monkeyocr/json/')
items = sorted(resp.get('Contents', []), key=lambda x: x['LastModified'])

print(f"\n{'='*70}")
print(f"MonkeyOCR outputs done: {len(items)}")
print(f"{'='*70}")
for o in items:
    data = json.loads(s3.get_object(Bucket=bucket, Key=o['Key'])['Body'].read())
    pages = data.get('page_count', '?')
    chars = len(data.get('content', ''))
    tables = len(data.get('tables', []))
    ts = o['LastModified'].strftime('%H:%M:%S')
    name = o['Key'].split('/')[-1]
    # extract readable title from filename
    parts = name.replace('.json', '').split('_')
    # last meaningful segment usually has study name
    readable = ' '.join(parts[-4:]) if len(parts) > 4 else name[:50]
    print(f"  [{ts}]  pages={pages:>3}  chars={chars:>6}  tables={tables:>2}  {readable}")

resp2 = s3.list_objects_v2(Bucket=bucket, Prefix='outputs/json/')
mineru_count = len(resp2.get('Contents', []))
print(f"\nMinerU outputs: {mineru_count}")
print(f"MonkeyOCR done: {len(items)} / {mineru_count}  ({100*len(items)//max(mineru_count,1)}%)")

# check still-running apps
print("\nStill running (ephemeral Modal apps):")
import subprocess
result = subprocess.run(['modal', 'app', 'list'], capture_output=True, text=True, encoding='utf-8', errors='replace')
for line in result.stdout.splitlines():
    if 'ephemeral' in line:
        print(' ', line.strip())
