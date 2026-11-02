# Phase 7: Evaluation and comparison

## Locked plan

This plan was written before the holdout was opened. Nothing here changes after seeing results.

**Data:** models train on `period == "development"` rows and are scored on `period == "holdout"` rows, which are orders from 2018-06-01 to 2018-08-21. Embargo rows are used for neither.

**Frozen choices:** model families, settings, alert cutoffs, and the promise margin come from `reports/tuned_models.json`. Forecast models are trained once. Their lag features are always at least 28 days old.

**Comparison:** each tuned model faces the best simple rule from Phase 5, chosen on development scores. The linear model is reported too.

| Problem | Primary metric | Simple rule |
|---|---|---|
| 1. Late delivery | PR-AUC | Rate by same-state route |
| 2. Low review | PR-AUC | Rate by overdue |
| 3. Daily orders | MAE | Mean of 28 days, 4 weeks ago |
| 4. Delivery time | MAE | Median by customer state |
| 5. Category demand | WAPE | Mean of 4 weeks, 4 weeks ago |
| 6. Seller inactivity | PR-AUC | Days since last sale |
| 7. Freight | MAE | Median by state pair |

**Uncertainty:** a 95% bootstrap interval on the tuned model's improvement over the simple rule, using 1,000 resamples and the project seed. Rows are resampled individually, except for forecasts, where whole weeks are resampled to keep neighbouring days together.

**Verdicts**

| Verdict | Rule |
|---|---|
| Ready | The whole interval shows an improvement, and any alert reaches at least 80% of its target precision |
| Ready for ranking only | The whole interval shows an improvement, but the alert misses that precision |
| Use the simple rule | The interval includes no improvement, or shows the model is worse |

**After the holdout:** no re-tuning or changes to settings. If a bug is found, it gets fixed and disclosed here, along with what changed.

## Results

The holdout was run once under the locked plan. A second run with the same code only confirmed the numbers. Code is in `src/models/evaluate.py`, and results are in `reports/model_comparison.md` and the `reports/holdout_*.csv` files.

| Problem | Metric | Simple rule | Tuned | Improvement (95% interval) | Locked verdict |
|---|---|---:|---:|---|---|
| 1. Late delivery | PR-AUC | 0.032 | 0.043 | 0.010 (0.007 to 0.016) | Ready for ranking only |
| 2. Low review | PR-AUC | 0.163 | 0.314 | 0.152 (0.139 to 0.166) | Ready for ranking only |
| 3. Daily orders | MAE | 57.5 | 44.7 | 12.7 (-2.7 to 25.8) | Use the simple rule |
| 4. Delivery time | MAE (days) | 4.47 | 5.75 | -1.29 (-1.34 to -1.23) | Use the simple rule |
| 5. Category demand | WAPE | 0.269 | 0.330 | -0.062 (-0.145 to -0.001) | Use the simple rule |
| 6. Seller inactivity | PR-AUC | 0.569 | 0.609 | 0.040 (0.014 to 0.064) | Ready |
| 7. Freight | MAE | 8.20 | 5.61 | 2.59 (2.47 to 2.70) | Ready |

| Alert | Target precision | Precision | Recall | Rows flagged | Actual rate |
|---|---:|---:|---:|---:|---:|
| 1. Late delivery | 25% | 3.9% | 52.5% | 50.1% | 3.7% |
| 2. Low review | 50% | 32.8% | 38.1% | 11.4% | 9.8% |
| 6. Seller inactivity | 60% | 59.5% | 52.1% | 24.6% | 28.2% |

| Promise | Mean days promised | Arrived by promise |
|---|---:|---:|
| Olist | 21.1 | 94.5% |
| Tuned 90th percentile | 23.9 | 97.9% |
| Tuned promise with margin | 28.2 | 99.1% |

## Why results differ from development

Diagnostics found no sign of a bug. The three recent-condition features checked stayed within their development ranges, and the large gaps match real changes in the data:

| Measure | Development | Holdout |
|---|---:|---:|
| Mean delivery days | 13.6 | 8.8 |
| Late rate | 7.5% | 3.7% |
| Overdue share of reviewed orders | 7.4% | 3.7% |
| Low-review rate among overdue orders | 66.1% | 46.9% |

- **Deliveries sped up.** The model predicted about 13 days a month while actual means were 8 to 9 days.
- **Olist changed its promises.** The median promise fell from 27.3 days in June to 13.9 in August, even as delivery times stayed low. The late rate climbed with it, from 1.2% to 6.8%. Models trained on earlier promises couldn't learn this.
- **Freight rose.** Mean freight went from about 20 in early 2018 to 22 to 23, though a sample of light, same-state items stayed flat. The cause isn't clear.

## Conclusions

The locked verdicts stand. Two need added context:

- **Late delivery shouldn't be deployed, despite its verdict.** It passed only because its simple rule was worse than a constant score (0.032 against 0.037). Its lift over a constant score is 1.15 times, it lost to logistic regression (0.073), and its top-scored fifth of orders is less often late (3.8%) than the middle fifth (5.6%). Its alert flags half of all orders at 3.9% precision.
- **Daily orders may deserve another look.** The model's error was lower in every month, but 12 weeks of data aren't enough to rule out luck, so the simple rule stands.

| Problem | Plan for Phase 8 |
|---|---|
| 1. Late delivery | Hold, and don't deploy until retrained on newer data |
| 2. Low review | Use for ranking, such as a daily top-N review queue, without the fixed cutoff |
| 3. Daily orders | Simple rule |
| 4. Delivery time | Simple rule, and keep Olist's promises |
| 5. Category demand | Simple rule |
| 6. Seller inactivity | Deploy, and note that days since last sale catches more revenue (33.9% against 24.3%) |
| 7. Freight | Deploy |

## Lessons

- Development scores didn't carry over, and changing conditions look like the main reason, though this can't be separated cleanly from overfitting.
- Models that lean on recent history can lag behind a sudden change.
- Any deployed model needs monitoring and regular retraining.
- The holdout is now used. Later improvements need newer data for an honest test.
