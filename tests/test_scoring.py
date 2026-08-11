import math
import pytest
from listing_radar import scoring


def test_median_of_even_length_averages_middle_two():
    assert scoring.median([1.0, 2.0, 3.0, 4.0]) == 2.5


def test_median_of_empty_is_zero():
    assert scoring.median([]) == 0.0


def test_views_per_day_never_divides_by_less_than_one_day():
    assert scoring.views_per_day(100, 0.0) == 100.0
    assert scoring.views_per_day(100, 10.0) == 10.0


def test_winnable_saturates_at_one_for_young_rankers():
    assert scoring.winnable(50.0) == 1.0
    assert scoring.winnable(400.0) == 1.0


def test_winnable_penalises_entrenched_rankers():
    assert scoring.winnable(800.0) == pytest.approx(0.5)


def test_opportunity_matches_the_carried_over_formula():
    expected = 12.0 / math.log10(500 + 10) * 0.8
    assert scoring.opportunity(12.0, 500, 0.8) == pytest.approx(expected)


def test_opportunity_is_zero_when_there_is_no_demand():
    assert scoring.opportunity(0.0, 500, 1.0) == 0.0


def test_thin_result_set_is_no_market_even_when_we_rank_first():
    assert scoring.rank_verdict(1, 12) == "NO MARKET"


def test_competition_exactly_at_no_market_below_is_not_no_market():
    """NO_MARKET_BELOW is a strict lower bound (`competition < no_market_below`
    in rank_verdict, `NO_MARKET_BELOW <= competition` in niche's room gate) —
    the boundary value itself counts as a market. It is read by demand.py,
    niche.py, and scoring.py, making it the most load-bearing constant in the
    tool, and its exact boundary had no test."""
    assert scoring.rank_verdict(1, scoring.NO_MARKET_BELOW) != "NO MARKET"
    assert scoring.rank_verdict(None, scoring.NO_MARKET_BELOW) == "ABSENT"


def test_not_found_in_a_real_market_is_absent():
    assert scoring.rank_verdict(None, 5000) == "ABSENT"


def test_position_within_first_hundred_is_top100():
    assert scoring.rank_verdict(100, 5000) == "TOP100"


def test_position_past_first_hundred_is_buried():
    assert scoring.rank_verdict(101, 5000) == "BURIED"
