"""Tests for feature rules, focused on leakage."""

import pandas as pd
import pytest

from src.features.build import (
    DAILY_HORIZON,
    FEATURES,
    build_daily_features,
    build_seller_features,
    build_weekly_features,
)
from src.features.common import (
    black_friday,
    brazil_holidays,
    haversine_km,
    past_totals,
    smoothed_rate,
    window_totals,
)
from src.features.make_features import validate


def dates(*values):
    return pd.Series(pd.to_datetime(list(values)))


def test_past_totals_only_counts_outcomes_known_before_the_time():
    totals = past_totals(
        dates("2018-01-10"), dates("2018-01-05", "2018-01-20"), pd.Series([1.0, 1.0])
    )
    assert totals["count"].tolist() == [1.0]


def test_past_totals_excludes_an_outcome_known_at_the_exact_time():
    totals = past_totals(dates("2018-01-10"), dates("2018-01-10"), pd.Series([1.0]))
    assert totals["count"].tolist() == [0.0]


def test_past_totals_ignores_later_changes_to_history():
    known = dates("2018-01-05", "2018-02-01")
    first = past_totals(dates("2018-01-10"), known, pd.Series([1.0, 0.0]))
    second = past_totals(dates("2018-01-10"), known, pd.Series([1.0, 999.0]))
    assert first.equals(second)


def test_past_totals_keeps_groups_apart_and_preserves_row_order():
    totals = past_totals(
        dates("2018-02-01", "2018-01-01"),
        dates("2017-12-01", "2017-12-02"),
        pd.Series([1.0, 1.0]),
        pd.Series(["a", "b"]),
        pd.Series(["a", "a"]),
    )
    assert totals["count"].tolist() == [2.0, 0.0]


def test_window_totals_drops_values_older_than_the_window():
    totals = window_totals(
        dates("2018-02-01"), 10, dates("2018-01-01", "2018-01-28"), pd.Series([5.0, 2.0])
    )
    assert totals["total"].tolist() == [2.0]


def test_smoothed_rate_stays_near_the_prior_with_little_history():
    totals = pd.DataFrame({"count": [1.0], "total": [1.0]})
    assert smoothed_rate(totals, pd.Series([0.1])).iloc[0] < 0.2


def test_haversine_km_matches_a_known_distance():
    # Sao Paulo to Rio de Janeiro is about 360 km.
    distance = haversine_km(-23.55, -46.63, -22.91, -43.17)
    assert distance == pytest.approx(360, abs=10)


def test_black_friday_2017():
    assert black_friday(2017) == pd.Timestamp("2017-11-24")


def test_brazil_holidays_includes_independence_day():
    assert pd.Timestamp("2017-09-07") in brazil_holidays([2017])


def test_daily_lags_never_use_the_forecast_window():
    days = pd.date_range("2018-01-01", periods=80, freq="D")
    daily = pd.DataFrame({"date": days, "orders": range(80), "period": "development"})
    changed = daily.copy()
    changed.loc[40:, "orders"] = 9999

    original = build_daily_features(daily)
    edited = build_daily_features(changed)
    columns = ["lag_28", "lag_35", "lag_42", "mean_7_lag_28", "mean_28_lag_28"]

    # Row 67 is the last one that can't see row 40, and row 68 is the first that can.
    last_safe = 40 + DAILY_HORIZON - 1
    pd.testing.assert_frame_equal(
        original.loc[:last_safe, columns], edited.loc[:last_safe, columns]
    )
    assert edited.loc[last_safe + 1, "lag_28"] == 9999
    assert original.loc[40, "lag_28"] == 12


def test_weekly_lags_stay_within_their_category():
    weeks = pd.date_range("2018-01-07", periods=6, freq="W-SUN")
    weekly = pd.concat(
        [
            pd.DataFrame({"week_end": weeks, "category": "a", "items": 1, "period": "development"}),
            pd.DataFrame({"week_end": weeks, "category": "b", "items": 7, "period": "development"}),
        ]
    )
    table = build_weekly_features(weekly)

    assert set(table[table["category"] == "a"]["lag_4"].dropna()) == {1}
    assert set(table[table["category"] == "b"]["lag_4"].dropna()) == {7}


def test_seller_features_ignore_sales_on_or_after_the_snapshot():
    snapshots = pd.DataFrame(
        {
            "snapshot_date": pd.to_datetime(["2018-03-01"]),
            "seller_id": ["s"],
            "is_inactive": [False],
            "seller_state": ["SP"],
            "period": ["development"],
        }
    )
    sales = pd.DataFrame(
        {
            "order_id": ["old", "same_day", "later"],
            "seller_id": ["s", "s", "s"],
            "price": [10.0, 500.0, 500.0],
            "sale_date": pd.to_datetime(["2018-02-20", "2018-03-01", "2018-03-02"]),
        }
    )
    empty_delivery = pd.DataFrame(
        {
            "outcome_date": pd.to_datetime([]),
            "is_late": pd.Series([], dtype=float),
            "seller_id": pd.Series([], dtype=str),
        }
    )
    empty_reviews = pd.DataFrame(
        {
            "score_known_date": pd.to_datetime([]),
            "is_low": pd.Series([], dtype=float),
            "seller_id": pd.Series([], dtype=str),
        }
    )

    table = build_seller_features(snapshots, sales, empty_delivery, empty_reviews)

    assert table.loc[0, "sales_90d"] == 1
    assert table.loc[0, "revenue_90d"] == 10.0
    assert table.loc[0, "days_since_last_sale"] == 9


def test_validate_rejects_a_target_used_as_a_feature(monkeypatch):
    spec = {"numeric": ["is_late"], "categorical": []}
    monkeypatch.setitem(FEATURES, "delivery", spec)
    table = pd.DataFrame({"order_id": ["a"], "is_late": [1]})

    with pytest.raises(ValueError, match="targets as features"):
        validate({"delivery": table})
