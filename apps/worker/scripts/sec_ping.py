import os
import requests
from dotenv import load_dotenv

ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(ENV_PATH)

ua = os.getenv("SEC_USER_AGENT", "").strip()
url = "https://www.sec.gov/Archives/edgar/daily-index/2025/QTR4/master.20251202.idx"

headers = {
  "User-Agent": ua,
  "Accept-Encoding": "gzip, deflate",
  "Host": "www.sec.gov",
}

r = requests.get(url, headers=headers, timeout=30)
print("status:", r.status_code)
print("len:", len(r.text))
print("has_header:", "CIK|Company Name|Form Type|Date Filed|Filename" in r.text)

lines = r.text.splitlines()
count_4  = sum(1 for ln in lines if "|4|" in ln)
count_4a = sum(1 for ln in lines if "|4/A|" in ln)
print("lines:", len(lines), "form4:", count_4, "form4/a:", count_4a)