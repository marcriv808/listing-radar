"""demand <phrase> — is anyone actually searching for this?

A phrase whose top rankers earn roughly zero views a day has no traffic,
however targeted it feels. That is the whole point of the command.
"""
from __future__ import annotations

from .. import scoring
from ..models import Listing


def analyse(client, phrase: str, sample: int = 100, now: float | None = None) -> dict:
    # Both ends need clamping, not just the top: an un-clamped 0 or negative
    # --sample is forwarded to Etsy verbatim and produces a 400.
    sample = max(1, min(sample, 100))
    page = client.search(phrase, limit=sample, offset=0)
    competition = page.get("count", 0)
    listings = [Listing.from_api(r, now=now) for r in page.get("results", [])]

    d = scoring.median([l.views_per_day for l in listings])
    ent = scoring.entrenchment([l.age_days for l in listings])
    win = scoring.winnable(ent)
    return {
        "phrase": phrase,
        "competition": competition,
        "sampled": len(listings),
        "demand": round(d, 2),
        "entrenchment": round(ent, 0),
        "winnable": round(win, 2),
        "opportunity": round(scoring.opportunity(d, competition, win), 2),
        "no_market": competition < scoring.NO_MARKET_BELOW,
        "api_calls": client.calls,
        "cache_hits": client.cache_hits,
    }


def render(result: dict) -> str:
    lines = [
        f"phrase        {result['phrase']}",
        f"demand        {result['demand']} median views/day of the listings ranking for it",
        f"competition   {result['competition']} active listings",
        f"entrenchment  {result['entrenchment']:.0f} days median age of the top rankers",
        f"winnable      {result['winnable']}",
        f"opportunity   {result['opportunity']}",
    ]
    if result["no_market"]:
        lines.append("")
        lines.append(
            f"NO MARKET — fewer than {scoring.NO_MARKET_BELOW} listings match this "
            f"phrase. That is an empty room, not a cheap one: nobody sells it "
            f"because nobody buys it."
        )
    lines.append("")
    lines.append(f"{result['api_calls']} API calls, {result['cache_hits']} from cache")
    return "\n".join(lines)
