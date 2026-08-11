"""traction <shop|listing> — how well is this competitor really doing?

Lifetime views plus an original creation date gives views/day for any active
listing. Shops additionally expose transaction_sold_count and a create date,
which gives sales/day. None of this requires the competitor's permission; it
is all public on the app key.
"""
from __future__ import annotations

import time

from ..models import Listing


def for_listing(client, listing_id: int, now: float | None = None) -> dict:
    payload = client.listing(listing_id)
    rows = payload.get("results") or [payload]
    listing = Listing.from_api(rows[0], now=now)
    return {
        "kind": "listing",
        "listing_id": listing.listing_id,
        "title": listing.title,
        "views": listing.views,
        "favorers": listing.favorers,
        "age_days": round(listing.age_days, 1),
        "views_per_day": round(listing.views_per_day, 2),
        "fav_rate": round(listing.fav_rate * 100, 2),
    }


def for_shop(client, shop_id: int, now: float | None = None) -> dict:
    now = time.time() if now is None else now
    s = client.shop(shop_id)
    created = s.get("create_date") or s.get("created_timestamp") or now
    age_days = max((now - created) / 86400.0, 1.0)
    sold = s.get("transaction_sold_count") or 0
    return {
        "kind": "shop",
        "shop_id": s.get("shop_id", shop_id),
        "shop_name": s.get("shop_name", ""),
        "sold": sold,
        "age_days": round(age_days, 1),
        "sales_per_day": round(sold / age_days, 3),
    }


def render(result: dict) -> str:
    if result["kind"] == "shop":
        return "\n".join([
            f"shop           {result['shop_name']} ({result['shop_id']})",
            f"sold           {result['sold']} lifetime transactions",
            f"age            {result['age_days']:.0f} days",
            f"sales/day      {result['sales_per_day']}",
        ])
    return "\n".join([
        f"listing        {result['title'][:60]} ({result['listing_id']})",
        f"views          {result['views']} lifetime",
        f"age            {result['age_days']:.0f} days"
        f"   (original creation date, not the last renewal)",
        f"views/day      {result['views_per_day']}",
        f"favourite rate {result['fav_rate']}%",
    ])
