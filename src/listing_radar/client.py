"""Thin Etsy Open API v3 client. GET only.

The whole tool rests on one fact: /v3/application/listings/active returns
`views` and `num_favorers` for any active listing with only an app key. That
makes every competitor's traction public, which is what lets demand be
inferred where Etsy publishes no search-volume API.
"""
from __future__ import annotations

import pathlib
import time

import requests

from . import config
from .cache import Cache

API = "https://openapi.etsy.com/v3/application"
DEFAULT_CACHE_DIR = pathlib.Path.home() / ".cache" / "listing-radar"


class QuotaExhausted(RuntimeError):
    """The daily cap is gone. Distinct from a transient failure so callers stop
    retrying and fall back to cached data instead of hammering a dead quota."""


class EtsyClient:
    def __init__(self, cache: Cache | None = None, session=None):
        self.cache = cache if cache is not None else Cache(DEFAULT_CACHE_DIR)
        self.session = session if session is not None else requests.Session()
        self.session.headers["x-api-key"] = config.credentials()
        self.calls = 0

    @property
    def cache_hits(self) -> int:
        return self.cache.hits

    def get(self, path: str, **params) -> dict:
        cached = self.cache.get(path, params)
        if cached is not None:
            return cached
        for attempt in range(4):
            r = self.session.get(f"{API}{path}", params=params, headers={}, timeout=30)
            self.calls += 1
            if r.status_code == 200:
                payload = r.json()
                self.cache.put(path, params, payload)
                return payload
            if r.status_code == 429 and "daily" in r.text.lower():
                raise QuotaExhausted(
                    "Etsy daily quota is gone. Cached results still work; "
                    "live lookups resume tomorrow."
                )
            if r.status_code == 403 and "shared secret" in r.text.lower():
                raise RuntimeError(
                    "Etsy rejected the API key. The x-api-key header must be "
                    "keystring:shared_secret — a bare keystring returns 403. "
                    "Check ETSY_SHARED_SECRET."
                )
            if r.status_code in (429, 500, 502, 503):
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"{r.status_code} {path} :: {r.text[:300]}")
        raise RuntimeError(f"retries exhausted: {path}")

    def search(self, keywords: str, limit: int = 100, offset: int = 0) -> dict:
        return self.get("/listings/active", keywords=keywords,
                        limit=limit, offset=offset)

    def shop(self, shop_id: int) -> dict:
        return self.get(f"/shops/{shop_id}")

    def listing(self, listing_id: int) -> dict:
        return self.get(f"/listings/{listing_id}")
