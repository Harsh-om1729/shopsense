"""Load the database from the feature tables.

Run after make_features with: uv run python -m src.db.load
"""

import pandas as pd
from sqlalchemy import Engine, func, select

from src import config
from src.data.load import load_table
from src.data.preprocess import clean_orders, clean_zip_coordinates
from src.db.schema import DATA_TABLES, make_engine

CHUNK_ROWS = 5000


def read_features(table: str) -> pd.DataFrame:
    """Read a feature table, with a clear error if it hasn't been built."""
    path = config.FEATURES_DIR / f"{table}.parquet"
    if not path.is_file():
        raise FileNotFoundError(f"Missing {path}. Run src.features.make_features first.")
    return pd.read_parquet(path)


def build_frames() -> dict[str, pd.DataFrame]:
    """Return the rows for each database table."""
    customers = load_table("customers")[["customer_id", "customer_state"]]
    orders = clean_orders(load_table("orders")).merge(customers, on="customer_id", how="left")
    coordinates = clean_zip_coordinates(load_table("geolocation"))
    coordinates = coordinates.rename_axis("zip_prefix").reset_index()

    return {
        "orders": orders,
        "zip_coordinates": coordinates,
        "review_features": read_features("reviews"),
        "seller_snapshots": read_features("seller_snapshots"),
    }


def to_records(frame: pd.DataFrame, table) -> list[dict]:
    """Return a table's columns as records, with missing values as None."""
    columns = [column.name for column in table.columns]
    missing = set(columns) - set(frame.columns)
    if missing:
        raise ValueError(f"{table.name} is missing columns: {sorted(missing)}.")
    selected = frame[columns].astype(object)
    return selected.where(selected.notna(), None).to_dict("records")


def load_database(engine: Engine, frames: dict[str, pd.DataFrame]) -> dict[str, int]:
    """Replace the data tables in one transaction and return their row counts.

    A failure rolls everything back, so the old data stays usable.
    """
    counts = {}
    with engine.begin() as connection:
        for table in reversed(DATA_TABLES):
            connection.execute(table.delete())

        for table in DATA_TABLES:
            records = to_records(frames[table.name], table)
            for start in range(0, len(records), CHUNK_ROWS):
                connection.execute(table.insert(), records[start : start + CHUNK_ROWS])

            count = connection.scalar(select(func.count()).select_from(table))
            if count != len(frames[table.name]):
                raise ValueError(f"{table.name} loaded {count} of {len(frames[table.name])} rows.")
            counts[table.name] = count
    return counts


def main() -> None:
    counts = load_database(make_engine(), build_frames())
    for table, count in counts.items():
        print(f"{table}: {count:,} rows")
    print(f"Saved the database to {config.DATABASE_PATH}")


if __name__ == "__main__":
    main()
