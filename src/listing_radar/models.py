"""The one listing shape this tool reads.

Only the fields the four commands actually use. Price is deliberately absent:
Etsy returns each listing in the seller's own currency, and taking a median
across mixed currencies silently produces a wrong number.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from . import scoring


@dataclass
class Listing:
    listing_id: int
    shop_id: int
    title: str
    views: int
    favorers: int
    age_days: float
    views_per_day: float
    fav_rate: float
    url: str = ""
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_api(cls, row: dict, now: float | None = None) -> "Listing":
        now = time.time() if now is None else now
        # original_creation_timestamp, never creation_timestamp — see the
        # regression test in tests/test_models.py for why this matters.
        created = row.get("original_creation_timestamp") or now
        age_days = max((now - created) / 86400.0, 1.0)
        views = row.get("views") or 0
        favorers = row.get("num_favorers") or 0
        return cls(
            listing_id=row["listing_id"],
            shop_id=row.get("shop_id", 0),
            title=row.get("title", ""),
            views=views,
            favorers=favorers,
            age_days=age_days,
            views_per_day=scoring.views_per_day(views, age_days),
            fav_rate=(favorers / views if views else 0.0),
            url=row.get("url", ""),
            tags=row.get("tags") or [],
        )
