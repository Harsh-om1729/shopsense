# Model comparison

Baseline scores from time-based validation on development rows.
The holdout hasn't been used. See `docs/phase_05_baselines.md`.

## 1. Late delivery risk

Primary metric: `pr_auc`. Higher is better.

| Baseline | Metric | Mean | Std | Lowest fold | Highest fold |
|---|---|---:|---:|---:|---:|
| Overall rate | `pr_auc` | 0.0890 | 0.0315 | 0.0428 | 0.1131 |
| Overall rate | `recall_at_precision` | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Rate by same-state route | `pr_auc` | 0.1079 | 0.0464 | 0.0406 | 0.1465 |
| Rate by same-state route | `recall_at_precision` | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Logistic regression | `pr_auc` | 0.1365 | 0.0495 | 0.0900 | 0.2000 |
| Logistic regression | `recall_at_precision` | 0.0808 | 0.1251 | 0.0000 | 0.2637 |

## 2. Low review risk

Primary metric: `pr_auc`. Higher is better.

| Baseline | Metric | Mean | Std | Lowest fold | Highest fold |
|---|---|---:|---:|---:|---:|
| Overall rate | `pr_auc` | 0.1479 | 0.0280 | 0.1063 | 0.1647 |
| Overall rate | `recall_at_precision` | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Rate by overdue | `pr_auc` | 0.3422 | 0.0973 | 0.1975 | 0.4003 |
| Rate by overdue | `recall_at_precision` | 0.3819 | 0.1165 | 0.2097 | 0.4671 |
| Logistic regression | `pr_auc` | 0.4686 | 0.1096 | 0.3076 | 0.5451 |
| Logistic regression | `recall_at_precision` | 0.5131 | 0.1653 | 0.2693 | 0.6246 |

## 3. Daily order forecast

Primary metric: `mae`. Lower is better.

| Baseline | Metric | Mean | Std | Lowest fold | Highest fold |
|---|---|---:|---:|---:|---:|
| Same weekday 4 weeks ago | `mae` | 66.6488 | 42.7628 | 31.2143 | 141.3929 |
| Same weekday 4 weeks ago | `mase` | 1.9433 | 1.2762 | 0.9015 | 4.2020 |
| Mean of 28 days, 4 weeks ago | `mae` | 53.4828 | 19.7601 | 34.4464 | 78.8865 |
| Mean of 28 days, 4 weeks ago | `mase` | 1.5573 | 0.5980 | 0.9932 | 2.3444 |
| Ridge regression | `mae` | 49.1883 | 32.7497 | 23.9102 | 97.4770 |
| Ridge regression | `mase` | 1.4403 | 0.9836 | 0.6894 | 2.8969 |

## 4. Delivery time estimate

Primary metric: `mae`. Lower is better.

| Baseline | Metric | Mean | Std | Lowest fold | Highest fold |
|---|---|---:|---:|---:|---:|
| Olist's promised days | `mae` | 11.8860 | 0.4623 | 11.4018 | 12.5108 |
| Olist's promised days | `share_by_predicted` | 0.8975 | 0.0342 | 0.8708 | 0.9475 |
| Overall median | `mae` | 6.8089 | 1.2070 | 5.0498 | 7.6618 |
| Overall median | `share_by_predicted` | 0.4451 | 0.0749 | 0.3697 | 0.5191 |
| Median by customer state | `mae` | 5.9704 | 1.2146 | 4.2587 | 6.8801 |
| Median by customer state | `share_by_predicted` | 0.4240 | 0.0832 | 0.3439 | 0.5122 |
| Ridge regression | `mae` | 5.7386 | 1.4070 | 3.9164 | 7.2878 |
| Ridge regression | `share_by_predicted` | 0.4532 | 0.1477 | 0.2538 | 0.6105 |

## 5. Category demand forecast

Primary metric: `wape`. Lower is better.

| Baseline | Metric | Mean | Std | Lowest fold | Highest fold |
|---|---|---:|---:|---:|---:|
| Mean of 4 weeks, 4 weeks ago | `wape` | 0.3582 | 0.2091 | 0.1878 | 0.7625 |
| Ridge regression | `wape` | 0.3176 | 0.1386 | 0.1715 | 0.5676 |

## 6. Seller inactivity risk

Primary metric: `pr_auc`. Higher is better.

| Baseline | Metric | Mean | Std | Lowest fold | Highest fold |
|---|---|---:|---:|---:|---:|
| Overall rate | `pr_auc` | 0.2709 | 0.0164 | 0.2575 | 0.2918 |
| Overall rate | `recall_at_precision` | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Overall rate | `revenue_recall` | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Days since last sale | `pr_auc` | 0.5581 | 0.0257 | 0.5304 | 0.5893 |
| Days since last sale | `recall_at_precision` | 0.4650 | 0.1006 | 0.3474 | 0.5786 |
| Days since last sale | `revenue_recall` | 0.3458 | 0.1008 | 0.2336 | 0.4765 |
| Logistic regression | `pr_auc` | 0.5822 | 0.0313 | 0.5558 | 0.6205 |
| Logistic regression | `recall_at_precision` | 0.4712 | 0.1251 | 0.3440 | 0.6050 |
| Logistic regression | `revenue_recall` | 0.3159 | 0.0994 | 0.2243 | 0.4488 |

## 7. Freight cost estimate

Primary metric: `mae`. Lower is better.

| Baseline | Metric | Mean | Std | Lowest fold | Highest fold |
|---|---|---:|---:|---:|---:|
| Overall median | `mae` | 7.3627 | 0.9012 | 6.5711 | 8.6440 |
| Overall median | `mape` | 0.5658 | 0.1393 | 0.3862 | 0.7224 |
| Median by state pair | `mae` | 5.8455 | 0.9075 | 5.0975 | 7.1560 |
| Median by state pair | `mape` | 0.4603 | 0.1102 | 0.3018 | 0.5495 |
| Ridge regression | `mae` | 4.7752 | 0.7306 | 4.2488 | 5.8493 |
| Ridge regression | `mape` | 0.5073 | 0.1566 | 0.2992 | 0.6793 |
