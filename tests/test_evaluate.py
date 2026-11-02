"""Tests for the holdout evaluation, using made-up data."""

import numpy as np
import pandas as pd
import pytest

from src.models.baselines import PROBLEMS
from src.models.evaluate import (
    SIMPLE_RULES,
    alert_scores,
    bootstrap_improvement,
    split_holdout,
    verdict,
)


def mean_error(actual, predicted):
    return float(np.abs(actual - predicted).mean())


def test_split_holdout_keeps_periods_apart_and_skips_the_embargo():
    table = pd.DataFrame({"period": ["development", "embargo", "holdout"], "is_late": [0, 1, 1]})
    development, holdout = split_holdout(PROBLEMS[0], table)

    assert development["period"].tolist() == ["development"]
    assert holdout["period"].tolist() == ["holdout"]


def test_split_holdout_needs_both_periods():
    table = pd.DataFrame({"period": ["development"], "is_late": [0]})
    with pytest.raises(ValueError, match="holdout"):
        split_holdout(PROBLEMS[0], table)


def test_every_problem_has_a_simple_rule_from_its_baselines():
    for problem in PROBLEMS:
        assert SIMPLE_RULES[problem.name] in problem.baselines


def test_bootstrap_interval_excludes_zero_for_a_clear_improvement():
    rng = np.random.default_rng(0)
    actual = rng.normal(size=500)
    good = actual + rng.normal(scale=0.1, size=500)
    poor = actual + rng.normal(scale=2.0, size=500)

    improvement, low, high = bootstrap_improvement(mean_error, actual, good, poor, False)

    assert improvement > 0
    assert 0 < low < improvement < high


def test_bootstrap_interval_includes_zero_when_models_match():
    rng = np.random.default_rng(0)
    actual = rng.normal(size=500)
    first = actual + rng.normal(size=500)
    second = actual + rng.normal(size=500)

    _, low, high = bootstrap_improvement(mean_error, actual, first, second, False)

    assert low < 0 < high


def test_bootstrap_groups_stay_together():
    actual = np.zeros(4)
    model = np.array([0.0, 0.0, 1.0, 1.0])
    rule = np.ones(4)
    groups = np.array(["a", "a", "b", "b"])

    # Each resampled week gains either 1 or 0, so results can only be 0, 0.5, or 1.
    _, low, high = bootstrap_improvement(mean_error, actual, model, rule, False, groups)

    assert low in {0.0, 0.5, 1.0}
    assert high in {0.0, 0.5, 1.0}


def test_bootstrap_is_repeatable():
    actual = np.arange(50.0)
    model = actual + 1
    rule = actual + 3
    first = bootstrap_improvement(mean_error, actual, model, rule, False)
    assert first == bootstrap_improvement(mean_error, actual, model, rule, False)


@pytest.mark.parametrize(
    ("low", "precision", "target", "expected"),
    [
        (0.01, None, None, "Ready"),
        (0.01, 0.45, 0.5, "Ready"),
        (0.01, 0.40, 0.5, "Ready"),
        (0.01, 0.39, 0.5, "Ready for ranking only"),
        (0.0, 0.9, 0.5, "Use the simple rule"),
        (-0.01, None, None, "Use the simple rule"),
    ],
)
def test_verdict_applies_the_locked_rules(low, precision, target, expected):
    assert verdict(low, precision, target) == expected


def test_alert_scores_use_the_frozen_cutoff():
    precision, recall, flagged = alert_scores([1, 1, 0, 0], [0.9, 0.2, 0.8, 0.1], 0.5)

    assert precision == 0.5
    assert recall == 0.5
    assert flagged == 0.5


def test_alert_scores_handle_nothing_flagged():
    assert alert_scores([1, 0], [0.1, 0.1], 0.5) == (0.0, 0.0, 0.0)
