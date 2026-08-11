"""First-run acceptance of the Application Terms.

Etsy's API Terms §3 require the developer to enter into terms with the
Application's users, "accept[ed] ... in a manner that is legally enforceable,
including but not limited to a click-through or equivalent user experience."

A CLI has no install-time prompt, and a LICENSE file or a README section is not
acceptance — nobody has to read either to run the tool. The equivalent here is
an explicit affirmative command (`listing-radar accept-terms`) that every other
command refuses to run without. A passive notice printed on first use would not
satisfy the requirement, so the gate blocks rather than warns.

Acceptance is recorded per terms version, on the user's own machine, and
nothing about it leaves the machine.
"""
from __future__ import annotations

import datetime
import json
import pathlib

VERSION = 1
MARKER = "accepted-terms.json"
DOC_URL = "https://github.com/marcriv808/listing-radar/blob/main/TERMS.md"


def accepted(root: pathlib.Path) -> bool:
    """True only when this exact terms version was affirmatively accepted.

    Every failure mode returns False. Consent has to be affirmative, so a
    truncated write, a hand-edited file, or an acceptance of an older version
    all mean "ask again" rather than "close enough".
    """
    try:
        payload = json.loads((pathlib.Path(root) / MARKER).read_text())
    except (OSError, json.JSONDecodeError):
        return False
    return payload.get("version") == VERSION


def accept(root: pathlib.Path) -> None:
    root = pathlib.Path(root)
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": VERSION,
        "accepted_at": datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
    }
    # Atomic, for the same reason the cache is: a Ctrl-C mid-write must not
    # leave a half-written marker. A corrupt marker fails closed above, so the
    # cost is a re-prompt rather than a wrong grant, but re-prompting a user
    # who already accepted is still a bug.
    p = root / MARKER
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(payload))
    tmp.replace(p)


def notice() -> str:
    return (
        f"Before first use, please read and accept the terms (version {VERSION}).\n"
        f"\n"
        f"  TERMS.md in this repository, or\n"
        f"  {DOC_URL}\n"
        f"\n"
        f"They are short. In summary: this tool runs entirely on your machine\n"
        f"using your own Etsy API key, sends nothing anywhere except to Etsy,\n"
        f"never writes to any shop, and has no telemetry. Its scoring formulas\n"
        f"are unvalidated heuristics — do not treat the output as advice.\n"
        f"\n"
        f"Accept with:\n"
        f"\n"
        f"  listing-radar accept-terms\n"
    )
