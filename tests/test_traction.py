import pytest
from listing_radar.commands import traction

NOW = 1700000000 + 100 * 86400


class FakeClient:
    def __init__(self, listing=None, shop=None, cache_hits=0, listing_payload=None):
        self._listing, self._shop = listing, shop
        # listing_payload lets a test hand back the raw envelope exactly as
        # Etsy would (e.g. {"results": []}) instead of the auto-wrapped
        # {"results": [listing]} shape every other test here relies on.
        self._listing_payload = listing_payload
        self.calls = 0
        self.cache_hits = cache_hits

    def listing(self, listing_id):
        self.calls += 1
        if self._listing_payload is not None:
            return self._listing_payload
        return {"results": [self._listing]}

    def shop(self, shop_id):
        self.calls += 1
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


def test_empty_results_envelope_raises_a_clean_error_not_a_keyerror():
    """`payload.get("results") or [payload]` used to trigger its fallback on
    {"results": []} too (an empty list is falsy), handing the envelope
    itself to Listing.from_api and raising an uncatchable
    KeyError: 'listing_id' — the only uncaught exception class in the app,
    since cli.main() only catches MissingCredentials/QuotaExhausted/
    RuntimeError."""
    client = FakeClient(listing_payload={"results": []})
    with pytest.raises(RuntimeError, match="listing 1 returned no data"):
        traction.for_listing(client, 1, now=NOW)


def test_unwrapped_payload_missing_listing_id_raises_a_clean_error():
    """A genuinely unwrapped payload (no "results" key at all) still needs a
    "listing_id" to be usable. If it's missing, that must fail the same
    clean way as the empty-results case, not with a raw KeyError."""
    client = FakeClient(listing_payload={"shop_id": 2, "views": 10})
    with pytest.raises(RuntimeError, match="listing 1 returned no data"):
        traction.for_listing(client, 1, now=NOW)


def test_render_includes_the_api_calls_and_cache_hits_footer_for_listing():
    row = {"listing_id": 1, "shop_id": 2, "title": "t", "views": 900,
           "num_favorers": 45,
           "original_creation_timestamp": NOW - 100 * 86400}
    client = FakeClient(listing=row, cache_hits=1)
    text = traction.render(traction.for_listing(client, 1, now=NOW))
    assert "1 API calls, 1 from cache" in text


def test_render_includes_the_api_calls_and_cache_hits_footer_for_shop():
    shop = {"shop_id": 2, "shop_name": "Example", "transaction_sold_count": 1,
            "create_date": NOW - 10 * 86400}
    client = FakeClient(shop=shop, cache_hits=2)
    text = traction.render(traction.for_shop(client, 2, now=NOW))
    assert "1 API calls, 2 from cache" in text
