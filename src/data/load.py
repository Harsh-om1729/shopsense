"""Load the raw Olist CSVs with parsed dates."""

from pathlib import Path

import pandas as pd

from src import config

# Table name -> (CSV file name, columns to parse as datetimes).
TABLES = {
    "customers": ("olist_customers_dataset.csv", []),
    "geolocation": ("olist_geolocation_dataset.csv", []),
    "order_items": ("olist_order_items_dataset.csv", ["shipping_limit_date"]),
    "order_payments": ("olist_order_payments_dataset.csv", []),
    "order_reviews": (
        "olist_order_reviews_dataset.csv",
        ["review_creation_date", "review_answer_timestamp"],
    ),
    "orders": (
        "olist_orders_dataset.csv",
        [
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
    ),
    "products": ("olist_products_dataset.csv", []),
    "sellers": ("olist_sellers_dataset.csv", []),
    "category_translation": ("product_category_name_translation.csv", []),
}


def load_table(name: str, data_dir: Path = config.OLIST_DIR) -> pd.DataFrame:
    """Return one raw table, raising a clear error if it can't be found."""
    if name not in TABLES:
        raise ValueError(f"Unknown table {name!r}. Expected one of: {sorted(TABLES)}")

    file_name, date_columns = TABLES[name]
    path = Path(data_dir) / file_name
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}. Put the Olist CSVs in {data_dir}.")

    return pd.read_csv(path, parse_dates=date_columns, low_memory=False)


def load_all(data_dir: Path = config.OLIST_DIR) -> dict[str, pd.DataFrame]:
    """Return every raw table, keyed by table name."""
    return {name: load_table(name, data_dir) for name in TABLES}
