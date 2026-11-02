"""Time-based validation folds. Random splits would let models see the future."""

from dataclasses import dataclass

import pandas as pd

from src import config

# Two-month validation windows, ending where the embargo begins.
FOLD_STARTS = ["2017-09-01", "2017-11-01", "2018-01-01", "2018-03-01"]
FOLD_MONTHS = 2

FORECAST_FOLDS = 6
FORECAST_DAYS = 28


@dataclass(frozen=True)
class Fold:
    name: str
    start: pd.Timestamp
    end: pd.Timestamp


def tabular_folds() -> list[Fold]:
    """Return the validation windows for row-level problems."""
    folds = []
    for start in pd.to_datetime(FOLD_STARTS):
        end = start + pd.DateOffset(months=FOLD_MONTHS)
        folds.append(Fold(f"{start:%Y-%m}", start, end))
    return folds


def forecast_folds() -> list[Fold]:
    """Return consecutive forecast windows ending at the holdout."""
    holdout_start = pd.Timestamp(config.HOLDOUT_START)
    window = pd.Timedelta(days=FORECAST_DAYS)
    starts = [holdout_start - window * step for step in range(FORECAST_FOLDS, 0, -1)]
    return [Fold(f"{start:%Y-%m-%d}", start, start + window) for start in starts]


def split_fold(table, fold, time_column, known_column=None, gap_days=0):
    """Return train and validation rows for one fold.

    Training rows must fall before the gap, and their outcome must have been
    known when the validation window began.
    """
    times = table[time_column]
    in_validation = (times >= fold.start) & (times < fold.end)
    in_training = times < fold.start - pd.Timedelta(days=gap_days)
    if known_column is not None:
        in_training &= table[known_column] < fold.start
    return table[in_training], table[in_validation]
