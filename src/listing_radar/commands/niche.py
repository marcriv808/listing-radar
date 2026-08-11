"""niche <phrase> — is this worth building?

Three gates, all of which must pass. The third exists because demand alone is
a trap: in the shop this tool came from, 39 of 70 listings targeted phrases
carrying 5,000-99,000 competitors and never appeared in the top 250 results
for their own lead phrase. Demand you cannot surface against is not an
opportunity, it is a trap you fall into repeatedly.
"""
from __future__ import annotations

from .. import scoring
from ..models import Listing
from . import demand as demand_cmd

# Formats a well-built alternative can beat on usability. Presence of these
# among the top rankers means the incumbent product is a document, not an app.
BEATABLE_FORMATS = (
    "spreadsheet", "google sheet", "google sheets", "excel", "xlsx",
    "pdf", "printable", "template", "canva", "notion", "worksheet",
)

MIN_DEMAND = 1.0
MAX_COMPETITION = 2000


def screen(client, phrase: str, min_demand: float = MIN_DEMAND,
           max_competition: int = MAX_COMPETITION, now: float | None = None) -> dict:
    d = demand_cmd.analyse(client, phrase, now=now)

    page = client.search(phrase, limit=100, offset=0)
    listings = [Listing.from_api(r, now=now) for r in page.get("results", [])]
    formats = sorted({
        fmt for l in listings for fmt in BEATABLE_FORMATS
        if fmt in l.title.lower()
    })

    demand_gate = d["demand"] >= min_demand
    room_gate = (scoring.NO_MARKET_BELOW <= d["competition"] <= max_competition)
    format_gate = bool(formats)

    return {
        "phrase": phrase,
        "demand_gate": demand_gate,
        "room_gate": room_gate,
        "format_gate": format_gate,
        "formats": formats,
        "passes": demand_gate and room_gate and format_gate,
        "detail": d,
    }


def render(result: dict) -> str:
    d = result["detail"]
    mark = lambda ok: "pass" if ok else "FAIL"
    lines = [
        f"phrase   {result['phrase']}",
        "",
        f"DEMAND   {mark(result['demand_gate'])}   "
        f"{d['demand']} median views/day of the rankers "
        f"(needs >= {MIN_DEMAND})",
        f"ROOM     {mark(result['room_gate'])}   "
        f"{d['competition']} competitors "
        f"(needs {scoring.NO_MARKET_BELOW}-{MAX_COMPETITION}: enough to imply a "
        f"market, few enough to place in)",
        f"FORMAT   {mark(result['format_gate'])}   "
        f"{', '.join(result['formats']) if result['formats'] else 'no beatable format among the rankers'}",
        "",
        "BUILD" if result["passes"] else "SKIP — every gate must pass.",
    ]
    return "\n".join(lines)
