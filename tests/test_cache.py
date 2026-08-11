from listing_radar.cache import Cache


def test_put_then_get_round_trips(tmp_path):
    c = Cache(tmp_path)
    c.put("/listings/active", {"keywords": "x"}, {"count": 3})
    assert c.get("/listings/active", {"keywords": "x"}) == {"count": 3}
    assert c.hits == 1


def test_different_params_are_different_entries(tmp_path):
    c = Cache(tmp_path)
    c.put("/listings/active", {"keywords": "x"}, {"count": 3})
    assert c.get("/listings/active", {"keywords": "y"}) is None


def test_param_order_does_not_change_the_key(tmp_path):
    c = Cache(tmp_path)
    c.put("/x", {"a": 1, "b": 2}, {"ok": True})
    assert c.get("/x", {"b": 2, "a": 1}) == {"ok": True}


def test_expired_entry_is_a_miss(tmp_path):
    c = Cache(tmp_path, ttl_seconds=0)
    c.put("/x", {}, {"ok": True})
    assert c.get("/x", {}) is None


def test_corrupt_cache_entry_is_a_miss_not_a_crash(tmp_path):
    c = Cache(tmp_path)
    c.put("/x", {}, {"ok": True})
    assert list(tmp_path.glob("*.tmp")) == []  # put() leaves no temp file behind
    cached_file = next(tmp_path.glob("*.json"))
    cached_file.write_text("{not valid json")  # simulate a truncated write
    assert c.get("/x", {}) is None
    assert c.hits == 0
