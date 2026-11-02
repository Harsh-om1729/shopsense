# Phase 3: Preprocessing

The code is in `src/data/preprocess.py`, and `src/data/make_dataset.py` builds, validates, and saves the tables to `data/processed/`. Those files aren't committed, so rebuild them with the command below.

This phase uses fixed rules only. Anything learned from data, such as imputation, scaling, or encoding, belongs in model pipelines, fitted on training rows only.

## Tables

| Table | Problems | One row per | Development rows | Embargo rows | Holdout rows | Development target rate |
|---|---|---|---:|---:|---:|---|
| `delivery` | 1, 4 | Delivered order | 71,001 | 6,599 | 17,922 | 7.51% late |
| `reviews` | 2 | Reviewed delivered order | 70,275 | 6,495 | 17,830 | 13.76% low |
| `daily_orders` | 3 | Day | 512 | 0 | 82 | Not applicable |
| `weekly_category` | 5 | Week and category | 720 | 0 | 120 | Not applicable |
| `seller_snapshots` | 6 | Seller at a month start | 13,348 | 1,487 | 1,555 | 27.93% inactive |
| `freight` | 7 | Product in an order | 82,468 | 0 | 18,899 | Not applicable |

Holdout target rates are deliberately not printed.

## Corrections to Phase 2

**The data ends earlier than it appears to.** Daily orders fall from 243 on 21 August 2018 to 1 on 31 August. That looks like an extraction cut-off, though the cause can't be confirmed. All tables stop at 2018-08-21.

**The boundary rule became an embargo.** Phase 2 said to drop development rows whose outcome came after `HOLDOUT_START`. There were 2,438 such orders, and 20.3% were late, against about 7.5% overall. Dropping only those would remove slow deliveries from training. Instead, every order from the last 30 days before the holdout is excluded. The development late rate stayed steady at 7.51%.

**Problem 2's prediction moment moved.** The first version predicted at delivery and dropped reviews written before delivery. Those were 5.91% of rows, but 95.1% of them were late orders, and the low rate fell from 13.76% to 9.89%. The survey usually goes out a day after delivery or the promised date, whichever comes first, so late orders are often reviewed before they arrive. The prediction moment is now the delivery or the end of the promised day, whichever comes first. If the order is overdue by then, `is_overdue` is true and the final delivery date is hidden.

## Cleaning rules

| Issue | Rule |
|---|---|
| Items and payments have several rows per order | Aggregate to one row per order |
| Orders with several sellers | Use the seller of the most expensive item |
| Several reviews for one order | Keep the most recently answered |
| Reviews created before the prediction moment | Drop |
| Carrier date before purchase or after customer delivery | Clear the date |
| Zero product weight | Treat as missing |
| Zero instalments | Treat as 1 |
| Missing or untranslated category | Use `unknown`, or the Portuguese name |
| Coordinates outside Brazil | Drop before taking each zip prefix's median |
| Repeated product in an order | One row with a `quantity`, since freight is identical |
| `product_name_lenght`, `product_description_lenght` | Rename to the correct spelling |

## Deliberately kept or left out

- **Long deliveries:** 63 development orders took over 100 days. Nothing shows they're errors, so they stay.
- **Zero freight:** kept, because it may be genuine free shipping.
- **City names:** unused, because seller cities are messy. State and coordinates are used instead.
- **`shipping_limit_date`:** left out, because the data doesn't show when it becomes known.
- **Daily orders:** counts every order placed, including cancelled ones, because they still show demand.
- **Seller sales:** ignores cancelled and unavailable orders, because those aren't completed sales.

## Rules for later phases

- Train only on rows with `period == "development"`.
- Never use `TARGET_COLUMNS` from `src/data/preprocess.py` as features.
- About 0.3% of rows have no coordinates, and these are left missing for model pipelines to handle.
- Validation folds need a gap too, or the same leakage returns inside cross-validation.

## Verify

```bash
uv run python -m src.data.make_dataset
uv run pytest
uv run ruff check .
uv run ruff format --check .
```
