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


def test_503_then_200_retries_once_and_returns_the_payload(tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr("listing_radar.client.time.sleep", sleeps.append)
    session = FakeSession([FakeResponse(503), FakeResponse(200, {"count": 1})])
    c = EtsyClient(cache=Cache(tmp_path), session=session)
    assert c.get("/listings/active", keywords="x") == {"count": 1}
    assert c.calls == 2
    assert sleeps == [1]


def test_four_consecutive_failures_exhausts_retries_without_a_final_sleep(tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr("listing_radar.client.time.sleep", sleeps.append)
    session = FakeSession([FakeResponse(503)] * 4)
    c = EtsyClient(cache=Cache(tmp_path), session=session)
    with pytest.raises(RuntimeError, match="retries exhausted"):
        c.get("/listings/active", keywords="x")
    assert sleeps == [1, 2, 4]


def test_source_tree_contains_no_write_calls():
    """This tool is read-only by construction. If a write ever lands here it is
    a design break, not a feature, so the test scans the source itself."""
    # Scoped to HTTP verbs on a requests object plus the auth header. A bare
    # ".put(" would match the cache's own put() and fail on correct code.
    banned = ("requests.post", "requests.patch", "requests.put",
              "requests.delete", "session.post", "session.patch",
              "session.put", "session.delete", "Authorization")
    offenders = []
    for path in SRC.rglob("*.py"):
        text = path.read_text()
        for token in banned:
            if token in text:
                offenders.append(f"{path.name}: {token}")
    assert offenders == []
