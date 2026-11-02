"""Define the seven problems and the baselines each model must beat."""

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.features.build import FEATURES
from src.models import metrics
from src.models.pipelines import make_linear_classifier, make_linear_regressor
from src.models.validation import Fold, forecast_folds, split_fold, tabular_folds

GAP_DAYS = 30

# Precision each alert must reach. These are assumptions set before seeing
# results, because the data has no cost for a false alarm.
LATE_PRECISION = 0.25
LOW_REVIEW_PRECISION = 0.50
INACTIVE_PRECISION = 0.60


@dataclass(frozen=True)
class Problem:
    name: str
    table: str
    target: str
    time_column: str
    primary: str
    higher_is_better: bool
    baselines: dict[str, Callable]
    metrics: dict[str, Callable]
    folds: Callable[[], list[Fold]] = tabular_folds
    known_column: str | None = None
    gap_days: int = 0
    required_columns: tuple[str, ...] = ()


def overall_rate(train, valid, target):
    """Predict the training mean for every row."""
    return np.full(len(valid), train[target].mean())


def overall_median(train, valid, target):
    """Predict the training median for every row."""
    return np.full(len(valid), train[target].median())


def by_group(columns, statistic):
    """Return a baseline that predicts a training statistic for each group."""

    def predict(train, valid, target):
        grouped = train.groupby(columns)[target].agg(statistic)
        fallback = train[target].agg(statistic)
        keys = pd.MultiIndex.from_frame(valid[columns])
        return grouped.reindex(keys).fillna(fallback).to_numpy()

    return predict


def use_column(column):
    """Return a baseline that reads a value already known at prediction time."""

    def predict(train, valid, target):
        return valid[column].to_numpy(dtype=float)

    return predict


def linear_classifier(table):
    """Return a logistic regression baseline for a feature table."""

    def predict(train, valid, target):
        model = make_linear_classifier(FEATURES[table])
        model.fit(train, train[target])
        return model.predict_proba(valid)[:, 1]

    return predict


def linear_regressor(table):
    """Return a ridge regression baseline. Negative predictions become zero."""

    def predict(train, valid, target):
        model = make_linear_regressor(FEATURES[table])
        model.fit(train, train[target])
        return np.clip(model.predict(valid), 0, None)

    return predict


def recall_metric(precision):
    def compute(actual, predicted, valid, train):
        return metrics.recall_at_precision(actual, predicted, precision)

    return compute


def pr_auc(actual, predicted, valid, train):
    return metrics.pr_auc(actual, predicted)


def mae(actual, predicted, valid, train):
    return metrics.mae(actual, predicted)


def share_by_predicted(actual, predicted, valid, train):
    return metrics.share_by_predicted(actual, predicted)


def mean_predicted(actual, predicted, valid, train):
    return float(np.mean(predicted))


def mape(actual, predicted, valid, train):
    return metrics.mape_nonzero(actual, predicted)


def wape(actual, predicted, valid, train):
    return metrics.wape(actual, predicted)


def mase(actual, predicted, valid, train):
    return metrics.mase(actual, predicted, train["orders"])


def revenue_recall(actual, predicted, valid, train):
    return metrics.weighted_recall_at_precision(
        actual, predicted, valid["revenue_90d"], INACTIVE_PRECISION
    )


PROBLEMS = [
    Problem(
        name="1. Late delivery risk",
        table="delivery",
        target="is_late",
        time_column="order_purchase_timestamp",
        known_column="outcome_date",
        gap_days=GAP_DAYS,
        primary="pr_auc",
        higher_is_better=True,
        baselines={
            "Overall rate": overall_rate,
            "Rate by same-state route": by_group(["same_state"], "mean"),
            "Logistic regression": linear_classifier("delivery"),
        },
        metrics={"pr_auc": pr_auc, "recall_at_precision": recall_metric(LATE_PRECISION)},
    ),
    Problem(
        name="2. Low review risk",
        table="reviews",
        target="is_low",
        time_column="order_purchase_timestamp",
        known_column="score_known_date",
        gap_days=GAP_DAYS,
        primary="pr_auc",
        higher_is_better=True,
        baselines={
            "Overall rate": overall_rate,
            "Rate by overdue": by_group(["is_overdue"], "mean"),
            "Logistic regression": linear_classifier("reviews"),
        },
        metrics={"pr_auc": pr_auc, "recall_at_precision": recall_metric(LOW_REVIEW_PRECISION)},
    ),
    Problem(
        name="3. Daily order forecast",
        table="daily_orders",
        target="orders",
        time_column="date",
        primary="mae",
        higher_is_better=False,
        folds=forecast_folds,
        required_columns=("lag_28", "mean_28_lag_28"),
        baselines={
            "Same weekday 4 weeks ago": use_column("lag_28"),
            "Mean of 28 days, 4 weeks ago": use_column("mean_28_lag_28"),
            "Ridge regression": linear_regressor("daily_orders"),
        },
        metrics={"mae": mae, "mase": mase},
    ),
    Problem(
        name="4. Delivery time estimate",
        table="delivery",
        target="days_to_deliver",
        time_column="order_purchase_timestamp",
        known_column="outcome_date",
        gap_days=GAP_DAYS,
        primary="mae",
        higher_is_better=False,
        baselines={
            "Olist's promised days": use_column("days_promised"),
            "Overall median": overall_median,
            "Median by customer state": by_group(["customer_state"], "median"),
            "Ridge regression": linear_regressor("delivery"),
        },
        metrics={
            "mae": mae,
            "share_by_predicted": share_by_predicted,
            "mean_predicted": mean_predicted,
        },
    ),
    Problem(
        name="5. Category demand forecast",
        table="weekly_category",
        target="items",
        time_column="week_end",
        primary="wape",
        higher_is_better=False,
        folds=forecast_folds,
        required_columns=("lag_4", "mean_4_lag_4"),
        baselines={
            "Mean of 4 weeks, 4 weeks ago": use_column("mean_4_lag_4"),
            "Ridge regression": linear_regressor("weekly_category"),
        },
        metrics={"wape": wape},
    ),
    Problem(
        name="6. Seller inactivity risk",
        table="seller_snapshots",
        target="is_inactive",
        time_column="snapshot_date",
        known_column="outcome_date",
        primary="pr_auc",
        higher_is_better=True,
        baselines={
            "Overall rate": overall_rate,
            "Days since last sale": use_column("days_since_last_sale"),
            "Logistic regression": linear_classifier("seller_snapshots"),
        },
        metrics={
            "pr_auc": pr_auc,
            "recall_at_precision": recall_metric(INACTIVE_PRECISION),
            "revenue_recall": revenue_recall,
        },
    ),
    Problem(
        name="7. Freight cost estimate",
        table="freight",
        target="freight_value",
        time_column="order_purchase_timestamp",
        primary="mae",
        higher_is_better=False,
        baselines={
            "Overall median": overall_median,
            "Median by state pair": by_group(["seller_state", "customer_state"], "median"),
            "Ridge regression": linear_regressor("freight"),
        },
        metrics={"mae": mae, "mape": mape},
    ),
]


def usable_rows(problem: Problem, table: pd.DataFrame) -> pd.DataFrame:
    """Return rows a model may use, refusing anything outside development."""
    if not table["period"].eq("development").all():
        raise ValueError("Models must only see development rows.")
    return table.dropna(subset=list(problem.required_columns))


def score_predictor(problem, usable, label, predict):
    """Return metric rows and out-of-fold predictions for one predictor."""
    results, predictions = [], []
    for fold in problem.folds():
        train, valid = split_fold(
            usable, fold, problem.time_column, problem.known_column, problem.gap_days
        )
        if train.empty or valid.empty:
            raise ValueError(f"{problem.name} has an empty fold: {fold.name}.")

        predicted = predict(train, valid, problem.target)
        actual = valid[problem.target]
        predictions.append(pd.DataFrame({"fold": fold.name, "actual": actual, "score": predicted}))
        for metric, compute in problem.metrics.items():
            results.append(
                {
                    "problem": problem.name,
                    "baseline": label,
                    "fold": fold.name,
                    "metric": metric,
                    "value": compute(actual, predicted, valid, train),
                    "train_rows": len(train),
                    "valid_rows": len(valid),
                }
            )
    return results, pd.concat(predictions, ignore_index=True)


def evaluate_problem(problem: Problem, table: pd.DataFrame) -> pd.DataFrame:
    """Return one row per baseline, fold, and metric, using development rows only."""
    usable = usable_rows(problem, table)
    results = []
    for baseline, predict in problem.baselines.items():
        results += score_predictor(problem, usable, baseline, predict)[0]
    return pd.DataFrame(results)
