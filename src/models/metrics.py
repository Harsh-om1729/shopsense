"""Evaluation metrics for all seven problems."""

import numpy as np
from sklearn.metrics import average_precision_score, precision_recall_curve


def pr_auc(actual, scores) -> float:
    """Return average precision, which suits rare positive classes."""
    return float(average_precision_score(actual, scores))


def threshold_at_precision(actual, scores, target):
    """Return the score cutoff with the most recall at the target precision, if any."""
    precision, recall, thresholds = precision_recall_curve(actual, scores)
    reachable = precision[:-1] >= target
    if not reachable.any():
        return None
    best = np.flatnonzero(reachable)[np.argmax(recall[:-1][reachable])]
    return thresholds[best]


def recall_at_precision(actual, scores, target) -> float:
    """Return the share of positives caught at the target precision, or 0 if unreachable."""
    actual, scores = np.asarray(actual), np.asarray(scores)
    cutoff = threshold_at_precision(actual, scores, target)
    if cutoff is None:
        return 0.0
    return float((scores[actual == 1] >= cutoff).mean())


def weighted_recall_at_precision(actual, scores, weights, target) -> float:
    """Return the share of positive weight caught at the target precision."""
    actual, scores, weights = map(np.asarray, (actual, scores, weights))
    cutoff = threshold_at_precision(actual, scores, target)
    if cutoff is None:
        return 0.0
    positive = actual == 1
    return float(weights[positive & (scores >= cutoff)].sum() / weights[positive].sum())


def mae(actual, predicted) -> float:
    """Return the mean absolute error."""
    return float(np.abs(np.asarray(actual) - np.asarray(predicted)).mean())


def mape_nonzero(actual, predicted) -> float:
    """Return the mean absolute percentage error, skipping zero actuals."""
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    nonzero = actual != 0
    return float((np.abs(actual - predicted)[nonzero] / actual[nonzero]).mean())


def share_by_predicted(actual, predicted) -> float:
    """Return the share of orders that arrive by the predicted time."""
    return float((np.asarray(actual) <= np.asarray(predicted)).mean())


def mase(actual, predicted, training_series, season=7) -> float:
    """Return MAE scaled by a weekly naive forecast's error on the training data.

    Below 1 means the forecast beats that naive method's typical in-sample error.
    """
    training = np.asarray(training_series, dtype=float)
    scale = np.abs(training[season:] - training[:-season]).mean()
    return mae(actual, predicted) / scale


def wape(actual, predicted) -> float:
    """Return total absolute error as a share of total actual volume."""
    actual, predicted = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    return float(np.abs(actual - predicted).sum() / actual.sum())
