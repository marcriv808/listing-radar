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
