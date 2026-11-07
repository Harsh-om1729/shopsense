"""Load packaged models and rules behind one predict interface.

Use load_predictor(name).predict(rows), which returns a DataFrame. Rows hold
feature columns for models, and dates or categories for forecast rules.
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

from src import config

METADATA_FILE = "metadata.json"
MODEL_FILE = "model.joblib"
RULE_FILE = "rule.json"

# Lags are at least this old, which limits how far ahead a rule can forecast.
DAILY_LAG_DAYS = 28
DAILY_WINDOW_DAYS = 28
WEEKLY_LAG_WEEKS = 4
WEEKLY_WINDOW_WEEKS = 4


class InvalidInputError(ValueError):
    """The rows can't be scored, for a reason the caller can fix."""


class ModelNotAvailableError(RuntimeError):
    """The model is held, or isn't usable in this environment."""


def require_rows(rows: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Return the required columns, or raise a clear error."""
    if not isinstance(rows, pd.DataFrame) or rows.empty:
        raise InvalidInputError("Expected a DataFrame with at least one row.")
    missing = sorted(set(columns) - set(rows.columns))
    if missing:
        raise InvalidInputError(f"Missing columns: {missing}.")
    return rows[columns].copy()


def require_dates(values: pd.Series, name: str) -> pd.Series:
    """Return parsed dates, or raise a clear error."""
    parsed = pd.to_datetime(values, errors="coerce")
    if parsed.isna().any():
        raise InvalidInputError(f"Column {name} has invalid dates.")
    return parsed.dt.normalize()


class TrainedModel:
    """A fitted scikit-learn pipeline."""

    def __init__(self, metadata: dict, model):
        self.metadata = metadata
        self.model = model
        self.numeric = metadata["features"]["numeric"]
        self.categorical = metadata["features"]["categorical"]

    def prepare(self, rows: pd.DataFrame) -> pd.DataFrame:
        """Return validated rows. Missing values are allowed, wrong types aren't."""
        frame = require_rows(rows, self.numeric + self.categorical)
        for column in self.numeric:
            try:
                frame[column] = pd.to_numeric(frame[column]).astype(float)
            except (TypeError, ValueError) as error:
                raise InvalidInputError(f"Column {column} must be numeric.") from error
        return frame

    def predict(self, rows: pd.DataFrame) -> pd.DataFrame:
        frame = self.prepare(rows)
        kind = self.metadata["kind"]
        if kind == "regression":
            predicted = np.clip(self.model.predict(frame), 0, None)
            return pd.DataFrame({self.metadata["output"]: predicted}, index=rows.index)

        scores = self.model.predict_proba(frame)[:, 1]
        result = pd.DataFrame({"risk_score": scores}, index=rows.index)
        if kind == "alert":
            result["is_alert"] = scores >= self.metadata["alert_cutoff"]
        else:
            # Scores are for ordering. A fixed cutoff failed on the holdout.
            result["rank"] = result["risk_score"].rank(ascending=False, method="first").astype(int)
        return result


class GroupMedianRule:
    """Predict a stored median for each group, or the overall median if it's unseen."""

    def __init__(self, metadata: dict, rule: dict):
        self.metadata = metadata
        self.rule = rule

    def predict(self, rows: pd.DataFrame) -> pd.DataFrame:
        column = self.rule["group_column"]
        frame = require_rows(rows, [column])
        predicted = frame[column].map(self.rule["medians"]).fillna(self.rule["fallback"])
        return pd.DataFrame({self.metadata["output"]: predicted.astype(float)}, index=rows.index)


class DailyOrderRule:
    """Predict the mean of the 28 days that end 28 days before each date."""

    def __init__(self, metadata: dict, rule: dict):
        self.metadata = metadata
        self.history = pd.Series(rule["orders"], index=pd.to_datetime(rule["dates"]), dtype=float)

    def data_end(self) -> pd.Timestamp:
        return self.history.index.max()

    def latest_date(self) -> pd.Timestamp:
        """Return the last date the rule can forecast."""
        return self.data_end() + pd.Timedelta(days=DAILY_LAG_DAYS)

    def forecast_one(self, date: pd.Timestamp) -> float:
        end = date - pd.Timedelta(days=DAILY_LAG_DAYS)
        start = end - pd.Timedelta(days=DAILY_WINDOW_DAYS - 1)
        window = self.history.loc[start:end].dropna()
        if len(window) < DAILY_WINDOW_DAYS:
            latest = self.history.index.max() + pd.Timedelta(days=DAILY_LAG_DAYS)
            raise InvalidInputError(
                f"{date.date()} is out of range. Latest date is {latest.date()}."
            )
        return float(window.mean())

    def predict(self, rows: pd.DataFrame) -> pd.DataFrame:
        dates = require_dates(require_rows(rows, ["date"])["date"], "date")
        predicted = [self.forecast_one(date) for date in dates]
        return pd.DataFrame({self.metadata["output"]: predicted}, index=rows.index)


class WeeklyCategoryRule:
    """Predict the mean of the 4 weeks that end 4 weeks before each week."""

    def __init__(self, metadata: dict, rule: dict):
        self.metadata = metadata
        weeks = pd.to_datetime(rule["week_ends"])
        self.history = {
            category: pd.Series(items, index=weeks, dtype=float)
            for category, items in rule["items"].items()
        }

    def categories(self) -> list[str]:
        return sorted(self.history)

    def latest_week_end(self) -> pd.Timestamp:
        """Return the last week end the rule can forecast."""
        data_end = max(series.index.max() for series in self.history.values())
        return data_end + pd.Timedelta(weeks=WEEKLY_LAG_WEEKS)

    def forecast_one(self, week_end: pd.Timestamp, category: str) -> float:
        if category not in self.history:
            raise InvalidInputError(f"Unknown category {category!r}. Use {sorted(self.history)}.")
        if week_end.day_of_week != 6:
            raise InvalidInputError(f"{week_end.date()} isn't a Sunday week end.")

        series = self.history[category]
        end = week_end - pd.Timedelta(weeks=WEEKLY_LAG_WEEKS)
        start = end - pd.Timedelta(weeks=WEEKLY_WINDOW_WEEKS - 1)
        window = series.loc[start:end].dropna()
        if len(window) < WEEKLY_WINDOW_WEEKS:
            latest = series.index.max() + pd.Timedelta(weeks=WEEKLY_LAG_WEEKS)
            raise InvalidInputError(
                f"{week_end.date()} is out of range. Latest week is {latest.date()}."
            )
        return float(window.mean())

    def predict(self, rows: pd.DataFrame) -> pd.DataFrame:
        frame = require_rows(rows, ["week_end", "category"])
        weeks = require_dates(frame["week_end"], "week_end")
        predicted = [
            self.forecast_one(week, category)
            for week, category in zip(weeks, frame["category"], strict=True)
        ]
        return pd.DataFrame({self.metadata["output"]: predicted}, index=rows.index)


RULES = {
    "group_median": GroupMedianRule,
    "daily_rule": DailyOrderRule,
    "weekly_rule": WeeklyCategoryRule,
}


def read_metadata(name: str, models_dir: Path = config.MODELS_DIR) -> dict:
    """Return a package's metadata, or raise if it hasn't been built."""
    path = Path(models_dir) / name / METADATA_FILE
    if not path.is_file():
        raise ModelNotAvailableError(f"No package at {path}. Run src.models.package first.")
    return json.loads(path.read_text())


def load_predictor(name: str, models_dir: Path = config.MODELS_DIR):
    """Return a predictor, refusing held models and mismatched library versions."""
    metadata = read_metadata(name, models_dir)
    if metadata["status"] == "held":
        raise ModelNotAvailableError(f"{name} is held: {metadata['reason']}")

    directory = Path(models_dir) / name
    kind = metadata["kind"]
    if kind in RULES:
        return RULES[kind](metadata, json.loads((directory / RULE_FILE).read_text()))

    trained_with = metadata["environment"]["scikit-learn"]
    if trained_with != sklearn.__version__:
        raise ModelNotAvailableError(
            f"{name} needs scikit-learn {trained_with}, but {sklearn.__version__} is installed."
        )
    return TrainedModel(metadata, joblib.load(directory / MODEL_FILE))
