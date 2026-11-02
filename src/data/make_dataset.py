"""Build and save the processed tables.

Run with: uv run python -m src.data.make_dataset
"""

import pandas as pd

from src import config
from src.data.load import load_all
from src.data.preprocess import POST_PURCHASE_COLUMNS, TARGET_COLUMNS, build_all

# Each table's unique row key.
TABLE_KEYS = {
    "delivery": ["order_id"],
    "reviews": ["order_id"],
    "daily_orders": ["date"],
    "weekly_category": ["week_end", "category"],
    "seller_snapshots": ["snapshot_date", "seller_id"],
    "freight": ["order_id", "product_id", "seller_id"],
}
ALLOWED_PERIODS = {"development", "embargo", "holdout"}
TARGET_RATES = {
    "delivery": "is_late",
    "reviews": "is_low",
    "seller_snapshots": "is_inactive",
}


def validate(processed: dict[str, pd.DataFrame]) -> None:
    """Raise ValueError if a table breaks a rule the later phases rely on."""
    for name, keys in TABLE_KEYS.items():
        table = processed[name]
        if table.empty:
            raise ValueError(f"{name} is empty.")
        if table.duplicated(keys).any():
            raise ValueError(f"{name} has duplicate rows for {keys}.")
        unexpected = set(table["period"]) - ALLOWED_PERIODS
        if unexpected:
            raise ValueError(f"{name} has unexpected periods: {unexpected}.")

    leaked = set(processed["delivery"].columns) & set(POST_PURCHASE_COLUMNS)
    if leaked:
        raise ValueError(f"delivery contains post-purchase columns: {leaked}.")

    reviews = processed["reviews"]
    if "order_delivered_customer_date" in reviews.columns:
        raise ValueError("reviews must not contain the unmasked delivery date.")
    if (reviews["delivered_date"] > reviews["prediction_moment"]).any():
        raise ValueError("reviews reveals a delivery after the prediction moment.")

    for name, columns in TARGET_COLUMNS.items():
        missing = set(columns) - set(processed[name].columns)
        if missing:
            raise ValueError(f"{name} is missing target columns: {missing}.")

    daily = processed["daily_orders"]["date"]
    if len(daily) != (daily.max() - daily.min()).days + 1:
        raise ValueError("daily_orders has missing days.")


def summarise(processed: dict[str, pd.DataFrame]) -> None:
    """Print row counts, and target rates for development rows only."""
    for name, table in processed.items():
        counts = table["period"].value_counts().to_dict()
        print(f"{name}: {len(table):,} rows, {counts}")
        target = TARGET_RATES.get(name)
        if target:
            rate = table.loc[table["period"] == "development", target].mean()
            print(f"  development {target} rate: {rate:.4f}")


def main() -> None:
    processed = build_all(load_all())
    validate(processed)

    config.DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for name, table in processed.items():
        table.to_parquet(config.DATA_PROCESSED_DIR / f"{name}.parquet", index=False)

    summarise(processed)
    print(f"Saved {len(processed)} tables to {config.DATA_PROCESSED_DIR}")


if __name__ == "__main__":
    main()
