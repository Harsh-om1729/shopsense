# Phase 4: Feature engineering

The code is in `src/features/`. `FEATURES` in `src/features/build.py` lists the columns each model may use. Feature tables are saved to `data/processed/features/`, and they aren't committed.

No features were dropped. Scoring them with a model comes in Phases 5 and 6, and encoding and scaling belong in model pipelines.

## Tables

| Table | Problems | Rows | Features | Prediction moment |
|---|---|---:|---:|---|
| `delivery` | 1, 4 | 95,522 | 25 | Purchase |
| `reviews` | 2 | 94,600 | 34 | Delivery or end of promised day |
| `daily_orders` | 3 | 594 | 10 | Forecast start, 28 days ahead |
| `weekly_category` | 5 | 840 | 8 | Forecast start, 4 weeks ahead |
| `seller_snapshots` | 6 | 16,390 | 10 | Month start |
| `freight` | 7 | 101,367 | 10 | Checkout |

## How leakage is prevented

- **History counts from when an outcome was known.** `past_totals` in `src/features/common.py` counts an outcome only if it was known strictly before the row's moment. Delivery outcomes count from the delivery date, and review scores from when the customer answered.
- **Rates are smoothed.** `PRIOR_WEIGHT = 20` pulls a small group's rate toward the overall past rate, so one late order doesn't make a seller look 100% late.
- **Lags match the forecast horizon.** Daily lags are at least 28 days old and weekly lags at least 4 weeks old.
- **Overdue orders hide their final delivery.** Problem 2 sees only what was known at the prediction moment.

## Main features

- **Delivery:** distance, route, promised days, order size and value, seller history, route history, and recent platform conditions.
- **Reviews:** all of the above, plus `is_overdue`, timing so far, seller and category review history, and recent low-review rate.
- **Forecasts:** lags, rolling means, weekday, holidays, the Black Friday flag, and a time index.
- **Sellers:** recent sales, revenue, days since the last sale, tenure, and past late and low-review rates.
- **Freight:** distance, same-state flag, weight, volume, longest side, price, and quantity.

## Checks

- **Corruption test:** `tests/test_feature_leakage.py` changes every outcome known from the holdout onward and rebuilds the features. Development rows must stay identical across all six tables.
- **Proof the test works:** when a leak was injected on purpose, the test's comparison flagged the tables that use history.
- **Leak alarm:** `make_features` warns if any feature's Spearman correlation with a target reaches 0.9. None did.
- **Signal report:** `reports/feature_signal.csv` lists each numeric feature's correlation and missing share on development rows.

## Signal on development rows

| Target | Strongest features (Spearman) |
|---|---|
| Late delivery | `recent_orders` 0.14, `route_mean_days` 0.14, `route_late_rate` 0.13 |
| Delivery days | `distance_km` 0.54, `route_mean_days` 0.54, `days_promised` 0.50 |
| Low review | `is_overdue` 0.43, `days_to_moment` 0.22, `n_items` 0.14 |
| Daily orders | `days_since_start` 0.83, `lag_42` 0.77, `lag_35` 0.76 |
| Weekly category items | `mean_4_lag_4` 0.75, `lag_6` 0.73, `lag_4` 0.73 |
| Seller inactivity | `sales_30d` -0.48, `sales_90d` -0.45, `days_since_last_sale` 0.45 |
| Freight | `distance_km` 0.63, `same_state` -0.60, `product_weight_g` 0.45 |

Spearman only measures steady increases or decreases, so a low value doesn't prove a feature is useless. `purchase_hour` could still matter in a non-linear way, for example.

## Notes for Phase 5

- **Late delivery is the hardest problem.** No single feature passes 0.15, so it depends on combinations, and the correlations may partly reflect changes over time.
- **Time trends:** tree models can't extrapolate a rising trend, so check forecasts for this.
- **Missing values:** forecast lags are missing at the start of each series, so those rows can't be used. Seller rates are missing for sellers with no past outcomes, and pipelines need to handle this.
- **One peak:** Black Friday appears once in development and never in the holdout.

## Verify

```bash
uv run python -m src.data.make_dataset
uv run python -m src.features.make_features
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
