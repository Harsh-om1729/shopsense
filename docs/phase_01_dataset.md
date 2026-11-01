# Phase 1: Dataset selection

## Decision

ShopSense uses the Olist Brazilian e-commerce dataset, identified from its file names. The 9 CSV files are in `data/raw/olist/` and aren't committed to git.

The dataset's licence isn't stated in the files. Check it on the download page before deploying publicly.

## Why this dataset fits

- It has 99,441 orders from September 2016 to October 2018.
- It supports all three defined problems: delivery dates, review scores, and purchase dates are all present.
- Orders, items, reviews, payments, customers, products, and sellers join with no missing parent rows. The exception is 13 products whose category has no English translation.

## Tables

| Table | Rows | Grain |
|---|---:|---|
| `orders` | 99,441 | One order |
| `customers` | 99,441 | One order's customer record |
| `order_items` | 112,650 | One item in an order |
| `order_payments` | 103,886 | One payment in an order |
| `order_reviews` | 99,224 | One review, and some orders have several |
| `products` | 32,951 | One product |
| `sellers` | 3,095 | One seller |
| `geolocation` | 1,000,163 | One coordinate for a zip prefix |
| `category_translation` | 71 | One category name |

## Traps

- `customer_id` is unique per order. `customer_unique_id` identifies the person.
- Joining items or payments to orders creates extra rows, so aggregate them to one row per order first.
- `product_name_lenght` and `product_description_lenght` are misspelled in the source.
- The geolocation table has 261,831 exact duplicate rows.

## Verify

```bash
uv run python -c "from src.data.load import load_all; print({k: len(v) for k, v in load_all().items()})"
```
