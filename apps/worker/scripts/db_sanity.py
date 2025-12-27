import os
import sys

# Add apps/worker to PYTHONPATH so "import worker" works
WORKER_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, WORKER_ROOT)

import psycopg
from worker.config import DATABASE_URL

with psycopg.connect(DATABASE_URL) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT 1;")
        print("worker db ok:", cur.fetchone()[0])
