# Phase 2: EDA and problem definitions

Evidence is in `notebooks/01_eda.ipynb`. No models were fitted, so these numbers show the data can support each problem but not how well a model will perform.

All seven problems are final. Phase 3 corrected three rules below, and `docs/phase_03_preprocessing.md` explains why.

## Rules for every problem

- **Date range:** use orders from 2017-01-01 to 2018-08-21. 2016 is too thin, and daily orders fade out after 21 August 2018, which looks like an extraction cut-off.
- **Final test period:** orders purchased from `HOLDOUT_START` (2018-06-01) through 2018-08-21. Use it once, in Phase 7.
- **Validation:** always train on the past and validate on the future. Late rates moved from 2.8% to 19.0% across months, so random splits would give a false picture. Leave the same kind of gap between training and validation folds.
- **Embargo:** exclude rows from the 30 days before `HOLDOUT_START`, plus any row whose outcome came on or after it. Dropping only unfinished orders would remove slow deliveries.
- **Leakage:** use only what was known at the prediction moment.
- **Row counts:** aggregate items and payments before joining, and keep one review per order, the most recently answered.

## The seven problems

| # | Problem | Type | Prediction moment |
|---|---|---|---|
| 1 | Late delivery risk | Binary classification | Purchase |
| 2 | Low review risk | Binary classification | Delivery or end of promised day, whichever comes first |
| 3 | Daily order forecast | Time series | Start of forecast window |
| 4 | Delivery time estimate | Regression | Purchase |
| 5 | Category demand forecast | Time series | Start of forecast window |
| 6 | Seller inactivity risk | Binary classification | Monthly snapshot |
| 7 | Freight cost estimate | Regression | Checkout |

### 1. Late delivery risk

- **Business use:** flag orders that may miss their promised date, so the team can act before the customer complains.
- **Target:** the delivered calendar date is after `order_estimated_delivery_date`.
- **Rows:** delivered orders with a delivery date. The development late rate is 7.53% (77,867 orders).
- **Metrics:** PR-AUC, plus recall at a chosen precision. Accuracy would mislead, because always predicting "on time" scores about 92%.
- **Baselines:** the overall late rate, and the late rate by same-state vs different-state route.
- **Evidence:** the late rate rises from 3.9% in the shortest distance group to 11.1% in the longest. It's 4.3% within a state and 9.3% across states.
- **Never use:** any delivered date, order status, or review field.

### 2. Low review risk

- **Business use:** find unhappy customers so support can contact them first.
- **Target:** `review_score` of 1 or 2. This is simpler to act on than predicting all five scores.
- **Rows:** delivered orders with a review, excluding reviews created before the prediction moment. The development low rate is 13.76% (70,275 orders).
- **Metrics:** PR-AUC, plus recall at a chosen precision.
- **Baselines:** the overall low rate, and the rule "overdue means low review".
- **Evidence:** the low rate is 66.1% for overdue orders and 9.6% for the rest. But most low reviews are on orders that weren't late, and orders with three or more items have a 32.7% low rate.
- **Prediction moment:** 87.5% of reviews are created one day after delivery or the promised date, whichever comes first. So a late order is often reviewed before it arrives, and "at delivery" would be too late.
- **Allowed:** `is_overdue`, plus any delivery date known at the moment.
- **Never use:** any review field, or the final delivery date of an overdue order.
- **Limit:** the survey usually arrives about a day later, so there's little time to act.

### 3. Daily order forecast

- **Business use:** plan staffing, stock, and logistics capacity.
- **Target:** orders per day, 28 days ahead. Order count is steadier than revenue, and the same pipeline can forecast revenue later.
- **Metrics:** MAE and MASE across several forecast start dates.
- **Baseline:** the same weekday four weeks earlier, the most recent one available 28 days ahead.
- **Evidence:** 512 days with no gaps, a weekly pattern (lag 7 autocorrelation 0.655), and fewer orders at weekends.
- **Limit:** 24 November 2017 (1,176 orders) is the only peak of its kind. Treat it as a known holiday event, because yearly seasonality can't be learned from one example.

### 4. Delivery time estimate

- **Business use:** promise customers a more accurate date than the current estimate.
- **Target:** days from purchase to customer delivery.
- **Rows:** the same as problem 1.
- **Metric:** MAE, plus the share of orders that arrive by the predicted date.
- **Baselines:** Olist's promised days, and the median days by customer state.
- **Evidence:** the median is 11.2 days actual against 23.5 days promised, and the Spearman correlation with distance is 0.54.
- **Limit:** a tighter promise can create more late orders, so it must be evaluated against problem 1.

### 5. Category demand forecast

- **Business use:** help sellers and logistics plan by category.
- **Target:** items sold per week for the top 10 categories, 4 weeks ahead.
- **Metric:** WAPE across several forecast start dates.
- **Baseline:** the mean of the previous 4 weeks.
- **Evidence:** the top 10 categories hold 64.8% of items, and the largest sell about 90 to 120 items a week.
- **Limit:** there are only about 74 development weeks.

### 6. Seller inactivity risk

- **Business use:** contact valuable sellers before they stop selling. The top 10% of sellers bring in 66.7% of revenue.
- **Target:** at each month start, a seller with a sale in the past 90 days has no sale in the next 60 days.
- **Metric:** PR-AUC, plus revenue-weighted recall.
- **Baseline:** days since the seller's last sale.
- **Evidence:** 2,559 sellers, and the development target rate is 27.93% across 13,348 seller snapshots.
- **Limit:** the data has no seller account records, so inactivity doesn't prove a seller left. Many sellers have few orders (median 6). The holdout has only one snapshot (2018-06-01), because later ones lack 60 days of future data.

### 7. Freight cost estimate

- **Business use:** show sellers the likely shipping cost before they list a product on a route.
- **Target:** `freight_value` per item.
- **Metric:** MAE, plus MAPE on non-zero rows.
- **Baseline:** the median freight by seller state and customer state.
- **Evidence:** 91,231 item rows. Spearman correlation with distance is 0.63 and with weight is 0.45.
- **Limit:** this has the weakest business case of the seven. If Olist's freight comes from a carrier rate table, a model only approximates a formula. The data doesn't show how freight is set.

## Rejected candidates

| Candidate | Reason |
|---|---|
| Repeat purchase | 1,478 repeats within 90 days out of 58,033 first orders (2.55%) |
| Customer segmentation | 97.0% of customers have one order, so behaviour barely varies |
| Cancellation risk | 1,043 cases (1.30%), and no cancellation timestamp to set a prediction moment |
| Product recommendation | 54.8% of products sold once, and most customers have one order |
| Review sentiment | The score is already known, so a text model adds little business value |

## Other findings to keep in mind

- 959 orders with two or more sellers were rarely late (1.4%) but often got low reviews (48.9%). The data has only one delivery date per order, so split shipments may be hidden. This is a hypothesis.
- 197 development orders have conflicting review scores, and 1,440 development review rows share a `review_id` with another row.

## Verify

```bash
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/01_eda.ipynb
uv run pytest
uv run ruff check .
```
