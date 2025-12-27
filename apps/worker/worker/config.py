import os
from dotenv import load_dotenv

ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(dotenv_path=ENV_PATH)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "").strip()
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "").strip()

if not DATABASE_URL:
    raise RuntimeError(f"DATABASE_URL is required (check {ENV_PATH})")
if not SEC_USER_AGENT:
    raise RuntimeError(f"SEC_USER_AGENT is required (check {ENV_PATH})")
