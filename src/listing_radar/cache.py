"""Disk cache for GET responses.

Etsy's rate limit is per key, so this is a requirement rather than an
optimisation: a developer-mode app gets 10,000 calls a day and a few
uncached iterations will burn the lot.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import time

DEFAULT_TTL = 7 * 86400


class Cache:
    def __init__(self, root: pathlib.Path, ttl_seconds: int = DEFAULT_TTL):
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl_seconds
        self.hits = 0

    def _path(self, path: str, params: dict) -> pathlib.Path:
        key = path + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return self.root / f"{hashlib.sha1(key.encode()).hexdigest()}.json"

    def get(self, path: str, params: dict) -> dict | None:
        p = self._path(path, params)
        if not p.exists():
            return None
        if time.time() - p.stat().st_mtime >= self.ttl:
            return None
        try:
            payload = json.loads(p.read_text())
        except json.JSONDecodeError:
            # A truncated write (Ctrl-C mid-scan, full disk) must degrade to a
            # miss, not wedge every future run on a file nothing can parse.
            return None
        self.hits += 1
        return payload

    def put(self, path: str, params: dict, payload: dict) -> None:
        p = self._path(path, params)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(json.dumps(payload))
        tmp.replace(p)
