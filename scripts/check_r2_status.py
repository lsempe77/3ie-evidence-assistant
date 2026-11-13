"""Quick check: which MonkeyOCR outputs exist in R2 and when were they last modified."""
import boto3, os, json
from dotenv import load_dotenv
load_dotenv()

s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{os.environ['CLOUDFLARE_ACCOUNT_ID']}.r2.cloudflarestorage.com",
    aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
    aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    region_name="auto",
)
bucket = os.environ.get("R2_BUCKET_NAME", "devchat-pdfs")

keys = [
    "outputs/monkeyocr/json/0f5ea2c067ed_PDFs_of_included_programs_Bangladesh_-_all_BRAC_programs_BRAC_programs_(40)_Raza_(2012).json",
    "outputs/monkeyocr/json/076ec917aab5_PDFs_of_included_programs_121378172_Gilligan_(2024).json",
    "outputs/monkeyocr/json/0cb609fbf433_PDFs_of_included_programs_122182713.json",
    "outputs/monkeyocr/json/107e85be2bad_PDFs_of_included_programs_Bangladesh_-_all_BRAC_programs_BRAC_programs_(40)_Ahmed_(2009)_Capability_Development.json",
    "outputs/monkeyocr/json/1384653aa039_PDFs_of_included_programs_121378494_Leight_(2024).json",
]

for k in keys:
    doc = k.split("/")[-1][:50]
    try:
        meta = s3.head_object(Bucket=bucket, Key=k)
        size = meta["ContentLength"]
        mod = meta["LastModified"]
        print(f"EXISTS  {size:>8} bytes   {mod}  {doc}")
    except Exception:
        print(f"MISSING                                        {doc}")
