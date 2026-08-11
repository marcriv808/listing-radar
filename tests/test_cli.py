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
