import time

import pytest

from listing_radar import cli, config
from listing_radar.client import QuotaExhausted


def raising_client(exc: Exception):
    """A fake EtsyClient class that raises `exc` on construction — stands in
    for the real client at the exact point main() does `client = EtsyClient()`,
    so these tests never touch the network, real credentials, or disk."""

    class RaisingClient:
        def __init__(self, *args, **kwargs):
            raise exc

    return RaisingClient


def succeeding_client():
    """A fake EtsyClient class that constructs cleanly — the happy-path
    counterpart to raising_client, for tests that need to get past
    `client = EtsyClient()` and into the dispatch logic without ever touching
    the network, real credentials, or disk."""

    class SucceedingClient:
        def __init__(self, *args, **kwargs):
            pass

    return SucceedingClient


def test_bare_runtime_error_prints_clean_error_and_exits_nonzero(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "EtsyClient",
        raising_client(RuntimeError(
            "Etsy rejected the API key. The x-api-key header must be "
            "keystring:shared_secret — a bare keystring returns 403. "
            "Check ETSY_SHARED_SECRET."
        )),
    )
    code = cli.main(["demand", "candle holder"])
    out, err = capsys.readouterr()
    assert code == 1
    assert err == (
        "error: Etsy rejected the API key. The x-api-key header must be "
        "keystring:shared_secret — a bare keystring returns 403. "
        "Check ETSY_SHARED_SECRET.\n"
    )
    assert out == ""


def test_missing_credentials_still_maps_to_its_own_exit_code(monkeypatch, capsys):
    monkeypatch.setattr(
        cli, "EtsyClient", raising_client(config.MissingCredentials("ETSY_KEYSTRING not set."))
    )
    code = cli.main(["demand", "candle holder"])
    out, err = capsys.readouterr()
    assert code == 2
    assert err == "error: ETSY_KEYSTRING not set.\n"
    assert out == ""


def test_quota_exhausted_still_maps_to_its_own_exit_code(monkeypatch, capsys):
    monkeypatch.setattr(
        cli, "EtsyClient", raising_client(QuotaExhausted("Etsy daily quota is gone."))
    )
    code = cli.main(["demand", "candle holder"])
    out, err = capsys.readouterr()
    assert code == 3
    assert err == "error: Etsy daily quota is gone.\n"
    assert out == ""


def test_non_numeric_target_fails_cleanly_not_with_a_traceback(monkeypatch, capsys):
    """A typo'd listing id must not escape main() as a raw ValueError — it
    should fail the same clean way argparse already fails a bad --sample."""
    monkeypatch.setattr(cli, "EtsyClient", succeeding_client())
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["traction", "not-a-number"])
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert err.strip() != ""


def test_non_numeric_shop_target_fails_cleanly_not_with_a_traceback(monkeypatch, capsys):
    """Same defect, shop: form — shop:abc must not escape as a traceback either."""
    monkeypatch.setattr(cli, "EtsyClient", succeeding_client())
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["traction", "shop:abc"])
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert err.strip() != ""


@pytest.mark.parametrize("depth", ["-50", "0"])
def test_non_positive_depth_is_rejected_before_any_client_is_constructed(monkeypatch, capsys, depth):
    """range(depth // 100 + 1) silently becomes range(0) for depth < 1, so
    rank.probe() would return a confident NO MARKET verdict from zero API
    calls. --depth must be rejected by argparse — the same clean-exit-2
    pattern as a typo'd traction target — before EtsyClient is even
    constructed."""
    monkeypatch.setattr(cli, "EtsyClient", succeeding_client())
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["rank", "x", "--listing", "1", "--depth", depth])
    assert exc_info.value.code == 2
    err = capsys.readouterr().err
    assert "Traceback" not in err
    assert "--depth must be" in err


def patched_traction(monkeypatch):
    """Patch EtsyClient to construct cleanly and spy on traction.for_listing /
    traction.for_shop, so routing can be asserted on without a real client or
    a render()-shaped result dict. Returns the list calls get recorded into."""
    monkeypatch.setattr(cli, "EtsyClient", succeeding_client())
    calls = []

    def fake_for_listing(client, listing_id):
        calls.append(("listing", listing_id))
        return {"kind": "listing"}

    def fake_for_shop(client, shop_id):
        calls.append(("shop", shop_id))
        return {"kind": "shop"}

    monkeypatch.setattr(cli.traction, "for_listing", fake_for_listing)
    monkeypatch.setattr(cli.traction, "for_shop", fake_for_shop)
    monkeypatch.setattr(cli.traction, "render", lambda result: "")
    return calls


def test_numeric_target_routes_to_for_listing(monkeypatch):
    calls = patched_traction(monkeypatch)
    code = cli.main(["traction", "12345"])
    assert code == 0
    assert calls == [("listing", 12345)]


def test_shop_prefixed_target_routes_to_for_shop(monkeypatch):
    calls = patched_traction(monkeypatch)
    code = cli.main(["traction", "shop:678"])
    assert code == 0
    assert calls == [("shop", 678)]


def fake_client(search_result=None, listing_result=None, shop_result=None):
    """A fake EtsyClient class that returns fixture-shaped payloads instead
    of just constructing cleanly — unlike succeeding_client, this lets the
    real analyse/screen/probe/for_listing/for_shop -> render path actually
    run end to end, so what lands on stdout is what a real invocation would
    print. No network, no real credentials, no disk: EtsyClient itself is
    replaced, so config.credentials() and the real Cache are never reached."""

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.calls = 0
            self.cache_hits = 0

        def search(self, keywords, limit=100, offset=0):
            self.calls += 1
            return search_result

        def listing(self, listing_id):
            self.calls += 1
            return listing_result

        def shop(self, shop_id):
            self.calls += 1
            return shop_result

    return FakeClient


def test_demand_command_prints_the_rendered_report_and_exits_zero(monkeypatch, capsys):
    now = time.time()
    rows = [{"listing_id": 1000000001, "shop_id": 2000000001, "title": "Freelance Tracker",
             "views": 900, "num_favorers": 10,
             "original_creation_timestamp": now - 100 * 86400}]
    monkeypatch.setattr(cli, "EtsyClient",
                        fake_client(search_result={"count": 5000, "results": rows}))

    code = cli.main(["demand", "freelance tracker"])
    out, err = capsys.readouterr()

    assert code == 0
    assert err == ""
    assert "phrase        freelance tracker" in out
    assert "demand        9.0" in out
    assert "winnable" in out
    assert "1 API calls, 0 from cache" in out


def test_traction_command_prints_the_rendered_report_and_exits_zero(monkeypatch, capsys):
    now = time.time()
    row = {"listing_id": 1000000002, "shop_id": 2000000001, "title": "Ceramic Mug",
           "views": 900, "num_favorers": 45,
           "original_creation_timestamp": now - 100 * 86400}
    monkeypatch.setattr(cli, "EtsyClient",
                        fake_client(listing_result={"results": [row]}))

    code = cli.main(["traction", "1000000002"])
    out, err = capsys.readouterr()

    assert code == 0
    assert err == ""
    assert "listing        Ceramic Mug" in out
    assert "views/day      9.0" in out
    assert "1 API calls, 0 from cache" in out


def test_rank_command_prints_the_rendered_report_and_exits_zero(monkeypatch, capsys):
    hits = [{"listing_id": i} for i in range(1, 4)]
    monkeypatch.setattr(cli, "EtsyClient",
                        fake_client(search_result={"count": 5000, "results": hits}))

    code = cli.main(["rank", "estate executor checklist", "--listing", "2"])
    out, err = capsys.readouterr()

    assert code == 0
    assert err == ""
    assert "position     2 of 5000 competitors" in out
    assert "verdict      TOP100" in out
    assert cli.rank.CAVEAT in out
    assert "1 API calls, 0 from cache" in out


def test_niche_command_prints_the_rendered_report_and_exits_zero(monkeypatch, capsys):
    now = time.time()
    rows = [{"listing_id": i, "shop_id": 2000000001,
             "title": "Budget Spreadsheet Google Sheets", "views": 900,
             "num_favorers": 0, "original_creation_timestamp": now - 100 * 86400}
            for i in range(1, 6)]
    monkeypatch.setattr(cli, "EtsyClient",
                        fake_client(search_result={"count": 400, "results": rows}))

    code = cli.main(["niche", "budget spreadsheet"])
    out, err = capsys.readouterr()

    assert code == 0
    assert err == ""
    assert "DEMAND   pass" in out
    assert "ROOM     pass" in out
    assert "FORMAT   pass" in out
    assert out.strip().split("\n")[-3] == "BUILD"
    assert "2 API calls, 0 from cache" in out
