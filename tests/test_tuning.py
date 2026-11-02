"""Tests for tuned models, alert cutoffs, and Black Friday handling."""

import numpy as np
import pandas as pd
import pytest

from src.features.build import build_daily_features, build_weekly_features
from src.features.common import peak_window_days
from src.models.baselines import PROBLEMS, usable_rows
from src.models.tune import forward_alert_results, forward_promise_results
from src.models.tuned import SMALL_TABLE_SPACE, TUNING, make_predictor, sample_settings

SMALL_TREE = {
    "learning_rate": 0.1,
    "max_iter": 20,
    "max_leaf_nodes": 3,
    "min_samples_leaf": 2,
    "l2_regularization": 0.0,
}


def freight_rows(count, category="a"):
    rng = np.random.default_rng(0)
    distance = rng.uniform(1, 100, count)
    return pd.DataFrame(
        {
            "distance_km": distance,
            "same_state": rng.integers(0, 2, count),
            "product_weight_g": rng.uniform(1, 100, count),
            "volume_cm3": rng.uniform(1, 100, count),
            "longest_side_cm": rng.uniform(1, 100, count),
            "price": rng.uniform(1, 100, count),
            "quantity": 1,
            "customer_state": "SP",
            "seller_state": "RJ",
            "category": category,
            "freight_value": distance,
        }
    )


def test_sample_settings_is_repeatable():
    assert sample_settings(SMALL_TABLE_SPACE) == sample_settings(SMALL_TABLE_SPACE)
    assert len(sample_settings(SMALL_TABLE_SPACE)) == 8


def test_every_problem_has_a_tuning_space():
    assert set(TUNING) == {problem.name for problem in PROBLEMS}


def test_make_predictor_rejects_an_unknown_family():
    with pytest.raises(ValueError, match="Unknown model family"):
        make_predictor("mystery", "freight", {})


def test_boosted_median_handles_missing_values_and_unseen_categories():
    train = freight_rows(100)
    valid = freight_rows(5, category="never_seen")
    valid.loc[0, "distance_km"] = np.nan

    predicted = make_predictor("boosted_median", "freight", SMALL_TREE)(
        train, valid, "freight_value"
    )

    assert len(predicted) == 5
    assert np.isfinite(predicted).all()


def test_quantile_predictions_sit_above_median_predictions():
    train = freight_rows(300)
    train["freight_value"] += np.random.default_rng(1).uniform(0, 50, 300)
    valid = freight_rows(50)

    median = make_predictor("boosted_median", "freight", SMALL_TREE)(train, valid, "freight_value")
    upper = make_predictor("boosted_quantile", "freight", SMALL_TREE)(train, valid, "freight_value")

    assert upper.mean() > median.mean()


def test_ratio_forecast_can_exceed_training_volumes():
    days = 120
    train = pd.DataFrame(
        {
            "lag_28": 100.0,
            "lag_35": 100.0,
            "lag_42": 100.0,
            "mean_7_lag_28": 100.0,
            "mean_28_lag_28": 100.0,
            "day_of_week": np.arange(days) % 7,
            "is_weekend": 0,
            "is_holiday": 0,
            "is_peak_window": 0,
            "days_since_start": np.arange(days),
            "orders": 100.0,
        }
    )
    valid = train.head(3).copy()
    valid["mean_28_lag_28"] = 500.0

    predicted = make_predictor("boosted_ratio", "daily_orders", SMALL_TREE)(train, valid, "orders")

    assert predicted == pytest.approx([500.0] * 3)


def test_forward_alerts_set_cutoffs_on_earlier_folds_only():
    predictions = pd.DataFrame(
        {
            "fold": ["a", "a", "b", "b"],
            "actual": [1, 0, 1, 0],
            "score": [0.9, 0.1, 0.95, 0.5],
        }
    )
    rows = forward_alert_results("test", predictions, 1.0)
    values = {row["metric"]: row["value"] for row in rows}

    # The cutoff of 0.9 comes from fold a, so only 0.95 is flagged in fold b.
    assert values == {"forward_precision": 1.0, "forward_recall": 1.0}
    assert {row["fold"] for row in rows} == {"b"}


def test_forward_promise_uses_a_margin_from_earlier_folds():
    predictions = pd.DataFrame(
        {
            "fold": ["a"] * 10 + ["b"] * 2,
            "actual": [15.0] * 10 + [14.0, 16.0],
            "score": [10.0] * 10 + [10.0, 10.0],
        }
    )
    rows = forward_promise_results("test", predictions)
    values = {row["metric"]: row["value"] for row in rows}

    # Fold a was 5 days short, so fold b's promise is 15 days.
    assert values["mean_predicted"] == 15.0
    assert values["share_by_predicted"] == 0.5


def test_usable_rows_rejects_the_holdout():
    table = pd.DataFrame({"period": ["holdout"]})
    with pytest.raises(ValueError, match="development"):
        usable_rows(PROBLEMS[0], table)


def test_peak_window_covers_five_days_from_black_friday():
    days = sorted(peak_window_days([2017]))
    assert days[0] == pd.Timestamp("2017-11-24")
    assert days[-1] == pd.Timestamp("2017-11-28")


def test_daily_lags_skip_the_peak_but_the_target_keeps_it():
    dates = pd.date_range("2017-10-01", "2018-01-31", freq="D")
    orders = pd.Series(100, index=dates)
    orders["2017-11-24"] = 1176
    daily = pd.DataFrame({"date": dates, "orders": orders.to_numpy(), "period": "development"})

    table = build_daily_features(daily).set_index("date")

    assert table.loc["2017-11-24", "orders"] == 1176
    assert table.loc["2017-11-24", "is_peak_window"] == 1
    assert table.loc["2017-12-22", "lag_28"] == 100


def test_weekly_lags_skip_peak_weeks_within_each_category():
    weeks = pd.date_range("2017-10-01", "2018-01-28", freq="W-SUN")
    weekly = pd.DataFrame(
        {"week_end": weeks, "category": "a", "items": 10, "period": "development"}
    )
    weekly.loc[weekly["week_end"] == "2017-11-26", "items"] = 500

    table = build_weekly_features(weekly).set_index("week_end")

    assert table.loc["2017-11-26", "items"] == 500
    assert table.loc["2017-11-26", "is_peak_week"] == 1
    assert table.loc["2017-12-24", "lag_4"] == 10
