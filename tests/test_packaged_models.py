"""Check the real packages. These are skipped until src.models.package has run."""

import numpy as np
import pandas as pd
import pytest

from src import config
from src.features.build import FEATURES
from src.models.predictor import InvalidInputError, ModelNotAvailableError, load_predictor

ACTIVE = [
    "low_review_risk",
    "seller_inactivity_risk",
    "freight_cost",
    "daily_orders_rule",
    "delivery_time_rule",
    "category_demand_rule",
]

pytestmark = pytest.mark.skipif(
    not (config.MODELS_DIR / "freight_cost" / "metadata.json").is_file(),
    reason="Packages haven't been built.",
)


def features(name):
    return pd.read_parquet(config.FEATURES_DIR / f"{name}.parquet")


@pytest.mark.parametrize("name", ACTIVE)
def test_active_packages_load(name):
    assert load_predictor(name).metadata["status"] == "active"


def test_late_delivery_is_held():
    with pytest.raises(ModelNotAvailableError, match="held"):
        load_predictor("late_delivery_risk")


def test_trained_models_score_real_rows():
    rows = features("freight").tail(50)
    predicted = load_predictor("freight_cost").predict(rows)
    assert len(predicted) == 50
    assert predicted["predicted_freight"].between(0, 500).all()


def test_daily_rule_matches_real_features():
    table = features("daily_orders").dropna(subset=["mean_28_lag_28"])
    predicted = load_predictor("daily_orders_rule").predict(table)["predicted_orders"]
    assert np.allclose(predicted, table["mean_28_lag_28"])


def test_weekly_rule_matches_real_features():
    table = features("weekly_category").dropna(subset=["mean_4_lag_4"])
    predicted = load_predictor("category_demand_rule").predict(table)["predicted_items"]
    assert np.allclose(predicted, table["mean_4_lag_4"])


def test_model_features_match_the_current_feature_list():
    metadata = load_predictor("freight_cost").metadata
    assert metadata["features"] == FEATURES["freight"]


def test_real_model_rejects_missing_columns():
    with pytest.raises(InvalidInputError, match="Missing columns"):
        load_predictor("low_review_risk").predict(pd.DataFrame({"is_overdue": [1]}))
