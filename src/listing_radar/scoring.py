"""The four formulas, as pure functions.

Etsy publishes no search-volume API. Demand is therefore inferred from the
traction of whoever currently ranks for a phrase: every active listing exposes
lifetime views and an original creation date, so views/day is computable for
any competitor.

These are heuristics carried over unchanged from the project this was extracted
from. They have no published validation. Treat the output as a ranking signal,
not a measurement.
"""
from __future__ import annotations

import math
import statistics

# A result set thinner than this is an empty room, not a competitive loss.
NO_MARKET_BELOW = 200

# Top rankers younger than this are displaceable; older ones are entrenched.
WINNABLE_AGE_DAYS = 400.0


def median(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(statistics.median(values))


def views_per_day(views: int, age_days: float) -> float:
    return views / max(age_days, 1.0)


def entrenchment(age_days: list[float]) -> float:
    return median(age_days)


def winnable(entrenchment_days: float) -> float:
    return min(1.0, WINNABLE_AGE_DAYS / max(entrenchment_days, 1.0))


def opportunity(demand: float, competition: int, winnable_factor: float) -> float:
    return demand / math.log10(max(competition, 1) + 10) * winnable_factor


def rank_verdict(position: int | None, competition: int,
                 no_market_below: int = NO_MARKET_BELOW) -> str:
    """Zero views has three different causes and each has a different fix.

    NO MARKET is checked first and on purpose: ranking first in a room of twelve
    listings is not a win, and reporting it as TOP100 would read as success.
    """
    if competition < no_market_below:
        return "NO MARKET"
    if position is None:
        return "ABSENT"
    return "TOP100" if position <= 100 else "BURIED"
