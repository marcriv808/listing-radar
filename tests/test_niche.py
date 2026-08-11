from listing_radar.commands import niche

NOW = 1700000000 + 100 * 86400


class FakeClient:
    def __init__(self, count, rows, cache_hits=0):
        self._count, self._rows = count, rows
        self.calls = 0
        self.cache_hits = cache_hits

    def search(self, keywords, limit=100, offset=0):
        self.calls += 1
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


def test_render_names_the_overridden_thresholds_not_the_defaults():
    """Regression test for the critical whole-branch-review finding: screen()
    computed its gates from the min_demand/max_competition arguments, but
    render() interpolated the MIN_DEMAND/MAX_COMPETITION module constants —
    so a caller who overrode the thresholds got a report that named the
    defaults while having applied something else entirely. Demand 9.0 against
    a threshold of 1.0 (the default) reads as a pass; against an overridden
    threshold of 50.0 it must read, and be reported, as a FAIL. Likewise
    competition 400 is inside the default 200-2000 room window but outside an
    overridden 200-300 window."""
    rows = [row(i, 900, "Budget Spreadsheet Google Sheets") for i in range(1, 6)]
    result = niche.screen(FakeClient(400, rows), "budget spreadsheet", now=NOW,
                           min_demand=50.0, max_competition=300)
    text = niche.render(result)

    assert result["demand_gate"] is False
    assert result["room_gate"] is False

    # The rendered text must name the overridden thresholds (50.0 and 300),
    # never the module defaults (niche.MIN_DEMAND == 1.0, niche.MAX_COMPETITION == 2000).
    assert "needs >= 50.0" in text
    assert "needs >= 1.0" not in text
    assert "200-300" in text
    assert "200-2000" not in text
    assert "DEMAND   FAIL" in text
    assert "ROOM     FAIL" in text


def test_render_includes_the_api_calls_and_cache_hits_footer():
    # screen() calls client.search() twice: once inside the nested
    # demand_cmd.analyse(), once directly for format detection. The footer
    # must reflect the total, read from the client after both calls.
    rows = [row(i, 900, "Budget Spreadsheet Google Sheets") for i in range(1, 6)]
    client = FakeClient(400, rows, cache_hits=1)
    text = niche.render(niche.screen(client, "budget spreadsheet", now=NOW))
    assert "2 API calls, 1 from cache" in text
