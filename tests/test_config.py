import pytest
from listing_radar import config


def test_credentials_joins_keystring_and_secret(monkeypatch):
    monkeypatch.setenv("ETSY_KEYSTRING", "abc123")
    monkeypatch.setenv("ETSY_SHARED_SECRET", "s3cret")
    assert config.credentials() == "abc123:s3cret"


def test_missing_secret_names_the_actual_cause(monkeypatch):
    monkeypatch.setenv("ETSY_KEYSTRING", "abc123")
    monkeypatch.delenv("ETSY_SHARED_SECRET", raising=False)
    with pytest.raises(config.MissingCredentials) as e:
        config.credentials()
    assert "ETSY_SHARED_SECRET" in str(e.value)
    assert "keystring:shared_secret" in str(e.value)


def test_missing_keystring_is_not_reported_as_a_secret_problem(monkeypatch):
    monkeypatch.delenv("ETSY_KEYSTRING", raising=False)
    monkeypatch.setenv("ETSY_SHARED_SECRET", "s3cret")
    with pytest.raises(config.MissingCredentials) as e:
        config.credentials()
    assert "ETSY_KEYSTRING" in str(e.value)


def test_scoped_variables_win_over_the_plain_ones(monkeypatch):
    """Etsy issues one key per Application, so anyone running two Etsy apps
    from one shell has a collision on the plain names. The scoped pair lets
    this tool hold its own credential without disturbing whatever else reads
    ETSY_KEYSTRING."""
    monkeypatch.setenv("ETSY_KEYSTRING", "other-app")
    monkeypatch.setenv("ETSY_SHARED_SECRET", "other-secret")
    monkeypatch.setenv("LISTING_RADAR_ETSY_KEYSTRING", "mine")
    monkeypatch.setenv("LISTING_RADAR_ETSY_SHARED_SECRET", "my-secret")
    assert config.credentials() == "mine:my-secret"


def test_plain_variables_still_work_when_no_scoped_pair_is_set(monkeypatch):
    monkeypatch.delenv("LISTING_RADAR_ETSY_KEYSTRING", raising=False)
    monkeypatch.delenv("LISTING_RADAR_ETSY_SHARED_SECRET", raising=False)
    monkeypatch.setenv("ETSY_KEYSTRING", "abc123")
    monkeypatch.setenv("ETSY_SHARED_SECRET", "s3cret")
    assert config.credentials() == "abc123:s3cret"


def test_half_a_scoped_pair_does_not_silently_mix_two_apps_credentials(monkeypatch):
    """The dangerous case: a scoped keystring with no scoped secret must not
    fall back to the other app's secret and send a mismatched pair, which
    returns a 403 that reads exactly like an unapproved app."""
    monkeypatch.setenv("ETSY_KEYSTRING", "other-app")
    monkeypatch.setenv("ETSY_SHARED_SECRET", "other-secret")
    monkeypatch.setenv("LISTING_RADAR_ETSY_KEYSTRING", "mine")
    monkeypatch.delenv("LISTING_RADAR_ETSY_SHARED_SECRET", raising=False)
    with pytest.raises(config.MissingCredentials) as e:
        config.credentials()
    assert "LISTING_RADAR_ETSY_SHARED_SECRET" in str(e.value)
