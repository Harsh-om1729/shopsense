# Model cards

One card for each of the seven problems.

**Holdout scores** come from orders between 2018-06-01 and 2018-08-21. They were measured once, on models trained only on earlier data. The packaged models were then retrained on all data with the same settings, so they have no fresh test of their own.

**Intervals** are 95% bootstrap ranges for the improvement over the simple rule. Full numbers are in `reports/model_comparison.md`.

## Shared limits

- **Historic data:** the data covers 2017 to August 2018 and ends abruptly. All dates in the app describe that period.
- **Changing conditions:** during the holdout, delivery times fell from about 13.6 to 8.8 days, and Olist sharply shortened its promised dates. Every model needs monitoring and retraining.
- **Not probabilities:** risk scores rank cases from most to least at risk. Conditions changed over time, so the scores aren't calibrated chances.

---

## 1. Late delivery risk: held

| | |
|---|---|
| **Question** | At purchase, will this order arrive after its promised date? |
| **Status** | Held, not in use. The API returns 503 with the reason |
| **Holdout** | PR-AUC 0.043, against 0.037 for a constant guess and 0.073 for logistic regression |
| **Why held** | It passed the locked rule only because its simple rule was worse than a constant guess. Its top-scored fifth of orders was late less often (3.8%) than the middle fifth (5.6%) |
| **Next step** | Retrain and test on newer data, and require beating a constant guess as well as the rule |

## 2. Low review risk: trained model, ranking only

| | |
|---|---|
| **Question** | Will a delivered order get a 1 or 2 star review? |
| **Prediction moment** | Delivery or the end of the promised day, whichever comes first. Late orders are often reviewed before they arrive |
| **Model** | Gradient boosting classifier (`low_review_risk`) |
| **Training data** | 94,600 orders, from 2017-01-05 to 2018-08-21 |
| **Holdout** | PR-AUC 0.314, against 0.163 for the rule "overdue means low". Improvement 0.152 (0.139 to 0.166) |
| **Use** | A ranked queue for support. The fixed alert reached 32.8% precision against a 50% target, so it isn't used |
| **Limits** | Reviews usually arrive a day later, so there's little time to act. Queue scores in the app come from training data |

## 3. Daily order forecast: simple rule

| | |
|---|---|
| **Question** | How many orders will be placed each day, up to 28 days ahead? |
| **Rule** | The mean of the 28 days that ended four weeks earlier, with the Black Friday peak replaced (`daily_orders_rule`) |
| **Holdout** | Rule MAE 57.5, model MAE 44.7. Improvement 12.7 (-2.7 to 25.8), which includes zero |
| **Why a rule** | The model was better every month, but 12 weeks can't rule out luck. It's worth retesting on new data |
| **Limits** | It can only forecast 28 days past the end of the data, to 2018-09-18 |

## 4. Delivery time estimate: simple rule

| | |
|---|---|
| **Question** | How many days until delivery? |
| **Rule** | The median delivery days for the customer's state (`delivery_time_rule`) |
| **Holdout** | Rule MAE 4.47 days, model 5.75. The model was clearly worse (-1.29, from -1.34 to -1.23) |
| **Use** | Internal estimates only. Keep Olist's promised dates for customers. On the holdout, Olist promised 21.1 days with 94.5% on time, beating the model's 90th-percentile promise |
| **Limits** | The medians include the slower period before the holdout, so they may run high |

## 5. Category demand forecast: simple rule

| | |
|---|---|
| **Question** | How many items will each top-10 category sell in a week, up to 4 weeks ahead? |
| **Rule** | The mean of the 4 weeks that ended 4 weeks earlier (`category_demand_rule`) |
| **Holdout** | Rule WAPE 0.269, model 0.330. The model was worse (-0.062, from -0.145 to -0.001) |
| **Limits** | Covers the top 10 categories only. There are about 74 weeks of history |

## 6. Seller inactivity risk: trained model

| | |
|---|---|
| **Question** | At a month start, will an active seller make no sale in the next 60 days? |
| **Model** | Gradient boosting classifier with a fixed alert cutoff (`seller_inactivity_risk`) |
| **Training data** | 16,390 seller snapshots, from 2017-04-01 to 2018-06-01 |
| **Holdout** | PR-AUC 0.609, against 0.569 for days since last sale. Improvement 0.040 (0.014 to 0.064). The alert reached 59.5% precision and 52.1% recall, flagging 24.6% of sellers |
| **Limits** | Days since last sale caught more at-risk revenue (33.9% against 24.3%), so check both. The holdout had a single snapshot of 1,555 sellers. No account records exist, so inactivity doesn't prove a seller left. The cutoff was set before the final retraining |

## 7. Freight cost estimate: trained model

| | |
|---|---|
| **Question** | What will the freight be for one product on a route? |
| **Model** | Gradient boosting regressor with an absolute-error loss (`freight_cost`) |
| **Training data** | 101,367 product rows, from 2017-01-05 to 2018-08-21 |
| **Holdout** | MAE 5.61, against 8.20 for the median by state pair. Improvement 2.59 (2.47 to 2.70) |
| **Limits** | Freight rose during the holdout for unclear reasons, and error rose from 3.54 in development. It's unreliable without weight and dimensions, so the site requires them. The data doesn't show how freight is calculated |
