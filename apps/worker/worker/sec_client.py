from __future__ import annotations

import time
from typing import Any, Dict

import requests

DEFAULT_DELAY_S = 0.25  # ~4 req/sec

class SecClient:
    def __init__(self, user_agent: str, delay_s: float = DEFAULT_DELAY_S):
        if not user_agent or "@" not in user_agent:
            raise ValueError("SEC_USER_AGENT must include a contact email")
        self.user_agent = user_agent
        self.delay_s = delay_s
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": self.user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Accept": "*/*",
            }
        )
        self._last = 0.0

    def _throttle(self) -> None:
        now = time.time()
        wait = self.delay_s - (now - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()

    def get_text(self, url: str, timeout: int = 30) -> str:
        self._throttle()
        r = self._session.get(url, timeout=timeout)
        if r.status_code == 429:
            time.sleep(2.0)
            self._throttle()
            r = self._session.get(url, timeout=timeout)
        r.raise_for_status()
        return r.text

    def get_json(self, url: str, timeout: int = 30) -> Dict[str, Any]:
        self._throttle()
        r = self._session.get(url, timeout=timeout)
        if r.status_code == 429:
            time.sleep(2.0)
            self._throttle()
            r = self._session.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json()