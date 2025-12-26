import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

url = os.environ["DATABASE_URL"]
with psycopg2.connect(url) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT now();")
        print("DB OK:", cur.fetchone()[0])
