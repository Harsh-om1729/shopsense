# Phase 6: Training and tuning

The code is in `src/models/tuned.py` and `src/models/tune.py`. Chosen settings are in `reports/tuned_models.json`, every trial is in `reports/tuning_results.csv`, and fold scores are in `reports/tuned_folds.csv`. `reports/model_comparison.md` shows baselines and tuned models together. Final models are trained in Phase 7, and the holdout hasn't been used.

## Changes

- **Black Friday in lags:** days 24 to 28 November 2017 are replaced in lag features by the value a week earlier, and peak weeks by the last normal week. Targets keep the real values, and `is_peak_window` and `is_peak_week` mark the peak. This improved the baselines, so forecast scores in `docs/phase_05_baselines.md` are out of date. Current scores are in the table below.
- **Models:** gradient boosting for row-level problems, and tuned ridge against boosted ratio forecasts for problems 3 and 5.
- **Search:** up to 8 fixed-seed settings per model family, scored on the same time folds. Built-in early stopping is off, because it holds out random rows.
- **Selection:** the best mean primary metric across folds.

## Results

These are means across development folds. Baselines are the best from Phase 5, rescored after the Black Friday fix.

| Problem | Metric | Best baseline | Tuned model | Chosen model | Result |
|---|---|---:|---:|---|---|
| 1. Late delivery | PR-AUC, higher is better | 0.137 | **0.186** | Boosted classifier | Better |
| 2. Low review | PR-AUC, higher is better | 0.469 | **0.487** | Boosted classifier | Slightly better |
| 3. Daily orders | MAE, lower is better | 43.4 | **41.5** | Ridge, alpha 100 | Slightly better |
| 4. Delivery time | MAE in days, lower is better | 5.74 | **5.34** | Boosted median | Better |
| 5. Category demand | WAPE, lower is better | 0.2787 | **0.2783** | Ridge, alpha 0.1 | Tied |
| 6. Seller inactivity | PR-AUC, higher is better | 0.582 | **0.600** | Boosted classifier | Slightly better |
| 7. Freight | MAE, lower is better | 4.78 | **3.54** | Boosted median | Much better |

Boosted ratio forecasts lost clearly on both forecast problems, at 56.5 against 41.5 for daily orders and 0.317 against 0.278 for categories. With so few rows, the regularized linear models are safer.

## Late delivery by window

| Window | Constant score | Logistic regression | Tuned model | Lift over constant |
|---|---:|---:|---:|---:|
| Sep-Oct 2017 | 0.043 | 0.090 | 0.076 | 1.8 times |
| Nov-Dec 2017 | 0.103 | 0.106 | 0.153 | 1.5 times |
| Jan-Feb 2018 | 0.097 | 0.151 | 0.232 | 2.4 times |
| Mar-Apr 2018 | 0.113 | 0.200 | 0.284 | 2.5 times |

The peak-season weakness improved, from 1.0 to 1.5 times the constant score. The tuned model lost to logistic regression in the first window, when it had the least training data.

## Alerts tested on later data

Each cutoff was set on earlier folds, then tested on the next fold. These results replace the optimistic Phase 5 recall figures.

| Problem | Target precision | Precision by window | Mean precision | Mean recall |
|---|---:|---|---:|---:|
| 1. Late delivery | 25% | 14.8%, 40.6%, 39.3% | 31.6% | 11.6% |
| 2. Low review | 50% | 62.7%, 52.1%, 49.7% | 54.9% | 58.0% |
| 6. Seller inactivity | 60% | 61.4%, 68.4%, 65.1% | 65.0% | 41.5% |

- **Low review** and **seller inactivity** alerts hold their targets well.
- **Late delivery** alerts are unreliable. Precision swings widely and they catch only about 1 late order in 9.

## Delivery promises

Compared on the three windows where a margin can be set from earlier data:

| Promise | Mean days promised | Arrived by promise |
|---|---:|---:|
| Olist | 24.3 | 88.1% |
| Tuned 90th percentile | 20.1 | 81.2% |
| Tuned 90th percentile plus margin | 24.2 | 87.7% |

The model is a better estimator of delivery time, but it doesn't support shorter promises at the same reliability. Promising about 4 days sooner would cost about 7 points of on-time share. Which trade-off is right is a business decision, and the margin is also uneven by window (79.1%, 90.9%, 93.2%).

## Caveats

- **Scores are slightly optimistic.** Settings were chosen on the same folds that report them. The holdout gives the unbiased test.
- **Some settings sit at the edge of the search.** Late delivery and seller inactivity chose the smallest models tried, and freight chose one of the largest. A wider search might help freight, but small gains there aren't a priority.
- **Tiny margins aren't meaningful.** Problem 5 is a tie, and problems 2, 3, and 6 gain little over simple models.
- **Seller revenue:** days since last sale still catches more at-risk revenue, 34.6% against 32.0%, because the model was chosen on PR-AUC.
- **Probabilities aren't calibrated.** Training late rates sit below later ones, so scores should be used for ranking. The late alert cutoff is only 8.8%, for example.

## Verify

```bash
uv run python -m src.features.make_features
uv run python -m src.models.run_baselines
uv run python -m src.models.tune
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Tuning takes about 6 minutes.
