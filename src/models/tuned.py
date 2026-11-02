"""Model families and the settings searched for each problem."""

import numpy as np
from sklearn.model_selection import ParameterGrid, ParameterSampler

from src import config
from src.features.build import FEATURES
from src.models.pipelines import (
    make_boosted_classifier,
    make_boosted_regressor,
    make_linear_regressor,
)

CANDIDATES_PER_FAMILY = 8
PROMISE_QUANTILE = 0.9

LARGE_TABLE_SPACE = {
    "learning_rate": [0.03, 0.06, 0.1],
    "max_iter": [100, 200, 400],
    "max_leaf_nodes": [7, 15, 31],
    "min_samples_leaf": [20, 50, 100, 200],
    "l2_regularization": [0.0, 1.0, 10.0],
}

# Forecast tables have hundreds of rows, so their trees must stay small.
SMALL_TABLE_SPACE = {
    "learning_rate": [0.03, 0.06, 0.1],
    "max_iter": [50, 100, 200],
    "max_leaf_nodes": [3, 7, 15],
    "min_samples_leaf": [5, 10, 20],
    "l2_regularization": [0.0, 1.0, 10.0],
}

RIDGE_SPACE = {"alpha": [0.1, 1.0, 10.0, 100.0, 1000.0]}

# The recent average each forecast is expressed relative to.
FORECAST_REFERENCE = {"daily_orders": "mean_28_lag_28", "weekly_category": "mean_4_lag_4"}

TUNING = {
    "1. Late delivery risk": {"boosted_classifier": LARGE_TABLE_SPACE},
    "2. Low review risk": {"boosted_classifier": LARGE_TABLE_SPACE},
    "3. Daily order forecast": {"ridge": RIDGE_SPACE, "boosted_ratio": SMALL_TABLE_SPACE},
    "4. Delivery time estimate": {"boosted_median": LARGE_TABLE_SPACE},
    "5. Category demand forecast": {"ridge": RIDGE_SPACE, "boosted_ratio": SMALL_TABLE_SPACE},
    "6. Seller inactivity risk": {"boosted_classifier": LARGE_TABLE_SPACE},
    "7. Freight cost estimate": {"boosted_median": LARGE_TABLE_SPACE},
}


def sample_settings(space: dict) -> list[dict]:
    """Return a fixed random sample of settings, or all of them if there are few."""
    size = len(ParameterGrid(space))
    if size <= CANDIDATES_PER_FAMILY:
        return list(ParameterGrid(space))
    sampler = ParameterSampler(space, n_iter=CANDIDATES_PER_FAMILY, random_state=config.RANDOM_SEED)
    return list(sampler)


def make_predictor(family: str, table: str, params: dict):
    """Return a function that fits on training rows and predicts validation rows."""
    spec = FEATURES[table]

    def boosted_classifier(train, valid, target):
        model = make_boosted_classifier(spec, params)
        model.fit(train, train[target])
        return model.predict_proba(valid)[:, 1]

    def boosted_median(train, valid, target):
        model = make_boosted_regressor(spec, params, loss="absolute_error")
        model.fit(train, train[target])
        return np.clip(model.predict(valid), 0, None)

    def boosted_quantile(train, valid, target):
        model = make_boosted_regressor(spec, params, loss="quantile", quantile=PROMISE_QUANTILE)
        model.fit(train, train[target])
        return np.clip(model.predict(valid), 0, None)

    def boosted_ratio(train, valid, target):
        # Trees can't exceed the values they trained on, so they learn the
        # ratio to a recent average, which still works as volumes grow.
        reference = FORECAST_REFERENCE[table]
        model = make_boosted_regressor(spec, params)
        model.fit(train, train[target] / train[reference].clip(lower=1))
        recent_average = valid[reference].clip(lower=1).to_numpy()
        return np.clip(model.predict(valid) * recent_average, 0, None)

    def ridge(train, valid, target):
        model = make_linear_regressor(spec, **params)
        model.fit(train, train[target])
        return np.clip(model.predict(valid), 0, None)

    families = {
        "boosted_classifier": boosted_classifier,
        "boosted_median": boosted_median,
        "boosted_quantile": boosted_quantile,
        "boosted_ratio": boosted_ratio,
        "ridge": ridge,
    }
    if family not in families:
        raise ValueError(f"Unknown model family: {family}.")
    return families[family]
