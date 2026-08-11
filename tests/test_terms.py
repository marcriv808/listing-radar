import json
import pathlib

import pytest

from listing_radar import terms


def test_not_accepted_when_no_marker_exists(tmp_path):
    assert terms.accepted(tmp_path) is False


def test_accept_records_the_version_and_is_then_accepted(tmp_path):
    terms.accept(tmp_path)
    assert terms.accepted(tmp_path) is True

    payload = json.loads((tmp_path / terms.MARKER).read_text())
    assert payload["version"] == terms.VERSION
    assert payload["accepted_at"]


def test_a_new_terms_version_invalidates_a_previous_acceptance(tmp_path):
    """Etsy's API Terms §3 require the user to accept the Application Terms.
    An acceptance of v1 is not an acceptance of v2, so a version bump must
    re-prompt rather than silently carry the old consent forward."""
    terms.accept(tmp_path)
    (tmp_path / terms.MARKER).write_text(
        json.dumps({"version": terms.VERSION - 1, "accepted_at": "2020-01-01T00:00:00Z"})
    )
    assert terms.accepted(tmp_path) is False


def test_a_corrupt_marker_is_treated_as_not_accepted(tmp_path):
    """Failing open here would mean a truncated write silently counts as
    consent. Consent must be affirmative, so an unreadable marker means no."""
    (tmp_path / terms.MARKER).write_text("{not json")
    assert terms.accepted(tmp_path) is False


def test_marker_without_a_version_field_is_not_acceptance(tmp_path):
    (tmp_path / terms.MARKER).write_text(json.dumps({"accepted_at": "2026-01-01T00:00:00Z"}))
    assert terms.accepted(tmp_path) is False


def test_accept_is_idempotent(tmp_path):
    terms.accept(tmp_path)
    first = (tmp_path / terms.MARKER).read_text()
    terms.accept(tmp_path)
    assert terms.accepted(tmp_path) is True
    assert json.loads(first)["version"] == terms.VERSION


def test_notice_names_the_command_and_the_terms_file():
    text = terms.notice()
    assert "accept-terms" in text
    assert "TERMS.md" in text
    assert str(terms.VERSION) in text


def test_shipped_terms_file_version_matches_the_code():
    """The file users read and the version the code records must not drift —
    otherwise someone accepts v1 while reading v2."""
    doc = pathlib.Path(__file__).resolve().parent.parent / "TERMS.md"
    assert f"**Version {terms.VERSION}**" in doc.read_text()


def test_shipped_terms_file_carries_the_required_etsy_disclaimers():
    """API Terms §3 requires a warranty disclaimer naming the developer, and
    §1 requires the trademark statement verbatim."""
    doc = (pathlib.Path(__file__).resolve().parent.parent / "TERMS.md").read_text()
    collapsed = " ".join(doc.split())
    assert "ETSY, INC. AND ITS AFFILIATES ARE NOT THE APPLICATION DEVELOPER" in collapsed
    assert (
        "The term 'Etsy' is a trademark of Etsy, Inc. This Application uses "
        "Etsy's API, but is not endorsed or certified by Etsy." in collapsed
    )
