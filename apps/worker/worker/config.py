from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_WORKER_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(_WORKER_ROOT / ".env", override=False)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "").strip()
SEC_REQUEST_DELAY = float(os.getenv("SEC_REQUEST_DELAY", "0.25"))

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is missing in apps/worker/.env")

if not SEC_USER_AGENT:
    raise RuntimeError("SEC_USER_AGENT is missing in apps/worker/.env")