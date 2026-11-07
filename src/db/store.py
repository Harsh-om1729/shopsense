"""Read stored features and record predictions."""

import json
import logging
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import SQLAlchemyError

from src import config
from src.db.schema import (
    DATA_TABLES,
    make_engine,
    predictions,
    review_features,
    seller_snapshots,
    zip_coordinates,
)
from src.features.build import FEATURES
from src.models.predictor import ModelNotAvailableError

logger = logging.getLogger(__name__)

NOT_LOADED = "The database isn't loaded. Run src.db.load first."


class Store:
    """Give the API its data, hiding how it's stored."""

    def __init__(self, engine: Engine | None = None, log_predictions: bool | None = None):
        self.engine = engine or make_engine()
        self.log_predictions = (
            config.LOG_PREDICTIONS if log_predictions is None else log_predictions
        )

    def ready(self) -> bool:
        """Return whether every data table has rows."""
        try:
            with self.engine.connect() as connection:
                return all(
                    connection.scalar(select(table.c[table.primary_key.columns.keys()[0]]).limit(1))
                    is not None
                    for table in DATA_TABLES
                )
        except SQLAlchemyError:
            return False

    def read_rows(self, query, table: str) -> pd.DataFrame:
        """Return query results with missing categories as NaN, as in training."""
        with self.engine.connect() as connection:
            rows = pd.read_sql(query, connection)
        for column in FEATURES[table]["categorical"]:
            values = rows[column].astype(object)
            rows[column] = values.where(values.notna(), np.nan)
        return rows

    def recent_reviews(self, days: int) -> tuple[pd.Timestamp, pd.Timestamp, pd.DataFrame]:
        """Return the window's start and end, and the reviewable orders inside it."""
        with self.engine.connect() as connection:
            end = connection.scalar(select(func.max(review_features.c.prediction_moment)))
        if end is None:
            raise ModelNotAvailableError(NOT_LOADED)

        start = end - timedelta(days=days)
        query = (
            select(review_features)
            .where(review_features.c.prediction_moment > start)
            .order_by(review_features.c.prediction_moment, review_features.c.order_id)
        )
        return pd.Timestamp(start), pd.Timestamp(end), self.read_rows(query, "reviews")

    def latest_seller_snapshot(self) -> tuple[pd.Timestamp, pd.DataFrame]:
        """Return the latest snapshot's date and rows."""
        with self.engine.connect() as connection:
            snapshot = connection.scalar(select(func.max(seller_snapshots.c.snapshot_date)))
        if snapshot is None:
            raise ModelNotAvailableError(NOT_LOADED)

        query = (
            select(seller_snapshots)
            .where(seller_snapshots.c.snapshot_date == snapshot)
            .order_by(seller_snapshots.c.seller_id)
        )
        return pd.Timestamp(snapshot), self.read_rows(query, "seller_snapshots")

    def coordinates_for_zip(self, prefix: int) -> tuple[float, float] | None:
        """Return a zip prefix's coordinates, or None if the table doesn't have it."""
        with self.engine.connect() as connection:
            row = connection.execute(
                select(zip_coordinates.c.lat, zip_coordinates.c.lng).where(
                    zip_coordinates.c.zip_prefix == prefix
                )
            ).first()
            if (
                row is None
                and connection.scalar(select(zip_coordinates.c.zip_prefix).limit(1)) is None
            ):
                raise ModelNotAvailableError(NOT_LOADED)
        return None if row is None else (row.lat, row.lng)

    def record(self, model_name: str, version: str, inputs, outputs) -> None:
        """Log a served prediction. A logging failure must never break the prediction."""
        if not self.log_predictions:
            return
        try:
            row = {
                "created_at": datetime.now(UTC).replace(tzinfo=None),
                "model_name": model_name,
                "model_version": version,
                "inputs": json.dumps(inputs, default=str),
                "outputs": json.dumps(outputs, default=str),
            }
            with self.engine.begin() as connection:
                connection.execute(predictions.insert(), row)
        except (SQLAlchemyError, TypeError, ValueError) as error:
            logger.warning("Couldn't log a %s prediction: %s", model_name, error)
