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
