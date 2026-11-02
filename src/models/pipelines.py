"""Shared preprocessing, fitted on training rows only inside each fold."""

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

from src import config

# Categories rarer than this are grouped, so they can't memorise a few rows.
MIN_CATEGORY_ROWS = 20


def make_preprocessor(spec: dict) -> ColumnTransformer:
    """Return a transformer that imputes, scales, and encodes a feature spec."""
    numeric = make_pipeline(SimpleImputer(strategy="median"), StandardScaler())
    categorical = make_pipeline(
        SimpleImputer(strategy="constant", fill_value="missing"),
        OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=MIN_CATEGORY_ROWS),
    )
    return ColumnTransformer(
        [("numeric", numeric, spec["numeric"]), ("categorical", categorical, spec["categorical"])]
    )


def make_linear_classifier(spec: dict) -> Pipeline:
    """Return a logistic regression with shared preprocessing."""
    model = LogisticRegression(max_iter=1000, random_state=config.RANDOM_SEED)
    return make_pipeline(make_preprocessor(spec), model)


def make_linear_regressor(spec: dict, alpha: float = 1.0) -> Pipeline:
    """Return a ridge regression with shared preprocessing."""
    return make_pipeline(make_preprocessor(spec), Ridge(alpha=alpha))


def make_tree_preprocessor(spec: dict) -> ColumnTransformer:
    """Return a transformer for tree models, which need no scaling or imputing."""
    encoder = OrdinalEncoder(
        handle_unknown="use_encoded_value",
        unknown_value=np.nan,
        encoded_missing_value=np.nan,
    )
    return ColumnTransformer(
        [("numeric", "passthrough", spec["numeric"]), ("categorical", encoder, spec["categorical"])]
    )


def boosted_settings(spec: dict, params: dict) -> dict:
    """Return settings shared by the boosted models."""
    n_numeric = len(spec["numeric"])
    return {
        **params,
        "categorical_features": list(range(n_numeric, n_numeric + len(spec["categorical"]))),
        # Early stopping holds out random rows, which would break time order.
        "early_stopping": False,
        "random_state": config.RANDOM_SEED,
    }


def make_boosted_classifier(spec: dict, params: dict) -> Pipeline:
    """Return a gradient boosting classifier."""
    model = HistGradientBoostingClassifier(**boosted_settings(spec, params))
    return make_pipeline(make_tree_preprocessor(spec), model)


def make_boosted_regressor(spec: dict, params: dict, **loss_settings) -> Pipeline:
    """Return a gradient boosting regressor with the given loss."""
    model = HistGradientBoostingRegressor(**boosted_settings(spec, params), **loss_settings)
    return make_pipeline(make_tree_preprocessor(spec), model)
