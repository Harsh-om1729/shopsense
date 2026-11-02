# Model comparison

## Final holdout results

Orders from 2018-06-01 to 2018-08-21. Rules are in `docs/phase_07_evaluation.md`.

| Problem | Metric | Simple rule | Tuned | Improvement (95% interval) | Verdict |
|---|---|---:|---:|---|---|
| 1. Late delivery risk | `pr_auc` | 0.0322 | 0.0427 | 0.0104 (0.0068 to 0.0162) | Ready for ranking only |
| 2. Low review risk | `pr_auc` | 0.1626 | 0.3141 | 0.1515 (0.1385 to 0.1663) | Ready for ranking only |
| 3. Daily order forecast | `mae` | 57.4699 | 44.7316 | 12.7383 (-2.6520 to 25.7639) | Use the simple rule |
| 4. Delivery time estimate | `mae` | 4.4667 | 5.7542 | -1.2874 (-1.3408 to -1.2300) | Use the simple rule |
| 5. Category demand forecast | `wape` | 0.2685 | 0.3303 | -0.0617 (-0.1446 to -0.0013) | Use the simple rule |
| 6. Seller inactivity risk | `pr_auc` | 0.5685 | 0.6085 | 0.0399 (0.0138 to 0.0637) | Ready |
| 7. Freight cost estimate | `mae` | 8.1997 | 5.6130 | 2.5867 (2.4665 to 2.6983) | Ready |

| Alert | Target precision | Precision | Recall | Rows flagged | Actual rate |
|---|---:|---:|---:|---:|---:|
| 1. Late delivery risk | 25% | 3.9% | 52.5% | 50.1% | 3.7% |
| 2. Low review risk | 50% | 32.8% | 38.1% | 11.3% | 9.8% |
| 6. Seller inactivity risk | 60% | 59.5% | 52.1% | 24.6% | 28.2% |

| Promise | Mean days promised | Arrived by promise |
|---|---:|---:|
| Olist's promised days | 21.1 | 94.5% |
| Tuned 90th percentile promise | 23.9 | 97.9% |
| Tuned promise with margin | 28.2 | 99.1% |

Scores below come from time-based validation on development rows.

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
| Tuned model | `pr_auc` | 0.1864 | 0.0913 | 0.0761 | 0.2844 |
| Tuned model | `recall_at_precision` | 0.2255 | 0.2585 | 0.0015 | 0.5081 |
| Tuned model | `forward_precision` | 0.3159 | 0.1452 | 0.1484 | 0.4063 |
| Tuned model | `forward_recall` | 0.1162 | 0.0906 | 0.0144 | 0.1883 |

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
| Tuned model | `pr_auc` | 0.4867 | 0.1123 | 0.3214 | 0.5622 |
| Tuned model | `recall_at_precision` | 0.5272 | 0.1696 | 0.2781 | 0.6481 |
| Tuned model | `forward_precision` | 0.5486 | 0.0693 | 0.4973 | 0.6274 |
| Tuned model | `forward_recall` | 0.5802 | 0.0871 | 0.4831 | 0.6512 |

## 3. Daily order forecast

Primary metric: `mae`. Lower is better.

| Baseline | Metric | Mean | Std | Lowest fold | Highest fold |
|---|---|---:|---:|---:|---:|
| Same weekday 4 weeks ago | `mae` | 55.4167 | 23.8901 | 31.2143 | 80.7500 |
| Same weekday 4 weeks ago | `mase` | 1.6095 | 0.6984 | 0.9015 | 2.3828 |
| Mean of 28 days, 4 weeks ago | `mae` | 48.1601 | 15.3659 | 34.4464 | 76.0867 |
| Mean of 28 days, 4 weeks ago | `mase` | 1.3991 | 0.4572 | 0.9932 | 2.2452 |
| Ridge regression | `mae` | 43.3807 | 21.9492 | 25.4337 | 80.7204 |
| Ridge regression | `mase` | 1.2659 | 0.6606 | 0.7421 | 2.3819 |
| Tuned model | `mae` | 41.4614 | 19.6203 | 21.9386 | 74.0305 |
| Tuned model | `mase` | 1.2078 | 0.5872 | 0.6325 | 2.1845 |

## 4. Delivery time estimate

Primary metric: `mae`. Lower is better.

| Baseline | Metric | Mean | Std | Lowest fold | Highest fold |
|---|---|---:|---:|---:|---:|
| Olist's promised days | `mae` | 11.8860 | 0.4623 | 11.4018 | 12.5108 |
| Olist's promised days | `share_by_predicted` | 0.8975 | 0.0342 | 0.8708 | 0.9475 |
| Olist's promised days | `mean_predicted` | 23.9355 | 1.3826 | 22.7395 | 25.4501 |
| Overall median | `mae` | 6.8089 | 1.2070 | 5.0498 | 7.6618 |
| Overall median | `share_by_predicted` | 0.4451 | 0.0749 | 0.3697 | 0.5191 |
| Overall median | `mean_predicted` | 10.7311 | 0.2843 | 10.3933 | 11.0616 |
| Median by customer state | `mae` | 5.9704 | 1.2146 | 4.2587 | 6.8801 |
| Median by customer state | `share_by_predicted` | 0.4240 | 0.0832 | 0.3439 | 0.5122 |
| Median by customer state | `mean_predicted` | 10.8075 | 0.1872 | 10.5532 | 11.0045 |
| Ridge regression | `mae` | 5.7386 | 1.4070 | 3.9164 | 7.2878 |
| Ridge regression | `share_by_predicted` | 0.4532 | 0.1477 | 0.2538 | 0.6105 |
| Ridge regression | `mean_predicted` | 11.3260 | 1.7579 | 9.2814 | 13.0761 |
| Tuned model | `mae` | 5.3359 | 1.0320 | 3.8992 | 6.2013 |
| Tuned model | `share_by_predicted` | 0.4495 | 0.0860 | 0.3279 | 0.5305 |
| Tuned model | `mean_predicted` | 11.3999 | 1.0650 | 10.3577 | 12.5144 |
| Tuned 90th percentile promise | `mae` | 8.0520 | 1.6289 | 6.3458 | 9.8240 |
| Tuned 90th percentile promise | `share_by_predicted` | 0.8213 | 0.0610 | 0.7326 | 0.8688 |
| Tuned 90th percentile promise | `mean_predicted` | 19.1905 | 2.5206 | 16.4276 | 21.4790 |
| Tuned promise with margin | `share_by_predicted` | 0.8770 | 0.0757 | 0.7906 | 0.9320 |
| Tuned promise with margin | `mean_predicted` | 24.1643 | 4.0652 | 19.4702 | 26.5303 |

## 5. Category demand forecast

Primary metric: `wape`. Lower is better.

| Baseline | Metric | Mean | Std | Lowest fold | Highest fold |
|---|---|---:|---:|---:|---:|
| Mean of 4 weeks, 4 weeks ago | `wape` | 0.2863 | 0.0713 | 0.1878 | 0.3789 |
| Ridge regression | `wape` | 0.2787 | 0.0814 | 0.1517 | 0.3653 |
| Tuned model | `wape` | 0.2783 | 0.0812 | 0.1504 | 0.3639 |

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
| Tuned model | `pr_auc` | 0.6002 | 0.0289 | 0.5788 | 0.6404 |
| Tuned model | `recall_at_precision` | 0.5276 | 0.1275 | 0.4132 | 0.6737 |
| Tuned model | `revenue_recall` | 0.3204 | 0.1352 | 0.2101 | 0.5029 |
| Tuned model | `forward_precision` | 0.6498 | 0.0349 | 0.6144 | 0.6842 |
| Tuned model | `forward_recall` | 0.4153 | 0.0551 | 0.3778 | 0.4786 |

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
| Tuned model | `mae` | 3.5447 | 0.9517 | 2.8190 | 4.9396 |
| Tuned model | `mape` | 0.4035 | 0.1409 | 0.2094 | 0.5437 |
