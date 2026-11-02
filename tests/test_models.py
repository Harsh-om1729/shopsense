"""Tests for validation folds, metrics, and baselines."""

import numpy as np
import pandas as pd
import pytest

from src import config
from src.models import metrics
from src.models.baselines import PROBLEMS, by_group, evaluate_problem, overall_rate
from src.models.validation import Fold, forecast_folds, split_fold, tabular_folds


def fold():
    return Fold("test", pd.Timestamp("2018-03-01"), pd.Timestamp("2018-05-01"))


def rows(times, known):
    return pd.DataFrame({"time": pd.to_datetime(times), "known": pd.to_datetime(known)})


def test_split_fold_excludes_rows_inside_the_gap():
    table = rows(["2018-01-15", "2018-02-15", "2018-03-15"], ["2018-01-20"] * 3)
    train, valid = split_fold(table, fold(), "time", gap_days=30)

    assert train["time"].tolist() == [pd.Timestamp("2018-01-15")]
    assert valid["time"].tolist() == [pd.Timestamp("2018-03-15")]


def test_split_fold_excludes_outcomes_unknown_at_validation_start():
    table = rows(["2018-01-15", "2018-01-16"], ["2018-02-01", "2018-03-10"])
    train, _ = split_fold(table, fold(), "time", "known", gap_days=30)

    assert len(train) == 1


def test_folds_stop_before_the_embargo_and_the_holdout():
    embargo_start = pd.Timestamp(config.HOLDOUT_START) - pd.Timedelta(days=config.EMBARGO_DAYS)
    assert tabular_folds()[-1].end <= embargo_start
    assert forecast_folds()[-1].end <= pd.Timestamp(config.HOLDOUT_START)


def test_forecast_folds_do_not_overlap():
    folds = forecast_folds()
    assert all(a.end == b.start for a, b in zip(folds, folds[1:], strict=False))


def test_pr_auc_of_a_constant_equals_the_positive_rate():
    assert metrics.pr_auc([1, 0, 0, 0], [0.5] * 4) == pytest.approx(0.25)


def test_recall_at_precision_is_zero_when_unreachable():
    assert metrics.recall_at_precision([1, 0, 0, 0], [0.5] * 4, 0.9) == 0.0


def test_recall_at_precision_finds_the_best_cutoff():
    actual = [1, 1, 0, 1, 0]
    scores = [0.9, 0.8, 0.7, 0.6, 0.1]
    assert metrics.recall_at_precision(actual, scores, 0.75) == 1.0
    assert metrics.recall_at_precision(actual, scores, 1.0) == pytest.approx(2 / 3)


def test_weighted_recall_counts_weight_not_rows():
    actual = [1, 1, 0]
    scores = [0.9, 0.1, 0.5]
    weights = [90.0, 10.0, 1.0]
    assert metrics.weighted_recall_at_precision(actual, scores, weights, 1.0) == 0.9


def test_mape_skips_zero_actuals():
    assert metrics.mape_nonzero([0, 10], [5, 12]) == pytest.approx(0.2)


def test_wape_is_total_error_over_total_volume():
    assert metrics.wape([10, 30], [20, 30]) == 0.25


def test_mase_is_one_when_error_matches_the_naive_method():
    training = np.array([1.0] * 7 + [3.0] * 7)
    assert metrics.mase([10], [12], training) == pytest.approx(1.0)


def test_share_by_predicted():
    assert metrics.share_by_predicted([1, 5], [2, 3]) == 0.5


def test_by_group_falls_back_for_unseen_groups():
    train = pd.DataFrame({"group": ["a", "a", "b"], "y": [1.0, 3.0, 5.0]})
    valid = pd.DataFrame({"group": ["a", "z"]})
    predicted = by_group(["group"], "median")(train, valid, "y")
    assert predicted.tolist() == [2.0, 3.0]


def test_overall_rate_uses_training_rows_only():
    train = pd.DataFrame({"y": [1, 0]})
    assert overall_rate(train, pd.DataFrame({"y": [1, 1, 1]}), "y").tolist() == [0.5] * 3


def test_evaluate_problem_rejects_rows_outside_development():
    table = pd.DataFrame({"period": ["development", "holdout"]})
    with pytest.raises(ValueError, match="development"):
        evaluate_problem(PROBLEMS[0], table)


def test_every_problem_has_a_primary_metric_and_a_baseline():
    assert len(PROBLEMS) == 7
    for problem in PROBLEMS:
        assert problem.primary in problem.metrics
        assert problem.baselines
