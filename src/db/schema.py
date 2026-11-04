"""Database tables.

Feature tables hold IDs and allowed features only. Targets are left out on
purpose, because serving code can't leak an answer the database doesn't contain.
"""

from pathlib import Path

from sqlalchemy import (
    Column,
    DateTime,
    Engine,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    event,
)

from src import config
from src.features.build import FEATURES

metadata = MetaData()


def feature_columns(table: str, skip: tuple[str, ...] = ()) -> list[Column]:
    """Return a column for each allowed feature in a table."""
    spec = FEATURES[table]
    numeric = [Column(name, Float) for name in spec["numeric"] if name not in skip]
    categorical = [Column(name, String) for name in spec["categorical"] if name not in skip]
    return numeric + categorical


orders = Table(
    "orders",
    metadata,
    Column("order_id", String, primary_key=True),
    Column("order_status", String, nullable=False),
    Column("order_purchase_timestamp", DateTime, nullable=False, index=True),
    Column("order_estimated_delivery_date", DateTime),
    Column("customer_state", String),
)

zip_coordinates = Table(
    "zip_coordinates",
    metadata,
    Column("zip_prefix", Integer, primary_key=True),
    Column("lat", Float, nullable=False),
    Column("lng", Float, nullable=False),
)

review_features = Table(
    "review_features",
    metadata,
    Column("order_id", String, ForeignKey("orders.order_id"), primary_key=True),
    Column("prediction_moment", DateTime, nullable=False, index=True),
    Column("seller_id", String, nullable=False),
    *feature_columns("reviews"),
)

seller_snapshots = Table(
    "seller_snapshots",
    metadata,
    Column("snapshot_date", DateTime, primary_key=True),
    Column("seller_id", String, primary_key=True),
    *feature_columns("seller_snapshots"),
)

# One row per served request. Reloading the data never touches this table.
predictions = Table(
    "predictions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("created_at", DateTime, nullable=False, index=True),
    Column("model_name", String, nullable=False, index=True),
    Column("model_version", String, nullable=False),
    Column("inputs", Text, nullable=False),
    Column("outputs", Text, nullable=False),
)

# Parents come before children, because of the foreign key.
DATA_TABLES = [orders, zip_coordinates, review_features, seller_snapshots]


def make_engine(path: Path = config.DATABASE_PATH) -> Engine:
    """Return a SQLite engine with foreign keys and concurrent reads turned on."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def configure(connection, _):
        cursor = connection.cursor()
        # SQLite ignores foreign keys unless asked, on every connection.
        cursor.execute("PRAGMA foreign_keys = ON")
        # WAL stops prediction logging from blocking reads.
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.close()

    metadata.create_all(engine)
    return engine
