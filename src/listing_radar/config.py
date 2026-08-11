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
    keystring = os.environ.get("ETSY_KEYSTRING", "").strip()
    secret = os.environ.get("ETSY_SHARED_SECRET", "").strip()
    missing = [n for n, v in (("ETSY_KEYSTRING", keystring),
                              ("ETSY_SHARED_SECRET", secret)) if not v]
    if missing:
        raise MissingCredentials(
            f"{' and '.join(missing)} not set. Etsy needs both halves: the "
            f"x-api-key header value is keystring:shared_secret, and a bare "
            f"keystring returns 403. Register an app at {DOCS}, then export "
            f"both variables."
        )
    return f"{keystring}:{secret}"
