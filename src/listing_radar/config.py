"""Credential loading.

Etsy rejects a bare keystring on the endpoints this tool uses with
403 {"error":"Shared secret is required in x-api-key header."}. The credential
is the pair joined by a colon. In the project this was extracted from, that 403
was mapped to a generic fallback and read for weeks as "our app is not approved
yet" — a plausible story that was wrong and undisprovable without calling Etsy
by hand. So the error here names the actual missing variable.
"""
from __future__ import annotations

import os

DOCS = "https://www.etsy.com/developers/register"


class MissingCredentials(RuntimeError):
    pass


def credentials() -> str:
    # Etsy issues one key per Application, so anyone running a second Etsy app
    # from the same shell has a collision on the plain names. If either scoped
    # variable is set, this tool uses only the scoped pair — it never mixes one
    # app's keystring with another's secret, because that combination returns
    # the same 403 as an unapproved app and is miserable to diagnose.
    prefix = "LISTING_RADAR_"
    scoped = any(os.environ.get(prefix + n, "").strip()
                 for n in ("ETSY_KEYSTRING", "ETSY_SHARED_SECRET"))
    names = [(prefix if scoped else "") + n
             for n in ("ETSY_KEYSTRING", "ETSY_SHARED_SECRET")]

    keystring = os.environ.get(names[0], "").strip()
    secret = os.environ.get(names[1], "").strip()
    missing = [n for n, v in zip(names, (keystring, secret)) if not v]
    if missing:
        raise MissingCredentials(
            f"{' and '.join(missing)} not set. Etsy needs both halves: the "
            f"x-api-key header value is keystring:shared_secret, and a bare "
            f"keystring returns 403. Register an app at {DOCS}, then export "
            f"both variables."
        )
    return f"{keystring}:{secret}"
