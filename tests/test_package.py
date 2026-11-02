"""Tests for packaging and prediction, using small made-up tables."""

import json

import joblib
import numpy as np
import pandas as pd
import pytest

from src.features.build import build_daily_features, build_weekly_features
from src.models.package import (
    daily_rule_artifact,
    delivery_rule_artifact,
    weekly_rule_artifact,
)
from src.models.pipelines import make_boosted_classifier, make_boosted_regressor
from src.models.predictor import (
    DailyOrderRule,
    GroupMedianRule,
    InvalidInputError,
    ModelNotAvailableError,
    TrainedModel,
    WeeklyCategoryRule,
    load_predictor,
)

SPEC = {"numeric": ["size"], "categorical": ["group"]}
PARAMS = {"max_iter": 10, "max_leaf_nodes": 3, "min_samples_leaf": 2}


def training_rows():
    size = np.arange(60.0)
    return pd.DataFrame(
        {
            "size": size,
            "group": ["a", "b"] * 30,
            "label": (size > 30).astype(int),
            "cost": size * 2,
        }
    )


def daily_table(days=120):
    dates = pd.date_range("2018-01-01", periods=days, freq="D")
    daily = pd.DataFrame({"date": dates, "orders": np.arange(days), "period": "development"})
    return build_daily_features(daily)


def weekly_table():
    weeks = pd.date_range("2018-01-07", periods=20, freq="W-SUN")
    frames = [
        pd.DataFrame({"week_end": weeks, "category": name, "items": base + np.arange(20)})
        for name, base in [("toys", 10), ("books", 100)]
    ]
    table = pd.concat(frames, ignore_index=True).assign(period="development")
    return build_weekly_features(table)


def regression_model():
    rows = training_rows()
    model = make_boosted_regressor(SPEC, PARAMS, loss="absolute_error").fit(rows, rows["cost"])
    metadata = {"kind": "regression", "output": "predicted_cost", "features": SPEC}
    return TrainedModel(metadata, model)


def classifier(kind, **extra):
    rows = training_rows()
    model = make_boosted_classifier(SPEC, PARAMS).fit(rows, rows["label"])
    return TrainedModel({"kind": kind, "features": SPEC, **extra}, model)


def test_regression_model_returns_one_row_per_input():
    predicted = regression_model().predict(pd.DataFrame({"size": [5.0, 50.0], "group": ["a", "b"]}))
    assert list(predicted.columns) == ["predicted_cost"]
    assert predicted["predicted_cost"].iloc[1] > predicted["predicted_cost"].iloc[0]


def test_model_accepts_missing_values_and_unseen_categories():
    rows = pd.DataFrame({"size": [None], "group": ["never_seen"]})
    assert regression_model().predict(rows)["predicted_cost"].notna().all()


def test_model_ignores_extra_columns_and_keeps_the_index():
    rows = pd.DataFrame({"size": [1.0], "group": ["a"], "extra": ["x"]}, index=[7])
    assert regression_model().predict(rows).index.tolist() == [7]


def test_ranking_model_orders_rows_by_risk():
    rows = pd.DataFrame({"size": [1.0, 50.0], "group": ["a", "a"]})
    predicted = classifier("ranking").predict(rows)
    assert predicted["rank"].tolist() == [2, 1]
    assert "is_alert" not in predicted.columns


def test_alert_model_applies_its_stored_cutoff():
    rows = pd.DataFrame({"size": [1.0, 50.0], "group": ["a", "a"]})
    predicted = classifier("alert", alert_cutoff=0.5).predict(rows)
    assert predicted["is_alert"].tolist() == [False, True]


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        (pd.DataFrame(), "at least one row"),
        ("not a table", "at least one row"),
        (pd.DataFrame({"size": [1.0]}), "Missing columns"),
        (pd.DataFrame({"size": ["big"], "group": ["a"]}), "must be numeric"),
    ],
)
def test_model_rejects_bad_input(rows, message):
    with pytest.raises(InvalidInputError, match=message):
        regression_model().predict(rows)


def test_daily_rule_matches_the_training_feature():
    table = daily_table()
    rule = DailyOrderRule({"output": "predicted_orders"}, daily_rule_artifact(table))
    rows = table[table["mean_28_lag_28"].notna()]

    predicted = rule.predict(rows)["predicted_orders"]

    assert np.allclose(predicted, rows["mean_28_lag_28"])


def test_daily_rule_forecasts_up_to_28_days_past_the_data():
    table = daily_table()
    rule = DailyOrderRule({"output": "predicted_orders"}, daily_rule_artifact(table))
    last = table["date"].max()

    allowed = pd.DataFrame({"date": [last + pd.Timedelta(days=28)]})
    assert len(rule.predict(allowed)) == 1

    with pytest.raises(InvalidInputError, match="out of range"):
        rule.predict(pd.DataFrame({"date": [last + pd.Timedelta(days=29)]}))


def test_daily_rule_rejects_invalid_dates():
    rule = DailyOrderRule({"output": "predicted_orders"}, daily_rule_artifact(daily_table()))
    with pytest.raises(InvalidInputError, match="invalid dates"):
        rule.predict(pd.DataFrame({"date": ["soon"]}))


def test_weekly_rule_matches_the_training_feature():
    table = weekly_table()
    rule = WeeklyCategoryRule({"output": "predicted_items"}, weekly_rule_artifact(table))
    rows = table[table["mean_4_lag_4"].notna()]

    predicted = rule.predict(rows)["predicted_items"]

    assert np.allclose(predicted, rows["mean_4_lag_4"])


@pytest.mark.parametrize(
    ("week_end", "category", "message"),
    [
        ("2018-05-20", "cars", "Unknown category"),
        ("2018-05-16", "toys", "Sunday"),
        ("2019-01-06", "toys", "out of range"),
    ],
)
def test_weekly_rule_rejects_bad_requests(week_end, category, message):
    rule = WeeklyCategoryRule({"output": "predicted_items"}, weekly_rule_artifact(weekly_table()))
    with pytest.raises(InvalidInputError, match=message):
        rule.predict(pd.DataFrame({"week_end": [week_end], "category": [category]}))


def test_delivery_rule_falls_back_for_an_unseen_state():
    table = pd.DataFrame({"customer_state": ["SP", "SP", "RJ"], "days_to_deliver": [2.0, 4.0, 9.0]})
    rule = GroupMedianRule({"output": "predicted_days"}, delivery_rule_artifact(table))
    rows = pd.DataFrame({"customer_state": ["SP", "ZZ"]})
    assert rule.predict(rows)["predicted_days"].tolist() == [3.0, 4.0]


def write_metadata(directory, **metadata):
    directory.mkdir()
    (directory / "metadata.json").write_text(json.dumps(metadata))


def test_load_predictor_explains_a_held_model(tmp_path):
    write_metadata(tmp_path / "held", status="held", reason="its ranking didn't work")
    with pytest.raises(ModelNotAvailableError, match="its ranking didn't work"):
        load_predictor("held", tmp_path)


def test_load_predictor_explains_a_missing_package(tmp_path):
    with pytest.raises(ModelNotAvailableError, match="No package"):
        load_predictor("absent", tmp_path)


def test_load_predictor_refuses_a_different_scikit_learn(tmp_path):
    write_metadata(
        tmp_path / "old",
        status="active",
        kind="regression",
        environment={"scikit-learn": "0.0.1"},
    )
    with pytest.raises(ModelNotAvailableError, match="needs scikit-learn"):
        load_predictor("old", tmp_path)


def test_trained_model_survives_a_save_and_load(tmp_path):
    predictor = regression_model()
    directory = tmp_path / "saved"
    directory.mkdir()
    joblib.dump(predictor.model, directory / "model.joblib")
    import sklearn

    metadata = {
        **predictor.metadata,
        "status": "active",
        "environment": {"scikit-learn": sklearn.__version__},
    }
    (directory / "metadata.json").write_text(json.dumps(metadata))

    rows = pd.DataFrame({"size": [5.0], "group": ["a"]})
    pd.testing.assert_frame_equal(
        predictor.predict(rows), load_predictor("saved", tmp_path).predict(rows)
    )
