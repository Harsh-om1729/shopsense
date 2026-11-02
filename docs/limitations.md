# Limitations

- **History:** about 20 usable months, with one November peak, so yearly seasonality can't be learned.
- **Changing conditions:** late rates vary sharply by month, and the data doesn't explain why. Models may not hold up in new periods.
- **Peak season:** late-delivery models are weakest in November and December 2017, at 1.5 times a constant score. One peak gives little to learn from.
- **Late alerts:** precision swung from 14.8% to 40.6% across windows, so they aren't dependable yet.
- **Delivery promises:** the model doesn't support shorter promises at Olist's reliability.
- **Probabilities:** scores rank orders well but aren't calibrated, because conditions change over time.
- **Unexplained periods:** orders dip in May 2018, and the data doesn't say why.
- **Customers:** 97.0% have one order in the development period, so customer history adds little.
- **Delivery detail:** each order has one delivery date, so split shipments can't be seen.
- **End of data:** orders fade out after 21 August 2018 and the cause is unknown, so later orders are excluded.
- **Reviews:** late orders are often reviewed before they arrive, so a review may not reflect the final delivery.
- **Sellers:** there are no account records, so inactivity can't confirm a seller has left. The holdout has only one seller snapshot, so that test is thin.
- **Freight:** the data doesn't show how freight is calculated.
- **Licence:** not stated in the data files. Check it before deploying publicly.
