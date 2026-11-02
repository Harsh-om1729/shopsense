# Phase 5: Baselines

Forecast scores here predate the Black Friday fix. Phase 6 rescored them, and `docs/phase_06_tuning.md` has current numbers.

The code is in `src/models/`. Scores are in `reports/model_comparison.md`, with every fold in `reports/baseline_folds.csv`. The holdout wasn't used, and `evaluate_problem` raises an error if it's given any non-development row.

## Validation

- **Row-level problems (1, 2, 4, 6, 7):** four two-month validation windows, from September 2017 to April 2018.
- **Training rows:** they must come before the window, and their outcome must have been known when it began. Problems 1, 2, and 4 also leave a 30-day gap. Problem 6 is protected by its known-outcome rule, and problem 7 has no delay.
- **Forecasts (3, 5):** six consecutive 28-day windows ending at the holdout.
- **Pipelines:** imputation, scaling, and encoding are fitted on each fold's training rows only.
- **Alert precision:** 25% for late delivery, 50% for low reviews, and 60% for seller inactivity. These are assumptions set before seeing results, since the data has no cost for a false alarm.

Phase 2's baseline for problem 3 was corrected. The same weekday last week isn't available 28 days ahead, so the baseline is the same weekday four weeks earlier.

## Scores to beat

These are means across folds. No baseline was tuned.

| Problem | Metric | Simple rule | Best rule score | Linear model | Bar to beat |
|---|---|---|---:|---:|---:|
| 1. Late delivery | PR-AUC | Rate by same-state route | 0.108 | 0.137 | 0.137 |
| 2. Low review | PR-AUC | Rate by overdue | 0.342 | 0.469 | 0.469 |
| 3. Daily orders | MAE | Mean of 28 days, 4 weeks ago | 53.5 | 49.2 | 49.2 |
| 4. Delivery time | MAE (days) | Median by customer state | 5.97 | 5.74 | 5.74 |
| 5. Category demand | WAPE | Mean of 4 weeks, 4 weeks ago | 0.358 | 0.318 | 0.318 |
| 6. Seller inactivity | PR-AUC | Days since last sale | 0.558 | 0.582 | 0.582 |
| 7. Freight | MAE | Median by state pair | 5.85 | 4.78 | 4.78 |

The linear model has the best primary score on all seven, but two secondary results favour simple rules:

- **Problem 6:** days since last sale catches more at-risk revenue, 34.6% against 31.6%.
- **Problem 7:** median by state pair has the better MAPE, 0.460 against 0.507.

## What the folds show

**Late rates shift between training and validation.** The training late rate is 3.3% to 5.4%, while three of the four validation windows run from 9.7% to 11.3%. A model trained on calm months is tested on bad ones, so these scores measure how well it handles change.

**PR-AUC must be read against each window's late rate.** A constant score gets the late rate itself, so the mean of 0.137 hides this:

| Window | Late rate (constant score) | Logistic regression | Lift |
|---|---:|---:|---:|
| Sep-Oct 2017 | 0.043 | 0.090 | 2.1 times |
| Nov-Dec 2017 | 0.103 | 0.106 | 1.0 times |
| Jan-Feb 2018 | 0.097 | 0.151 | 1.6 times |
| Mar-Apr 2018 | 0.113 | 0.200 | 1.8 times |

In November and December the linear model was no better than a constant score, and the same-state rule beat it (0.126). This is the first time the model meets a peak season, and it's the main weakness to fix.

**Black Friday damages forecast lags.** In the window from 15 December 2017 the lags still contain the 1,176-order peak, so they average 294.5 orders against 170.8 actual. This is the worst window for most forecast baselines.

**The last forecast window is also weak.** Orders from 4 to 31 May 2018 average 214.9, and every baseline's error is about 76 to 84. The data doesn't explain this drop, so it's noted as unexplained.

**Accuracy and promises pull in opposite directions.** On problem 4, Olist's promise has a 11.9-day MAE but 89.8% of orders arrive by it. The linear model has a 5.7-day MAE, but only 45.3% arrive by its prediction. A model that minimises error aims for the middle, so about half of orders would be late against that date.

## Caveats

- **Recall scores are slightly optimistic.** Recall at a chosen precision picks its cutoff on the same window it reports, and the true cutoff must be chosen on earlier data. Fix this before Phase 7's final test.
- **MASE above 1:** forecasts average 1.44 to 1.94, so they're less accurate 28 days ahead than a one-week-ahead naive method on training data. That's expected at this horizon.
- **Few forecast windows:** six windows with one peak give a rough estimate only.

## Priorities for Phase 6

1. Handle Black Friday in forecast lags, for example by capping or masking the peak.
2. Judge problem 1 by its Nov-Dec lift, not only by the mean.
3. For problem 4, predict an upper range, such as the 90th percentile, rather than the middle. Then compare it with Olist's on-time share.
4. Set alert cutoffs on earlier data.
5. Try tree-based models and compare them fold by fold with these scores.

## Verify

```bash
uv run python -m src.data.make_dataset
uv run python -m src.features.make_features
uv run python -m src.models.run_baselines
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
