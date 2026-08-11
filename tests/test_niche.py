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
