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
