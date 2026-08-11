"""rank <phrase> --listing <id> — why does this listing get no views?

Zero views has three very different causes and the fix differs for each:

    BURIED     it ranks, but deep      -> competitive niche, the gap is authority
    ABSENT     not in the result set   -> not actually competing for that phrase
    NO MARKET  the phrase is near-empty-> nobody sells it because nobody buys it

TOP100 is the fourth outcome: it ranks fine and the problem is elsewhere.
"""
from __future__ import annotations

from .. import scoring

DEPTH = 250  # about three pages; past this nobody is finding the listing anyway

CAVEAT = (
    "Caveat: /listings/active?keywords= is the API's relevance search, not "
    "buyer-facing Etsy search ranking. Treat position as ordinal evidence only."
)


def probe(client, phrase: str, listing_id: int, depth: int = DEPTH) -> dict:
    position = None
    competition = None
    pages = 0
    for page in range(depth // 100 + 1):
        payload = client.search(phrase, limit=100, offset=page * 100)
        if competition is None:
            competition = payload.get("count", 0)
        hits = payload.get("results", [])
        pages += 1
        for i, hit in enumerate(hits):
            if hit["listing_id"] == listing_id:
                position = page * 100 + i + 1
                break
        if position is not None or len(hits) < 100 or (page + 1) * 100 >= depth:
            break
    return {
        "phrase": phrase,
        "listing_id": listing_id,
        "position": position,
        "competition": competition or 0,
        "verdict": scoring.rank_verdict(position, competition or 0),
        "pages_fetched": pages,
        "api_calls": client.calls,
        "cache_hits": client.cache_hits,
    }


MEANING = {
    "TOP100": "It ranks. If views are still low the problem is the listing, not visibility.",
    "BURIED": "It ranks but too deep to be found. The gap is authority, not wording.",
    "ABSENT": "It does not appear at all. It is not competing for this phrase.",
    "NO MARKET": "Too few listings match. An empty room, not a cheap one.",
}


def render(result: dict) -> str:
    pos = result["position"] if result["position"] else "not found"
    return "\n".join([
        f"phrase       {result['phrase']}",
        f"listing      {result['listing_id']}",
        f"position     {pos} of {result['competition']} competitors",
        f"verdict      {result['verdict']}",
        f"             {MEANING[result['verdict']]}",
        "",
        CAVEAT,
        "",
        f"{result['api_calls']} API calls, {result['cache_hits']} from cache",
    ])
