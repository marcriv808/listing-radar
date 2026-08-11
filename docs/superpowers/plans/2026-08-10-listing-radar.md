# listing-radar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a read-only, MIT-licensed command-line tool that infers Etsy demand from publicly available listing data, so a solo seller can decide what to build without paying for a research subscription.

**Architecture:** Five units with one responsibility each — `config` (credentials), `cache` (disk-backed responses), `client` (thin Etsy v3 wrapper, unauthenticated by default), `scoring` (pure functions, no I/O), and one module per command. The CLI dispatches subcommands. Nothing writes to Etsy; there is no OAuth flow anywhere in the codebase.

**Tech Stack:** Python 3.10+, `requests`, `pytest`. No other runtime dependencies.

## Global Constraints

- Python 3.10 or newer (the code uses `X | None` unions and builtin generics).
- Runtime dependencies are limited to `requests`. Dev dependencies are limited to `pytest`.
- **No write calls, ever.** No `requests.post/patch/put/delete`, no `Authorization` header, no OAuth, no token refresh. A test enforces this by scanning the source tree.
- Listing age is computed from `original_creation_timestamp`. Using `creation_timestamp` is a defect — digital listings auto-renew roughly every four months and that field reports the last renewal, making settled listings read as brand new.
- Credentials come from the environment only: `ETSY_KEYSTRING` and `ETSY_SHARED_SECRET`. The `x-api-key` header value is `keystring:shared_secret` — a bare keystring returns `403 {"error":"Shared secret is required in x-api-key header."}`.
- The `rank` command prints its relevance-search caveat on every run, to stdout, not only in documentation.
- Scoring formulas are carried over unchanged from the source project and are unvalidated heuristics. The README says so; no task "improves" them.
- Prices and currency conversion are out of scope for v1. Etsy returns each listing in the seller's currency and mixing them silently corrupts any median, so v1 omits price rather than shipping a wrong number.
- Every commit message ends with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

---

## File Structure

| Path | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, deps, `listing-radar` console script |
| `src/listing_radar/config.py` | Read and validate credentials from the environment |
| `src/listing_radar/cache.py` | Disk cache keyed by endpoint + params, with hit counting |
| `src/listing_radar/models.py` | `Listing` dataclass and `from_api` parsing |
| `src/listing_radar/scoring.py` | `median`, `entrenchment`, `winnable`, `opportunity`, `rank_verdict` — pure |
| `src/listing_radar/client.py` | `EtsyClient` — GET only, retries, quota handling |
| `src/listing_radar/commands/demand.py` | `demand <phrase>` |
| `src/listing_radar/commands/traction.py` | `traction <shop\|listing>` |
| `src/listing_radar/commands/rank.py` | `rank <phrase> --listing <id>` |
| `src/listing_radar/commands/niche.py` | `niche <vertical>` |
| `src/listing_radar/cli.py` | Argument parsing and subcommand dispatch |
| `tests/fixtures/*.json` | Recorded API shapes with identifying detail removed |
| `README.md`, `LICENSE` | Positioning and MIT license |

---

### Task 1: Project scaffold and credential handling

**Files:**
- Create: `pyproject.toml`
- Create: `src/listing_radar/__init__.py`
- Create: `src/listing_radar/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing
- Produces: `config.credentials() -> str` returning the `x-api-key` value `"keystring:shared_secret"`; raises `config.MissingCredentials` (subclass of `RuntimeError`) with an actionable message when either half is absent.

- [ ] **Step 1: Write the failing test**

```python
import pytest
from listing_radar import config


def test_credentials_joins_keystring_and_secret(monkeypatch):
    monkeypatch.setenv("ETSY_KEYSTRING", "abc123")
    monkeypatch.setenv("ETSY_SHARED_SECRET", "s3cret")
    assert config.credentials() == "abc123:s3cret"


def test_missing_secret_names_the_actual_cause(monkeypatch):
    monkeypatch.setenv("ETSY_KEYSTRING", "abc123")
    monkeypatch.delenv("ETSY_SHARED_SECRET", raising=False)
    with pytest.raises(config.MissingCredentials) as e:
        config.credentials()
    assert "ETSY_SHARED_SECRET" in str(e.value)
    assert "keystring:shared_secret" in str(e.value)


def test_missing_keystring_is_not_reported_as_a_secret_problem(monkeypatch):
    monkeypatch.delenv("ETSY_KEYSTRING", raising=False)
    monkeypatch.setenv("ETSY_SHARED_SECRET", "s3cret")
    with pytest.raises(config.MissingCredentials) as e:
        config.credentials()
    assert "ETSY_KEYSTRING" in str(e.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'listing_radar'`

- [ ] **Step 3: Write pyproject.toml**

```toml
[project]
name = "listing-radar"
version = "0.1.0"
description = "Demand research for Etsy sellers, from public listing data"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
dependencies = ["requests>=2.31"]

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.scripts]
listing-radar = "listing_radar.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 4: Write the implementation**

Create `src/listing_radar/__init__.py` containing only:

```python
__version__ = "0.1.0"
```

Create `src/listing_radar/config.py`:

```python
"""Credential loading.

Etsy rejects a bare keystring on the endpoints this tool uses with
403 {"error":"Shared secret is required in x-api-key header."}. The credential
is the pair joined by a colon. In the project this was extracted from, that 403
was mapped to a generic fallback and read for weeks as "our app is not approved
yet" — a plausible story that was wrong and undisprovable without calling Etsy
by hand. So the error here names the actual missing variable.
"""
from __future__ import annotations

import os

DOCS = "https://www.etsy.com/developers/register"


class MissingCredentials(RuntimeError):
    pass


def credentials() -> str:
    keystring = os.environ.get("ETSY_KEYSTRING", "").strip()
    secret = os.environ.get("ETSY_SHARED_SECRET", "").strip()
    missing = [n for n, v in (("ETSY_KEYSTRING", keystring),
                              ("ETSY_SHARED_SECRET", secret)) if not v]
    if missing:
        raise MissingCredentials(
            f"{' and '.join(missing)} not set. Etsy needs both halves: the "
            f"x-api-key header value is keystring:shared_secret, and a bare "
            f"keystring returns 403. Register an app at {DOCS}, then export "
            f"both variables."
        )
    return f"{keystring}:{secret}"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_config.py -v`
Expected: PASS, 3 passed

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/listing_radar/__init__.py src/listing_radar/config.py tests/test_config.py
git commit -m "$(cat <<'EOF'
feat: project scaffold and credential handling

The x-api-key value is keystring:shared_secret; a bare keystring 403s. The
error names the missing variable rather than failing vague.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Scoring functions

**Files:**
- Create: `src/listing_radar/scoring.py`
- Test: `tests/test_scoring.py`

**Interfaces:**
- Consumes: nothing (pure functions over plain numbers and lists)
- Produces:
  - `median(values: list[float]) -> float`
  - `views_per_day(views: int, age_days: float) -> float`
  - `entrenchment(age_days: list[float]) -> float`
  - `winnable(entrenchment_days: float) -> float`
  - `opportunity(demand: float, competition: int, winnable_factor: float) -> float`
  - `rank_verdict(position: int | None, competition: int, no_market_below: int = 200) -> str` returning one of `"NO MARKET"`, `"ABSENT"`, `"TOP100"`, `"BURIED"`

- [ ] **Step 1: Write the failing test**

```python
import math
import pytest
from listing_radar import scoring


def test_median_of_even_length_averages_middle_two():
    assert scoring.median([1.0, 2.0, 3.0, 4.0]) == 2.5


def test_median_of_empty_is_zero():
    assert scoring.median([]) == 0.0


def test_views_per_day_never_divides_by_less_than_one_day():
    assert scoring.views_per_day(100, 0.0) == 100.0
    assert scoring.views_per_day(100, 10.0) == 10.0


def test_winnable_saturates_at_one_for_young_rankers():
    assert scoring.winnable(50.0) == 1.0
    assert scoring.winnable(400.0) == 1.0


def test_winnable_penalises_entrenched_rankers():
    assert scoring.winnable(800.0) == pytest.approx(0.5)


def test_opportunity_matches_the_carried_over_formula():
    expected = 12.0 / math.log10(500 + 10) * 0.8
    assert scoring.opportunity(12.0, 500, 0.8) == pytest.approx(expected)


def test_opportunity_is_zero_when_there_is_no_demand():
    assert scoring.opportunity(0.0, 500, 1.0) == 0.0


def test_thin_result_set_is_no_market_even_when_we_rank_first():
    assert scoring.rank_verdict(1, 12) == "NO MARKET"


def test_not_found_in_a_real_market_is_absent():
    assert scoring.rank_verdict(None, 5000) == "ABSENT"


def test_position_within_first_hundred_is_top100():
    assert scoring.rank_verdict(100, 5000) == "TOP100"


def test_position_past_first_hundred_is_buried():
    assert scoring.rank_verdict(101, 5000) == "BURIED"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_scoring.py -v`
Expected: FAIL — `ImportError: cannot import name 'scoring'`

- [ ] **Step 3: Write the implementation**

Create `src/listing_radar/scoring.py`:

```python
"""The four formulas, as pure functions.

Etsy publishes no search-volume API. Demand is therefore inferred from the
traction of whoever currently ranks for a phrase: every active listing exposes
lifetime views and an original creation date, so views/day is computable for
any competitor.

These are heuristics carried over unchanged from the project this was extracted
from. They have no published validation. Treat the output as a ranking signal,
not a measurement.
"""
from __future__ import annotations

import math
import statistics

# A result set thinner than this is an empty room, not a competitive loss.
NO_MARKET_BELOW = 200

# Top rankers younger than this are displaceable; older ones are entrenched.
WINNABLE_AGE_DAYS = 400.0


def median(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(statistics.median(values))


def views_per_day(views: int, age_days: float) -> float:
    return views / max(age_days, 1.0)


def entrenchment(age_days: list[float]) -> float:
    return median(age_days)


def winnable(entrenchment_days: float) -> float:
    return min(1.0, WINNABLE_AGE_DAYS / max(entrenchment_days, 1.0))


def opportunity(demand: float, competition: int, winnable_factor: float) -> float:
    return demand / math.log10(max(competition, 1) + 10) * winnable_factor


def rank_verdict(position: int | None, competition: int,
                 no_market_below: int = NO_MARKET_BELOW) -> str:
    """Zero views has three different causes and each has a different fix.

    NO MARKET is checked first and on purpose: ranking first in a room of twelve
    listings is not a win, and reporting it as TOP100 would read as success.
    """
    if competition < no_market_below:
        return "NO MARKET"
    if position is None:
        return "ABSENT"
    return "TOP100" if position <= 100 else "BURIED"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_scoring.py -v`
Expected: PASS, 11 passed

- [ ] **Step 5: Commit**

```bash
git add src/listing_radar/scoring.py tests/test_scoring.py
git commit -m "$(cat <<'EOF'
feat: scoring formulas as pure functions

demand / log10(competition+10) * winnable, where winnable saturates at 1.0
below 400 days of ranker age. NO MARKET is evaluated before position so that
ranking first in an empty room never reports as success.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Listing model

**Files:**
- Create: `src/listing_radar/models.py`
- Create: `tests/fixtures/listing.json`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: `scoring.views_per_day`
- Produces: `Listing` dataclass with fields `listing_id, shop_id, title, tags, views, favorers, age_days, views_per_day, fav_rate, url`, and classmethod `Listing.from_api(row: dict, now: float) -> Listing`

- [ ] **Step 1: Write the failing test**

Create `tests/fixtures/listing.json`:

```json
{
  "listing_id": 1000000001,
  "shop_id": 2000002,
  "title": "Freelance Income Tracker, Client Tracker, Invoice Log",
  "tags": ["freelance tracker", "invoice log", "client tracker"],
  "views": 900,
  "num_favorers": 45,
  "url": "https://www.etsy.com/listing/1000000001/example",
  "original_creation_timestamp": 1700000000,
  "creation_timestamp": 1780000000
}
```

Create `tests/test_models.py`:

```python
import json
import pathlib
from listing_radar.models import Listing

FIXTURE = pathlib.Path(__file__).parent / "fixtures" / "listing.json"
# 100 days after the fixture's original_creation_timestamp
NOW = 1700000000 + 100 * 86400


def load():
    return json.loads(FIXTURE.read_text())


def test_age_uses_original_creation_timestamp_not_renewal():
    """Digital listings auto-renew about every four months. creation_timestamp
    reports the last renewal, which makes a settled listing read as brand new
    and inflates its views/day. The fixture's two timestamps are 925 days
    apart precisely so this test fails loudly if the wrong field is read."""
    listing = Listing.from_api(load(), now=NOW)
    assert round(listing.age_days) == 100
    assert round(listing.views_per_day, 1) == 9.0


def test_missing_views_defaults_to_zero_not_none():
    row = load()
    del row["views"]
    assert Listing.from_api(row, now=NOW).views == 0


def test_fav_rate_is_zero_when_no_views():
    row = load()
    row["views"] = 0
    assert Listing.from_api(row, now=NOW).fav_rate == 0.0


def test_fav_rate_is_favorers_over_views():
    assert Listing.from_api(load(), now=NOW).fav_rate == 45 / 900


def test_tags_default_to_empty_list_when_absent():
    row = load()
    del row["tags"]
    assert Listing.from_api(row, now=NOW).tags == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'listing_radar.models'`

- [ ] **Step 3: Write the implementation**

Create `src/listing_radar/models.py`:

```python
"""The one listing shape this tool reads.

Only the fields the four commands actually use. Price is deliberately absent:
Etsy returns each listing in the seller's own currency, and taking a median
across mixed currencies silently produces a wrong number.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import scoring


@dataclass
class Listing:
    listing_id: int
    shop_id: int
    title: str
    views: int
    favorers: int
    age_days: float
    views_per_day: float
    fav_rate: float
    url: str = ""
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, row: dict, now: float | None = None) -> "Listing":
        now = time.time() if now is None else now
        # original_creation_timestamp, never creation_timestamp — see the
        # regression test in tests/test_models.py for why this matters.
        created = row.get("original_creation_timestamp") or now
        age_days = max((now - created) / 86400.0, 1.0)
        views = row.get("views") or 0
        favorers = row.get("num_favorers") or 0
        return cls(
            listing_id=row["listing_id"],
            shop_id=row.get("shop_id", 0),
            title=row.get("title", ""),
            views=views,
            favorers=favorers,
            age_days=age_days,
            views_per_day=scoring.views_per_day(views, age_days),
            fav_rate=(favorers / views if views else 0.0),
            url=row.get("url", ""),
            tags=row.get("tags") or [],
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_models.py -v`
Expected: PASS, 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/listing_radar/models.py tests/test_models.py tests/fixtures/listing.json
git commit -m "$(cat <<'EOF'
feat: Listing model with an original_creation_timestamp regression test

The fixture carries two timestamps 925 days apart so reading the renewal date
instead of the original fails the test loudly.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Cache and client

**Files:**
- Create: `src/listing_radar/cache.py`
- Create: `src/listing_radar/client.py`
- Test: `tests/test_cache.py`
- Test: `tests/test_client.py`

**Interfaces:**
- Consumes: `config.credentials`
- Produces:
  - `cache.Cache(root: pathlib.Path, ttl_seconds: int = 604800)` with `.get(path, params) -> dict | None`, `.put(path, params, payload) -> None`, and attribute `.hits: int`
  - `client.EtsyClient(cache=None, session=None)` with `.get(path, **params) -> dict`, `.search(keywords, limit=100, offset=0) -> dict`, `.shop(shop_id) -> dict`, `.listing(listing_id) -> dict`, attributes `.calls: int` and `.cache_hits: int`
  - `client.QuotaExhausted(RuntimeError)`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_cache.py`:

```python
from listing_radar.cache import Cache


def test_put_then_get_round_trips(tmp_path):
    c = Cache(tmp_path)
    c.put("/listings/active", {"keywords": "x"}, {"count": 3})
    assert c.get("/listings/active", {"keywords": "x"}) == {"count": 3}
    assert c.hits == 1


def test_different_params_are_different_entries(tmp_path):
    c = Cache(tmp_path)
    c.put("/listings/active", {"keywords": "x"}, {"count": 3})
    assert c.get("/listings/active", {"keywords": "y"}) is None


def test_param_order_does_not_change_the_key(tmp_path):
    c = Cache(tmp_path)
    c.put("/x", {"a": 1, "b": 2}, {"ok": True})
    assert c.get("/x", {"b": 2, "a": 1}) == {"ok": True}


def test_expired_entry_is_a_miss(tmp_path):
    c = Cache(tmp_path, ttl_seconds=0)
    c.put("/x", {}, {"ok": True})
    assert c.get("/x", {}) is None
```

Create `tests/test_client.py`:

```python
import pathlib
import pytest
from listing_radar.cache import Cache
from listing_radar.client import EtsyClient, QuotaExhausted

SRC = pathlib.Path(__file__).resolve().parents[1] / "src"


class FakeResponse:
    def __init__(self, status_code, payload=None, text="", headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.headers = {}

    def get(self, url, params=None, headers=None, timeout=None):
        self.requests.append((url, params))
        return self.responses.pop(0)


@pytest.fixture(autouse=True)
def creds(monkeypatch):
    monkeypatch.setenv("ETSY_KEYSTRING", "k")
    monkeypatch.setenv("ETSY_SHARED_SECRET", "s")


def test_get_returns_payload_and_counts_the_call(tmp_path):
    session = FakeSession([FakeResponse(200, {"count": 1})])
    c = EtsyClient(cache=Cache(tmp_path), session=session)
    assert c.get("/listings/active", keywords="x") == {"count": 1}
    assert c.calls == 1


def test_second_identical_get_is_served_from_cache(tmp_path):
    session = FakeSession([FakeResponse(200, {"count": 1})])
    c = EtsyClient(cache=Cache(tmp_path), session=session)
    c.get("/listings/active", keywords="x")
    c.get("/listings/active", keywords="x")
    assert c.calls == 1
    assert c.cache_hits == 1


def test_daily_quota_raises_a_distinct_error(tmp_path):
    session = FakeSession([FakeResponse(429, text="daily limit exceeded")])
    c = EtsyClient(cache=Cache(tmp_path), session=session)
    with pytest.raises(QuotaExhausted):
        c.get("/listings/active", keywords="x")


def test_403_explains_the_shared_secret_requirement(tmp_path):
    session = FakeSession([
        FakeResponse(403, text='{"error":"Shared secret is required in x-api-key header."}')
    ])
    c = EtsyClient(cache=Cache(tmp_path), session=session)
    with pytest.raises(RuntimeError) as e:
        c.get("/listings/active", keywords="x")
    assert "keystring:shared_secret" in str(e.value)


def test_sends_the_api_key_header(tmp_path):
    session = FakeSession([FakeResponse(200, {})])
    EtsyClient(cache=Cache(tmp_path), session=session).get("/x")
    assert session.headers["x-api-key"] == "k:s"


def test_source_tree_contains_no_write_calls():
    """This tool is read-only by construction. If a write ever lands here it is
    a design break, not a feature, so the test scans the source itself."""
    banned = ("requests.post", "requests.patch", "requests.put",
              "requests.delete", ".post(", ".patch(", ".put(", ".delete(",
              "Authorization")
    offenders = []
    for path in SRC.rglob("*.py"):
        text = path.read_text()
        for token in banned:
            if token in text:
                offenders.append(f"{path.name}: {token}")
    assert offenders == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_cache.py tests/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'listing_radar.cache'`

- [ ] **Step 3: Write the cache**

Create `src/listing_radar/cache.py`:

```python
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
        self.hits += 1
        return json.loads(p.read_text())

    def put(self, path: str, params: dict, payload: dict) -> None:
        self._path(path, params).write_text(json.dumps(payload))
```

- [ ] **Step 4: Write the client**

Create `src/listing_radar/client.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_cache.py tests/test_client.py -v`
Expected: PASS, 10 passed

- [ ] **Step 6: Commit**

```bash
git add src/listing_radar/cache.py src/listing_radar/client.py tests/test_cache.py tests/test_client.py
git commit -m "$(cat <<'EOF'
feat: disk cache and read-only Etsy client

Rate limits are per key, so caching is a requirement not an optimisation. A
test scans the source tree for write calls and Authorization headers so the
read-only guarantee cannot silently regress.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: The `demand` command and CLI skeleton

**Files:**
- Create: `src/listing_radar/commands/__init__.py`
- Create: `src/listing_radar/commands/demand.py`
- Create: `src/listing_radar/cli.py`
- Test: `tests/test_demand.py`

**Interfaces:**
- Consumes: `EtsyClient.search`, `Listing.from_api`, `scoring.*`
- Produces: `demand.analyse(client, phrase, sample=100, now=None) -> dict` with keys `phrase, competition, sampled, demand, entrenchment, winnable, opportunity, no_market`; `demand.render(result) -> str`; `cli.main(argv=None) -> int`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from listing_radar.commands import demand

NOW = 1700000000 + 100 * 86400


class FakeClient:
    def __init__(self, count, rows):
        self._count, self._rows = count, rows
        self.cache_hits = 0

    def search(self, keywords, limit=100, offset=0):
        return {"count": self._count, "results": self._rows if offset == 0 else []}


def row(listing_id, views, age_days=100):
    return {"listing_id": listing_id, "shop_id": 1, "title": "t", "views": views,
            "num_favorers": 0,
            "original_creation_timestamp": NOW - age_days * 86400}


def test_demand_is_median_views_per_day_of_the_rankers():
    client = FakeClient(5000, [row(1, 100), row(2, 900), row(3, 500)])
    result = demand.analyse(client, "freelance tracker", now=NOW)
    assert result["demand"] == pytest.approx(5.0)
    assert result["competition"] == 5000
    assert result["sampled"] == 3


def test_thin_result_set_is_flagged_no_market():
    client = FakeClient(12, [row(1, 900)])
    result = demand.analyse(client, "very specific thing", now=NOW)
    assert result["no_market"] is True


def test_entrenched_rankers_reduce_opportunity():
    young = FakeClient(5000, [row(1, 900, age_days=100)])
    old = FakeClient(5000, [row(1, 900, age_days=1600)])
    a = demand.analyse(young, "x", now=NOW)
    b = demand.analyse(old, "x", now=NOW)
    assert b["opportunity"] < a["opportunity"]


def test_render_states_the_no_market_verdict_in_words():
    client = FakeClient(12, [row(1, 900)])
    text = demand.render(demand.analyse(client, "x", now=NOW))
    assert "NO MARKET" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_demand.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'listing_radar.commands'`

- [ ] **Step 3: Write the implementation**

Create `src/listing_radar/commands/__init__.py` as an empty file.

Create `src/listing_radar/commands/demand.py`:

```python
"""demand <phrase> — is anyone actually searching for this?

A phrase whose top rankers earn roughly zero views a day has no traffic,
however targeted it feels. That is the whole point of the command.
"""
from __future__ import annotations

from .. import scoring
from ..models import Listing


def analyse(client, phrase: str, sample: int = 100, now: float | None = None) -> dict:
    page = client.search(phrase, limit=min(sample, 100), offset=0)
    competition = page.get("count", 0)
    listings = [Listing.from_api(r, now=now) for r in page.get("results", [])]

    d = scoring.median([l.views_per_day for l in listings])
    ent = scoring.entrenchment([l.age_days for l in listings])
    win = scoring.winnable(ent)
    return {
        "phrase": phrase,
        "competition": competition,
        "sampled": len(listings),
        "demand": round(d, 2),
        "entrenchment": round(ent, 0),
        "winnable": round(win, 2),
        "opportunity": round(scoring.opportunity(d, competition, win), 2),
        "no_market": competition < scoring.NO_MARKET_BELOW,
    }


def render(result: dict) -> str:
    lines = [
        f"phrase        {result['phrase']}",
        f"demand        {result['demand']} median views/day of the listings ranking for it",
        f"competition   {result['competition']} active listings",
        f"entrenchment  {result['entrenchment']:.0f} days median age of the top rankers",
        f"opportunity   {result['opportunity']}",
    ]
    if result["no_market"]:
        lines.append("")
        lines.append(
            f"NO MARKET — fewer than {scoring.NO_MARKET_BELOW} listings match this "
            f"phrase. That is an empty room, not a cheap one: nobody sells it "
            f"because nobody buys it."
        )
    return "\n".join(lines)
```

Create `src/listing_radar/cli.py`:

```python
"""listing-radar — demand research for Etsy sellers, from public data."""
from __future__ import annotations

import argparse
import sys

from . import config
from .client import EtsyClient, QuotaExhausted
from .commands import demand


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="listing-radar",
        description="Demand research for Etsy sellers, from public listing data. "
                    "Read-only: this tool never writes to a shop.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("demand", help="is anyone searching for this phrase")
    d.add_argument("phrase")
    d.add_argument("--sample", type=int, default=100,
                   help="how many ranked listings to sample (max 100)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        client = EtsyClient()
        if args.command == "demand":
            print(demand.render(demand.analyse(client, args.phrase, args.sample)))
    except config.MissingCredentials as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except QuotaExhausted as e:
        print(f"error: {e}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_demand.py -v`
Expected: PASS, 4 passed

- [ ] **Step 5: Verify the CLI wiring end to end**

Run: `python3 -m pytest -q && python3 -c "from listing_radar.cli import build_parser; build_parser().parse_args(['demand','x'])" `
Expected: all tests pass, no output from the second command

- [ ] **Step 6: Commit**

```bash
git add src/listing_radar/commands/ src/listing_radar/cli.py tests/test_demand.py
git commit -m "$(cat <<'EOF'
feat: demand command and CLI entry point

demand(phrase) is the median views/day of the listings ranking for it. A thin
result set reports NO MARKET in words rather than as a low score, so a dead
phrase is never mistaken for a cheap one.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: The `traction` command

**Files:**
- Create: `src/listing_radar/commands/traction.py`
- Modify: `src/listing_radar/cli.py`
- Test: `tests/test_traction.py`

**Interfaces:**
- Consumes: `EtsyClient.shop`, `EtsyClient.listing`, `Listing.from_api`
- Produces: `traction.for_listing(client, listing_id, now=None) -> dict`; `traction.for_shop(client, shop_id, now=None) -> dict`; `traction.render(result) -> str`

- [ ] **Step 1: Write the failing test**

```python
import pytest
from listing_radar.commands import traction

NOW = 1700000000 + 100 * 86400


class FakeClient:
    def __init__(self, listing=None, shop=None):
        self._listing, self._shop = listing, shop
        self.cache_hits = 0

    def listing(self, listing_id):
        return {"results": [self._listing]}

    def shop(self, shop_id):
        return self._shop


def test_listing_traction_reports_views_per_day():
    row = {"listing_id": 1, "shop_id": 2, "title": "t", "views": 900,
           "num_favorers": 45,
           "original_creation_timestamp": NOW - 100 * 86400}
    r = traction.for_listing(FakeClient(listing=row), 1, now=NOW)
    assert r["views_per_day"] == pytest.approx(9.0)
    assert r["age_days"] == pytest.approx(100.0)


def test_shop_traction_reports_sales_per_day():
    shop = {"shop_id": 2, "shop_name": "Example", "transaction_sold_count": 500,
            "create_date": NOW - 1000 * 86400}
    r = traction.for_shop(FakeClient(shop=shop), 2, now=NOW)
    assert r["sold"] == 500
    assert r["sales_per_day"] == pytest.approx(0.5)


def test_shop_missing_create_date_falls_back_to_created_timestamp():
    shop = {"shop_id": 2, "shop_name": "Example", "transaction_sold_count": 500,
            "created_timestamp": NOW - 1000 * 86400}
    assert traction.for_shop(FakeClient(shop=shop), 2, now=NOW)["age_days"] == pytest.approx(1000.0)


def test_render_includes_the_shop_name():
    shop = {"shop_id": 2, "shop_name": "Example", "transaction_sold_count": 1,
            "create_date": NOW - 10 * 86400}
    assert "Example" in traction.render(traction.for_shop(FakeClient(shop=shop), 2, now=NOW))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_traction.py -v`
Expected: FAIL — `ImportError: cannot import name 'traction'`

- [ ] **Step 3: Write the implementation**

Create `src/listing_radar/commands/traction.py`:

```python
"""traction <shop|listing> — how well is this competitor really doing?

Lifetime views plus an original creation date gives views/day for any active
listing. Shops additionally expose transaction_sold_count and a create date,
which gives sales/day. None of this requires the competitor's permission; it
is all public on the app key.
"""
from __future__ import annotations

import time

from ..models import Listing


def for_listing(client, listing_id: int, now: float | None = None) -> dict:
    payload = client.listing(listing_id)
    rows = payload.get("results") or [payload]
    listing = Listing.from_api(rows[0], now=now)
    return {
        "kind": "listing",
        "listing_id": listing.listing_id,
        "title": listing.title,
        "views": listing.views,
        "favorers": listing.favorers,
        "age_days": round(listing.age_days, 1),
        "views_per_day": round(listing.views_per_day, 2),
        "fav_rate": round(listing.fav_rate * 100, 2),
    }


def for_shop(client, shop_id: int, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    s = client.shop(shop_id)
    created = s.get("create_date") or s.get("created_timestamp") or now
    age_days = max((now - created) / 86400.0, 1.0)
    sold = s.get("transaction_sold_count") or 0
    return {
        "kind": "shop",
        "shop_id": s.get("shop_id", shop_id),
        "shop_name": s.get("shop_name", ""),
        "sold": sold,
        "age_days": round(age_days, 1),
        "sales_per_day": round(sold / age_days, 3),
    }


def render(result: dict) -> str:
    if result["kind"] == "shop":
        return "\n".join([
            f"shop           {result['shop_name']} ({result['shop_id']})",
            f"sold           {result['sold']} lifetime transactions",
            f"age            {result['age_days']:.0f} days",
            f"sales/day      {result['sales_per_day']}",
        ])
    return "\n".join([
        f"listing        {result['title'][:60]} ({result['listing_id']})",
        f"views          {result['views']} lifetime",
        f"age            {result['age_days']:.0f} days"
        f"   (original creation date, not the last renewal)",
        f"views/day      {result['views_per_day']}",
        f"favourite rate {result['fav_rate']}%",
    ])
```

- [ ] **Step 4: Wire it into the CLI**

In `src/listing_radar/cli.py`, add `traction` to the imports:

```python
from .commands import demand, traction
```

Add this parser after the `demand` parser block in `build_parser`:

```python
    t = sub.add_parser("traction", help="how well is a competitor doing")
    t.add_argument("target", help="a listing id, or shop:<shop_id>")
```

Add this branch after the `demand` branch in `main`:

```python
        elif args.command == "traction":
            if args.target.startswith("shop:"):
                result = traction.for_shop(client, int(args.target[5:]))
            else:
                result = traction.for_listing(client, int(args.target))
            print(traction.render(result))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest -q`
Expected: PASS, all tests green

- [ ] **Step 6: Commit**

```bash
git add src/listing_radar/commands/traction.py src/listing_radar/cli.py tests/test_traction.py
git commit -m "$(cat <<'EOF'
feat: traction command for listings and shops

Views/day from the original creation date, sales/day from
transaction_sold_count over shop age. Output labels the age field as the
original creation date so nobody reads it as the renewal date.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: The `rank` command

**Files:**
- Create: `src/listing_radar/commands/rank.py`
- Modify: `src/listing_radar/cli.py`
- Test: `tests/test_rank.py`

**Interfaces:**
- Consumes: `EtsyClient.search`, `scoring.rank_verdict`
- Produces: `rank.probe(client, phrase, listing_id, depth=250) -> dict` with keys `phrase, listing_id, position, competition, verdict, pages_fetched`; `rank.render(result) -> str`; module constant `rank.CAVEAT: str`

- [ ] **Step 1: Write the failing test**

```python
from listing_radar.commands import rank


class FakeClient:
    def __init__(self, count, pages):
        self._count, self._pages = count, pages
        self.calls = 0
        self.cache_hits = 0

    def search(self, keywords, limit=100, offset=0):
        self.calls += 1
        idx = offset // 100
        results = self._pages[idx] if idx < len(self._pages) else []
        return {"count": self._count, "results": results}


def ids(*values):
    return [{"listing_id": v} for v in values]


def test_found_on_the_first_page_reports_its_position():
    client = FakeClient(5000, [ids(11, 22, 33)])
    r = rank.probe(client, "x", 22)
    assert r["position"] == 2
    assert r["verdict"] == "TOP100"


def test_found_on_the_second_page_is_buried():
    page1 = ids(*range(1, 101))
    page2 = ids(*range(101, 201))
    client = FakeClient(5000, [page1, page2])
    r = rank.probe(client, "x", 150)
    assert r["position"] == 150
    assert r["verdict"] == "BURIED"


def test_not_found_anywhere_in_a_real_market_is_absent():
    client = FakeClient(5000, [ids(*range(1, 101))] * 3)
    r = rank.probe(client, "x", 999999)
    assert r["position"] is None
    assert r["verdict"] == "ABSENT"


def test_thin_market_is_no_market_regardless_of_position():
    client = FakeClient(12, [ids(11, 22)])
    assert rank.probe(client, "x", 22)["verdict"] == "NO MARKET"


def test_probe_stops_early_on_a_short_page():
    client = FakeClient(5000, [ids(1, 2, 3)])
    rank.probe(client, "x", 999999)
    assert client.calls == 1


def test_render_always_includes_the_relevance_search_caveat():
    client = FakeClient(5000, [ids(11, 22)])
    assert rank.CAVEAT in rank.render(rank.probe(client, "x", 22))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_rank.py -v`
Expected: FAIL — `ImportError: cannot import name 'rank'`

- [ ] **Step 3: Write the implementation**

Create `src/listing_radar/commands/rank.py`:

```python
"""rank <phrase> --listing <id> — why does this listing get no views?

Zero views has three very different causes and the fix differs for each:

    BURIED     it ranks, but deep      -> competitive niche, the gap is authority
    ABSENT     not in the result set   -> not actually competing for that phrase
    NO MARKET  the phrase is near-empty-> nobody sells it because nobody buys it

TOP100 is the fourth outcome: it ranks fine and the problem is elsewhere.
"""
from __future__ import annotations

from .. import scoring

DEPTH = 250  # about three pages; past this nobody is finding the listing anyway

CAVEAT = (
    "Caveat: /listings/active?keywords= is the API's relevance search, not "
    "buyer-facing Etsy search ranking. Treat position as ordinal evidence only."
)


def probe(client, phrase: str, listing_id: int, depth: int = DEPTH) -> dict:
    position = None
    competition = None
    pages = 0
    for page in range(depth // 100 + 1):
        payload = client.search(phrase, limit=100, offset=page * 100)
        if competition is None:
            competition = payload.get("count", 0)
        hits = payload.get("results", [])
        pages += 1
        for i, hit in enumerate(hits):
            if hit["listing_id"] == listing_id:
                position = page * 100 + i + 1
                break
        if position is not None or len(hits) < 100 or (page + 1) * 100 >= depth:
            break
    return {
        "phrase": phrase,
        "listing_id": listing_id,
        "position": position,
        "competition": competition or 0,
        "verdict": scoring.rank_verdict(position, competition or 0),
        "pages_fetched": pages,
    }


MEANING = {
    "TOP100": "It ranks. If views are still low the problem is the listing, not visibility.",
    "BURIED": "It ranks but too deep to be found. The gap is authority, not wording.",
    "ABSENT": "It does not appear at all. It is not competing for this phrase.",
    "NO MARKET": "Too few listings match. An empty room, not a cheap one.",
}


def render(result: dict) -> str:
    pos = result["position"] if result["position"] else "not found"
    return "\n".join([
        f"phrase       {result['phrase']}",
        f"listing      {result['listing_id']}",
        f"position     {pos} of {result['competition']} competitors",
        f"verdict      {result['verdict']}",
        f"             {MEANING[result['verdict']]}",
        "",
        CAVEAT,
    ])
```

- [ ] **Step 4: Wire it into the CLI**

In `src/listing_radar/cli.py`, extend the imports:

```python
from .commands import demand, rank, traction
```

Add this parser after the `traction` parser block:

```python
    r = sub.add_parser("rank", help="why a listing gets no views")
    r.add_argument("phrase")
    r.add_argument("--listing", type=int, required=True, dest="listing_id")
    r.add_argument("--depth", type=int, default=rank.DEPTH,
                   help="how deep to look before calling it absent")
```

Add this branch after the `traction` branch in `main`:

```python
        elif args.command == "rank":
            print(rank.render(rank.probe(client, args.phrase,
                                         args.listing_id, args.depth)))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest -q`
Expected: PASS, all tests green

- [ ] **Step 6: Commit**

```bash
git add src/listing_radar/commands/rank.py src/listing_radar/cli.py tests/test_rank.py
git commit -m "$(cat <<'EOF'
feat: rank command with the four-way verdict

BURIED, ABSENT, NO MARKET and TOP100 have different fixes, so the command
names the cause rather than returning a position. The relevance-search caveat
prints on every run.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: The `niche` command

**Files:**
- Create: `src/listing_radar/commands/niche.py`
- Modify: `src/listing_radar/cli.py`
- Test: `tests/test_niche.py`

**Interfaces:**
- Consumes: `demand.analyse`, `EtsyClient.search`, `Listing.from_api`
- Produces: `niche.screen(client, phrase, min_demand=1.0, max_competition=2000, now=None) -> dict` with keys `phrase, demand_gate, room_gate, format_gate, formats, passes, detail`; `niche.render(result) -> str`

- [ ] **Step 1: Write the failing test**

```python
from listing_radar.commands import niche

NOW = 1700000000 + 100 * 86400


class FakeClient:
    def __init__(self, count, rows):
        self._count, self._rows = count, rows
        self.cache_hits = 0

    def search(self, keywords, limit=100, offset=0):
        return {"count": self._count, "results": self._rows if offset == 0 else []}


def row(listing_id, views, title="Planner Template", age_days=100):
    return {"listing_id": listing_id, "shop_id": 1, "title": title, "views": views,
            "num_favorers": 0,
            "original_creation_timestamp": NOW - age_days * 86400}


def test_high_demand_with_room_and_a_beatable_format_passes():
    rows = [row(i, 900, "Budget Spreadsheet Google Sheets") for i in range(1, 6)]
    r = niche.screen(FakeClient(400, rows), "budget spreadsheet", now=NOW)
    assert r["demand_gate"] is True
    assert r["room_gate"] is True
    assert r["format_gate"] is True
    assert r["passes"] is True


def test_demand_you_cannot_surface_against_fails_the_room_gate():
    """39 of 70 listings in the source shop targeted phrases with 5,000-99,000
    competitors and never appeared in the top 250. Demand you cannot rank
    against is not an opportunity."""
    rows = [row(i, 9000, "Budget Spreadsheet Google Sheets") for i in range(1, 6)]
    r = niche.screen(FakeClient(50000, rows), "planner", now=NOW)
    assert r["demand_gate"] is True
    assert r["room_gate"] is False
    assert r["passes"] is False


def test_dead_phrase_fails_the_demand_gate():
    rows = [row(i, 1, "Budget Spreadsheet") for i in range(1, 6)]
    r = niche.screen(FakeClient(400, rows), "obscure thing", now=NOW)
    assert r["demand_gate"] is False
    assert r["passes"] is False


def test_format_gate_fails_when_no_ranker_uses_a_beatable_format():
    rows = [row(i, 900, "Handmade Ceramic Mug") for i in range(1, 6)]
    r = niche.screen(FakeClient(400, rows), "mug", now=NOW)
    assert r["format_gate"] is False


def test_render_names_every_failing_gate():
    rows = [row(i, 1, "Handmade Ceramic Mug") for i in range(1, 6)]
    text = niche.render(niche.screen(FakeClient(50000, rows), "mug", now=NOW))
    assert "DEMAND" in text and "ROOM" in text and "FORMAT" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_niche.py -v`
Expected: FAIL — `ImportError: cannot import name 'niche'`

- [ ] **Step 3: Write the implementation**

Create `src/listing_radar/commands/niche.py`:

```python
"""niche <phrase> — is this worth building?

Three gates, all of which must pass. The third exists because demand alone is
a trap: in the shop this tool came from, 39 of 70 listings targeted phrases
carrying 5,000-99,000 competitors and never appeared in the top 250 results
for their own lead phrase. Demand you cannot surface against is not an
opportunity, it is a trap you fall into repeatedly.
"""
from __future__ import annotations

from .. import scoring
from ..models import Listing
from . import demand as demand_cmd

# Formats a well-built alternative can beat on usability. Presence of these
# among the top rankers means the incumbent product is a document, not an app.
BEATABLE_FORMATS = (
    "spreadsheet", "google sheet", "google sheets", "excel", "xlsx",
    "pdf", "printable", "template", "canva", "notion", "worksheet",
)

MIN_DEMAND = 1.0
MAX_COMPETITION = 2000


def screen(client, phrase: str, min_demand: float = MIN_DEMAND,
           max_competition: int = MAX_COMPETITION, now: float | None = None) -> dict:
    d = demand_cmd.analyse(client, phrase, now=now)

    page = client.search(phrase, limit=100, offset=0)
    listings = [Listing.from_api(r, now=now) for r in page.get("results", [])]
    formats = sorted({
        fmt for l in listings for fmt in BEATABLE_FORMATS
        if fmt in l.title.lower()
    })

    demand_gate = d["demand"] >= min_demand
    room_gate = (scoring.NO_MARKET_BELOW <= d["competition"] <= max_competition)
    format_gate = bool(formats)

    return {
        "phrase": phrase,
        "demand_gate": demand_gate,
        "room_gate": room_gate,
        "format_gate": format_gate,
        "formats": formats,
        "passes": demand_gate and room_gate and format_gate,
        "detail": d,
    }


def render(result: dict) -> str:
    d = result["detail"]
    mark = lambda ok: "pass" if ok else "FAIL"
    lines = [
        f"phrase   {result['phrase']}",
        "",
        f"DEMAND   {mark(result['demand_gate'])}   "
        f"{d['demand']} median views/day of the rankers "
        f"(needs >= {MIN_DEMAND})",
        f"ROOM     {mark(result['room_gate'])}   "
        f"{d['competition']} competitors "
        f"(needs {scoring.NO_MARKET_BELOW}-{MAX_COMPETITION}: enough to imply a "
        f"market, few enough to place in)",
        f"FORMAT   {mark(result['format_gate'])}   "
        f"{', '.join(result['formats']) if result['formats'] else 'no beatable format among the rankers'}",
        "",
        "BUILD" if result["passes"] else "SKIP — every gate must pass.",
    ]
    return "\n".join(lines)
```

- [ ] **Step 4: Wire it into the CLI**

In `src/listing_radar/cli.py`, extend the imports:

```python
from .commands import demand, niche, rank, traction
```

Add this parser after the `rank` parser block:

```python
    n = sub.add_parser("niche", help="screen a phrase against three gates")
    n.add_argument("phrase")
    n.add_argument("--min-demand", type=float, default=niche.MIN_DEMAND)
    n.add_argument("--max-competition", type=int, default=niche.MAX_COMPETITION)
```

Add this branch after the `rank` branch in `main`:

```python
        elif args.command == "niche":
            print(niche.render(niche.screen(client, args.phrase,
                                            args.min_demand, args.max_competition)))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest -q`
Expected: PASS, all tests green

- [ ] **Step 6: Commit**

```bash
git add src/listing_radar/commands/niche.py src/listing_radar/cli.py tests/test_niche.py
git commit -m "$(cat <<'EOF'
feat: niche command with three gates

DEMAND, ROOM and FORMAT must all pass. ROOM exists because demand you cannot
surface against is not an opportunity — the source shop targeted phrases with
tens of thousands of competitors 39 times and never placed.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: README, license, and pre-publication checklist

**Files:**
- Create: `README.md`
- Create: `LICENSE`
- Create: `docs/PRE-PUBLISH.md`
- Modify: `.gitignore` (verify only)

**Interfaces:**
- Consumes: everything
- Produces: no code

- [ ] **Step 1: Write the LICENSE**

Create `LICENSE` with the standard MIT text, `Copyright (c) 2026 Marc Rivera`.

- [ ] **Step 2: Write the README**

Create `README.md`:

````markdown
# listing-radar

Demand research for Etsy sellers, from public listing data. Read-only — it never
writes to your shop.

Built by a solo seller whose own shop scores 91 on every listing-hygiene check
and has made five sales. That is exactly why this measures demand instead of
grading your listings.

## What it answers

```bash
listing-radar demand "clinical supervision hours tracker"
listing-radar traction shop:12345678
listing-radar rank "estate executor checklist" --listing 4514299502
listing-radar niche "budget spreadsheet"
```

| Command | Question |
|---|---|
| `demand` | Is anyone actually searching for this? |
| `traction` | How well is this competitor really doing? |
| `rank` | Why does my listing get no views? |
| `niche` | Is this worth building? |

## How it works

Etsy publishes no search-volume API. But `/v3/application/listings/active`
returns `views` and `num_favorers` for **any** active listing with only an app
key, and every listing carries an original creation date. So demand is inferable
from the traction of whoever currently ranks:

```
demand(phrase)      = median views/day of the listings ranking for it
winnable(phrase)    = min(1, 400 / median age in days of the top rankers)
opportunity(phrase) = demand / log10(competition + 10) * winnable
```

A phrase whose top rankers earn roughly zero views a day has no traffic, however
targeted it feels.

**These formulas are unvalidated heuristics.** They are the ones the author uses,
carried over unchanged. Treat the output as a ranking signal, not a measurement.

## Why `rank` has four answers, not a number

Zero views has different causes and each has a different fix:

- **TOP100** — it ranks; if views are low the problem is the listing
- **BURIED** — ranks too deep to be found; the gap is authority, not wording
- **ABSENT** — not in the results at all; not competing for that phrase
- **NO MARKET** — too few listings match; an empty room, not a cheap one

`/listings/active?keywords=` is the API's relevance search, not buyer-facing
Etsy ranking. Position is ordinal evidence only, and the command says so on
every run.

## Setup

You need your own Etsy app key. Registration and approval take a few days and no
tool can shortcut that.

```bash
export ETSY_KEYSTRING=your_keystring
export ETSY_SHARED_SECRET=your_shared_secret
pip install listing-radar
```

Both halves are required. Etsy's `x-api-key` header value is
`keystring:shared_secret`; a bare keystring returns 403.

Responses are cached to `~/.cache/listing-radar` for seven days. Rate limits are
per key, so this is a requirement rather than an optimisation.

## What this replaces

eRank, Marmalade, and Alura charge roughly $20–50 a month for demand estimates.
This infers them from the same public data, for free.

## Related

I also build finished tools for solo sellers at
[listingresearchos.com](https://listingresearchos.com) — one-time purchase,
no subscription. The difference is that those are products for running a shop;
this is the research layer, and it is free.

## License

MIT.
````

- [ ] **Step 3: Write the pre-publication checklist**

Create `docs/PRE-PUBLISH.md`:

```markdown
# Pre-publication checklist

Do not push this repository publicly until every box is checked.

- [ ] Read Etsy's current API terms of use and developer policy. This tool
      encourages third parties to use their own keys; confirm that distributing
      an open-source client is permitted and that nothing in the README implies
      Etsy endorsement.
- [ ] Read Etsy's trademark policy. The repository is named `listing-radar`
      specifically to keep the mark out of the name; confirm that describing it
      as "for Etsy sellers" is acceptable use.
- [ ] Run a secret scan over the full history, not just the working tree:
      `gitleaks detect --source . --log-opts="--all"`
- [ ] Confirm no fixture contains a real shop id, listing id, or shop name.
- [ ] Confirm `.gitignore` covers `.env`, `cache/`, `data/`, `*.json` artifacts.
- [ ] Confirm `python3 -m pytest -q` passes from a clean clone.
- [ ] Confirm the read-only guarantee: `python3 -m pytest tests/test_client.py::test_source_tree_contains_no_write_calls`
- [ ] Set the repository homepage field to `https://listingresearchos.com`.
- [ ] Set the repository description to "Demand research for Etsy sellers, from
      public listing data".
```

- [ ] **Step 4: Verify the gitignore and the full suite**

Run: `cat .gitignore && python3 -m pytest -q`
Expected: `.gitignore` lists `.env`, `cache/`, `data/`, `*.json`; all tests pass

- [ ] **Step 5: Commit**

```bash
git add README.md LICENSE docs/PRE-PUBLISH.md
git commit -m "$(cat <<'EOF'
docs: README, MIT license, and pre-publication checklist

README opens with the author's own shop as the counterexample, states the
formulas are unvalidated heuristics, and puts the app-key friction before the
install instructions rather than after.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
)"
```

---

## Self-review notes

**Spec coverage.** All four commands have tasks (5–8). Read-only enforcement is
Task 4's source-scanning test. The `original_creation_timestamp` requirement is
Task 3's regression test. The credential-error requirement is Task 1. The
relevance-search caveat is Task 7. Positioning, license, and the Etsy-terms
pre-flight are Task 9.

**Correction to the spec.** The spec described a three-way `rank` verdict. The
source implementation has four — `TOP100` is the case where the listing ranks
fine and the problem lies elsewhere. The plan implements all four; the spec's
table should be updated to match.

**Deferred from the spec.** Price and currency conversion are omitted from v1
and recorded as a global constraint rather than silently dropped.
