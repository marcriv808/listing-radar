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
