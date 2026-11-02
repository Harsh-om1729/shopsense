# Phase 8: Model packaging

The code is in `src/models/package.py` and `src/models/predictor.py`. Packages are saved to `models/` and aren't committed, so rebuild them with the command below. `reports/model_registry.json` is the tracked record of what exists.

## Packages

| Package | Problem | Type | Output | Status |
|---|---|---|---|---|
| `low_review_risk` | 2 | Trained model | `risk_score`, `rank` | Active, ranking only |
| `seller_inactivity_risk` | 6 | Trained model | `risk_score`, `is_alert` | Active |
| `freight_cost` | 7 | Trained model | `predicted_freight` | Active |
| `daily_orders_rule` | 3 | Simple rule | `predicted_orders` | Active |
| `delivery_time_rule` | 4 | Simple rule | `predicted_days` | Active |
| `category_demand_rule` | 5 | Simple rule | `predicted_items` | Active |
| `late_delivery_risk` | 1 | None | None | Held |

## Using a package

```python
from src.models.predictor import load_predictor

predictor = load_predictor("freight_cost")
predictions = predictor.predict(rows)
```

| Package | Input columns |
|---|---|
| Trained models | The columns in `FEATURES` from `src/features/build.py` |
| `daily_orders_rule` | `date` |
| `delivery_time_rule` | `customer_state` |
| `category_demand_rule` | `week_end` (a Sunday) and `category` |

`InvalidInputError` means the caller can fix the request, and `ModelNotAvailableError` means the package is held, missing, or built with a different scikit-learn version.

## Decisions

- **Trained models are refitted on all known data** with frozen settings, up to 2018-08-21. Conditions shifted, so they need the newest orders. Holdout scores come from the earlier fit, and metadata says so.
- **Rules are JSON** so they can be read and checked by hand.
- **Lag code is shared** between training and serving through `daily_lag_input` and `weekly_lag_input`.
- **The low-review package has no alert,** because the fixed cutoff missed its target on the holdout.
- **Asking for the held model gives its reason** rather than a prediction.

## Checks

| Check | Result |
|---|---|
| Packaging code fitted on development rows reproduces Phase 7 holdout scores | Matches on all 3 models |
| Packages load and predict in a fresh process | Passed for all 6 |
| Predictions are identical after saving and reloading | Passed for all 3 models |
| Forecast rules match the training features | Passed on all real rows |
| Bad input and out-of-range dates are rejected | Passed |

## Known gaps

- **Refitted models have no fresh test.** The seller cutoff was also set before the refit, so check its alert rate on new data.
- **Trained models need feature rows.** Many features are history, such as `seller_late_rate`, and Phases 9 and 10 must supply them. They must come from the same logic as `src/features/`, or skew returns.
- **Forecast rules end soon after the data.** Daily forecasts stop at 2018-09-18 and weekly forecasts at 2018-09-16, until they're rebuilt with newer data.
- **Delivery medians include the slower period,** so they may run high.
- **Packages need the same scikit-learn version,** which `uv.lock` pins.

## Verify

```bash
uv run python -m src.models.package
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
