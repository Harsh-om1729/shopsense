"""Shared preprocessing, fitted on training rows only inside each fold."""

from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

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


def make_linear_regressor(spec: dict) -> Pipeline:
    """Return a ridge regression with shared preprocessing."""
    return make_pipeline(make_preprocessor(spec), Ridge())
