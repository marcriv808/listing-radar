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
