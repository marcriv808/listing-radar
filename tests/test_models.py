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
