import ast
import pathlib
import pytest
from listing_radar.cache import Cache
from listing_radar.client import EtsyClient, QuotaExhausted

SRC = pathlib.Path(__file__).resolve().parents[1] / "src"

# Attribute names a session/requests-like object may legitimately touch.
# Anything else accessed on one — a call (`.post(`, `.patch(`, `.put(`,
# `.delete(`, `.request(`) or a bare read — is either a write verb or has no
# business being called by a read-only tool. "Session" and "headers" are
# allowed because constructing a session and reading/writing its own
# `.headers` dict (for the x-api-key header) are legitimate; "get" is the
# only HTTP verb this tool is allowed to issue.
ALLOWED_SESSION_ATTRS = {"get", "Session", "headers"}


def _flatten(node: ast.AST) -> str:
    """Render a Name/Attribute chain (e.g. `self.session`) back to a dotted
    string so it can be pattern-matched. Anything that isn't a plain
    Name/Attribute chain (a call, a subscript, ...) falls back to ast.dump,
    which will never coincidentally contain "session" or equal "requests",
    so it simply never matches — which is correct, since the object being
    called there was itself already walked and checked independently."""
    try:
        return ast.unparse(node)
    except Exception:
        return ast.dump(node)


def _looks_session_or_requests(base: str) -> bool:
    b = base.lower()
    return b == "requests" or "session" in b


def _offenders_in(root: pathlib.Path) -> list[str]:
    """Walk every .py file under `root` as an AST (not a text scan) and
    return one string per violation of the read-only contract:

    1. Any attribute access — call or bare read — on something that looks
       like a `requests` module or a `.session`-named object must use an
       attribute from ALLOWED_SESSION_ATTRS. This catches `.request(`,
       `.post(`, `.patch(`, `.put(`, `.delete(` on a session/requests object
       without also flagging unrelated methods like Cache.put (`self.cache`
       is not session/requests-like, so it is never subject to this check).
    2. An "authorization" key or attribute being set — as a subscript
       assignment (`x.headers["authorization"] = ...`), a dict literal key
       (`headers={"Authorization": ...}`), an attribute assignment
       (`x.Authorization = ...`), or a call keyword argument — is flagged
       regardless of what the surrounding object is named. This is
       deliberately independent of check 1's session/requests heuristic: a
       header dict aliased to an unrelated-looking name (e.g. `s`) still
       gets caught, because the match is on the key/attribute text, matched
       case-insensitively, not on the variable it lives on.
    """
    offenders = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                base = _flatten(node.value)
                if _looks_session_or_requests(base) and node.attr not in ALLOWED_SESSION_ATTRS:
                    offenders.append(
                        f"{path.name}:{node.lineno}: {base}.{node.attr}( — "
                        f"not in the allowed attribute set {sorted(ALLOWED_SESSION_ATTRS)}"
                    )
                if node.attr.lower() == "authorization" and isinstance(node.ctx, ast.Store):
                    offenders.append(
                        f"{path.name}:{node.lineno}: attribute assignment "
                        f".{node.attr} sets an authorization header"
                    )

            if isinstance(node, ast.Subscript):
                slice_node = node.slice
                if (isinstance(slice_node, ast.Constant)
                        and isinstance(slice_node.value, str)
                        and slice_node.value.lower() == "authorization"
                        and isinstance(node.ctx, ast.Store)):
                    offenders.append(
                        f"{path.name}:{node.lineno}: subscript assignment "
                        f"keyed {slice_node.value!r} sets an authorization header"
                    )

            if isinstance(node, ast.Dict):
                for key in node.keys:
                    if (isinstance(key, ast.Constant) and isinstance(key.value, str)
                            and key.value.lower() == "authorization"):
                        offenders.append(
                            f"{path.name}:{node.lineno}: dict literal keyed "
                            f"{key.value!r} sets an authorization header"
                        )

            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if kw.arg and kw.arg.lower() == "authorization":
                        offenders.append(
                            f"{path.name}:{node.lineno}: keyword argument "
                            f"{kw.arg!r} sets an authorization header"
                        )
    return offenders


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
    a design break, not a feature, so the test scans the source itself.

    This is an AST walk, not a text/substring scan. A prior version banned
    nine literal substrings (e.g. "session.post", "Authorization") and a
    whole-branch review broke it three different ways in one sitting: calling
    `.request(` directly (not in the banned list at all), aliasing the
    session to a name that doesn't literally contain "session" before
    calling a banned verb, and setting a header keyed "authorization" in
    lowercase (case-sensitive match missed it). Parsing the source and
    reasoning about what each Attribute/Call/Dict/Subscript node actually
    does closes all three: see _offenders_in's docstring for exactly what it
    checks and why."""
    assert _offenders_in(SRC) == []
