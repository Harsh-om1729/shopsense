# Project summary

ShopSense set out to build seven models for an e-commerce business. It ended with three trained models, three simple rules, and one held model. Here's how it got there, and what went wrong along the way.

## The approach

- **Time order everywhere.** Splits, cross-validation folds, and the final holdout all respect time, because the late-delivery rate swung from 2.8% to 19.0% across months. A random split would have hidden that.
- **Features known at the time.** History features count an outcome only from when it was known. A test corrupts every holdout outcome and requires development features to stay identical, and an injected leak proved that test works.
- **Simple rules as the bar.** Every model had to beat a no-ML rule, not just a weak baseline.
- **One locked holdout.** The verdict rules were written before the holdout was opened, and nothing was tuned afterwards.

## Mistakes caught, and how

| Phase | Mistake | How it was caught | Fix |
|---|---|---|---|
| 3 | Dropping rows whose outcome came after the cutoff removed slow deliveries. The 2,438 such orders had a 20.3% late rate | Checked the late rate of the dropped rows | A 30-day embargo |
| 3 | Predicting reviews "at delivery" dropped 77% of late orders, which are often reviewed before they arrive | The low-review rate fell from 13.76% to 9.89% | Predict at delivery or the end of the promised day, whichever comes first |
| 3 | Daily orders fade out after 21 August 2018 | Looked at daily counts | End all tables at 2018-08-21 |
| 5 | Black Friday echoed through lag features for weeks | Fold-level errors | Lags see the week before the peak |
| 5 | Phase 2's forecast baseline wasn't available 28 days ahead | Reviewing the definition | Use the same weekday four weeks earlier |
| 6 | The 90th-percentile promise reached only 82% on time | Tested on later folds | A margin set on earlier data. Even then, it couldn't beat Olist |
| 7 | Late delivery passed the locked rule because its simple rule was worse than a constant guess | Diagnostics after the holdout | Held it anyway, and recorded the gap in the rules |
| 11 | A blank screen when another app answered on port 8000 | You reported it | Errors for replies that aren't JSON, an error boundary, and no browser caching |
| 12 | A test pattern blocked the site's own code, and chart labels overlapped on phones | Browser tests and screenshots | Narrower patterns and axis spacing |

## What the holdout taught

- **Development scores didn't carry over.** Deliveries sped up from 13.6 to 8.8 days on average, and Olist cut its promised dates sharply. Models that lean on recent history lagged behind.
- **Simple rules are strong baselines.** Three of seven problems are best served by a rule.
- **A model isn't the only way to fail.** The best result for delivery promises was learning that Olist's own estimate wasn't easy to beat.

## What's honestly unproven

- The packaged models were retrained on all data, so they have no fresh test.
- Queue scores in the app come from training rows.
- The app has no login, and the dataset's licence wasn't confirmed, so it runs locally only.

## If continued

1. Get newer data and follow `docs/retraining.md`.
2. Retest late delivery and the daily forecast model.
3. Compare logged predictions with real outcomes.
4. Add a login before any public deployment.
