import pytest
from listing_radar.commands import demand

NOW = 1700000000 + 100 * 86400


class FakeClient:
    def __init__(self, count, rows, cache_hits=0):
        self._count, self._rows = count, rows
        self.calls = 0
        self.cache_hits = cache_hits
        self.last_limit = None

    def search(self, keywords, limit=100, offset=0):
        self.calls += 1
        self.last_limit = limit
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


def test_render_prints_winnable():
    """winnable is returned by analyse() and documented in the README's
    formula, but render() never printed it — a pure oversight."""
    client = FakeClient(5000, [row(1, 900, age_days=100)])
    result = demand.analyse(client, "x", now=NOW)
    text = demand.render(result)
    assert f"winnable      {result['winnable']}" in text


def test_render_includes_the_api_calls_and_cache_hits_footer():
    # analyse() makes exactly one client.search() call; the fake increments
    # client.calls itself, exactly as the real EtsyClient does, so the
    # footer reflects the real call it made — not a value stuffed into the
    # result dict by the test.
    client = FakeClient(5000, [row(1, 900)], cache_hits=1)
    result = demand.analyse(client, "x", now=NOW)
    text = demand.render(result)
    assert "1 API calls, 1 from cache" in text


@pytest.mark.parametrize("requested,expected_limit", [(0, 1), (-5, 1), (500, 100), (40, 40)])
def test_sample_is_clamped_at_both_ends(requested, expected_limit):
    """--sample 0 or a negative value used to be forwarded to Etsy verbatim
    (min(sample, 100) only clamped the top), producing a 400. Both ends must
    be clamped locally before the request is made."""
    client = FakeClient(5000, [row(1, 900)])
    demand.analyse(client, "x", sample=requested, now=NOW)
    assert client.last_limit == expected_limit
