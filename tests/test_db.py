"""Database tests. Most use a small temporary database."""

import json

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import func, inspect, select, text
from sqlalchemy.exc import IntegrityError

from api.services import LOW_REVIEW, SELLER, Services
from src import config
from src.data.preprocess import TARGET_COLUMNS
from src.db.load import load_database, read_features
from src.db.schema import make_engine, orders, predictions, review_features
from src.db.store import Store
from src.features.build import FEATURES
from src.models.predictor import ModelNotAvailableError, load_predictor


def feature_values(table):
    spec = FEATURES[table]
    return {name: 1.0 for name in spec["numeric"]} | {name: "x" for name in spec["categorical"]}


def sample_frames(review_ids=("a", "b")):
    return {
        "orders": pd.DataFrame(
            {
                "order_id": ["a", "b"],
                "order_status": ["delivered"] * 2,
                "order_purchase_timestamp": pd.to_datetime(["2018-08-01", "2018-08-02"]),
                "order_estimated_delivery_date": pd.to_datetime(["2018-08-20", None]),
                "customer_state": ["SP", None],
            }
        ),
        "zip_coordinates": pd.DataFrame({"zip_prefix": [1037], "lat": [-23.5], "lng": [-46.6]}),
        "review_features": pd.DataFrame(
            [
                {
                    "order_id": order_id,
                    "prediction_moment": pd.Timestamp("2018-08-10") + pd.Timedelta(days=step * 9),
                    "seller_id": "s",
                    **feature_values("reviews"),
                }
                for step, order_id in enumerate(review_ids)
            ]
        ),
        "seller_snapshots": pd.DataFrame(
            [
                {
                    "snapshot_date": pd.Timestamp(date),
                    "seller_id": "s",
                    **feature_values("seller_snapshots"),
                }
                for date in ("2018-05-01", "2018-06-01")
            ]
        ),
    }


@pytest.fixture
def engine(tmp_path):
    return make_engine(tmp_path / "test.db")


@pytest.fixture
def store(engine):
    load_database(engine, sample_frames())
    return Store(engine)


def count(engine, table):
    with engine.connect() as connection:
        return connection.scalar(select(func.count()).select_from(table))


@pytest.mark.parametrize(
    ("table", "targets"),
    [
        ("review_features", TARGET_COLUMNS["reviews"]),
        ("seller_snapshots", TARGET_COLUMNS["seller_snapshots"]),
    ],
)
def test_feature_tables_hold_no_targets(engine, table, targets):
    columns = {column["name"] for column in inspect(engine).get_columns(table)}
    assert not columns & set(targets)


def test_load_replaces_data_when_repeated(engine):
    load_database(engine, sample_frames())
    load_database(engine, sample_frames())
    assert count(engine, orders) == 2


def test_load_keeps_the_prediction_log(engine):
    Store(engine).record("freight_cost", "1.0.0", {}, {})
    load_database(engine, sample_frames())
    assert count(engine, predictions) == 1


def test_failed_load_leaves_the_old_data(engine):
    load_database(engine, sample_frames())
    broken = sample_frames(review_ids=("a", "not_an_order"))

    with pytest.raises(IntegrityError):
        load_database(engine, broken)

    assert count(engine, orders) == 2
    assert count(engine, review_features) == 2


def test_load_reports_missing_columns(engine):
    frames = sample_frames()
    frames["orders"] = frames["orders"].drop(columns="order_status")
    with pytest.raises(ValueError, match="missing columns"):
        load_database(engine, frames)


def test_foreign_keys_are_enforced(engine):
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(
                review_features.insert(),
                {
                    "order_id": "ghost",
                    "prediction_moment": pd.Timestamp("2018-08-10"),
                    "seller_id": "s",
                },
            )


def test_engine_uses_wal(engine):
    with engine.connect() as connection:
        assert connection.scalar(text("PRAGMA journal_mode")) == "wal"


def test_store_is_ready_only_after_loading(engine):
    store = Store(engine)
    assert store.ready() is False
    load_database(engine, sample_frames())
    assert store.ready() is True


def test_recent_reviews_use_a_window_from_the_latest_moment(store):
    start, end, rows = store.recent_reviews(7)

    assert end == pd.Timestamp("2018-08-19")
    assert start == pd.Timestamp("2018-08-12")
    assert rows["order_id"].tolist() == ["b"]


def test_empty_database_gives_a_clear_error(engine):
    with pytest.raises(ModelNotAvailableError, match="isn't loaded"):
        Store(engine).recent_reviews(7)
    with pytest.raises(ModelNotAvailableError, match="isn't loaded"):
        Store(engine).latest_seller_snapshot()
    with pytest.raises(ModelNotAvailableError, match="isn't loaded"):
        Store(engine).coordinates_for_zip(1037)


def test_latest_snapshot_returns_only_that_date(store):
    snapshot, rows = store.latest_seller_snapshot()

    assert snapshot == pd.Timestamp("2018-06-01")
    assert len(rows) == 1


def test_missing_categories_come_back_as_nan(engine):
    frames = sample_frames()
    frames["review_features"]["main_category"] = None
    load_database(engine, frames)

    _, _, rows = Store(engine).recent_reviews(30)

    assert all(value is np.nan or pd.isna(value) for value in rows["main_category"])


def test_zip_lookup(store):
    assert store.coordinates_for_zip(1037) == (-23.5, -46.6)
    assert store.coordinates_for_zip(99999) is None


def test_record_saves_inputs_and_outputs(engine):
    Store(engine).record("freight_cost", "1.0.0", {"day": pd.Timestamp("2018-01-01")}, {"x": 1.5})

    with engine.connect() as connection:
        row = connection.execute(select(predictions)).one()

    assert row.model_name == "freight_cost"
    assert row.model_version == "1.0.0"
    assert "2018-01-01" in json.loads(row.inputs)["day"]
    assert json.loads(row.outputs) == {"x": 1.5}


def test_record_failure_only_warns(engine, caplog):
    store = Store(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE predictions"))

    store.record("freight_cost", "1.0.0", {}, {})

    assert "Couldn't log" in caplog.text


real_data = pytest.mark.skipif(
    not config.DATABASE_PATH.is_file(), reason="The database hasn't been built."
)


@pytest.fixture(scope="module")
def real_store():
    store = Store()
    # Tests must not fill the real prediction log.
    store.record = lambda *arguments: None
    return store


@real_data
def test_real_database_matches_the_feature_tables(real_store):
    with real_store.engine.connect() as connection:
        reviews = connection.scalar(select(func.count()).select_from(review_features))
    assert reviews == len(read_features("reviews"))


@real_data
def test_review_scores_match_the_feature_table(real_store):
    start, _, rows = real_store.recent_reviews(7)
    table = read_features("reviews")
    source = table[table["prediction_moment"] > start].set_index("order_id")
    predictor = load_predictor(LOW_REVIEW)

    from_database = predictor.predict(rows)["risk_score"].to_numpy()
    from_file = predictor.predict(source.loc[rows["order_id"]])["risk_score"].to_numpy()

    assert np.array_equal(from_database, from_file)


@real_data
def test_seller_scores_match_the_feature_table(real_store):
    snapshot, rows = real_store.latest_seller_snapshot()
    table = read_features("seller_snapshots")
    source = table[table["snapshot_date"] == snapshot].set_index("seller_id")
    predictor = load_predictor(SELLER)

    from_database = predictor.predict(rows)["risk_score"].to_numpy()
    from_file = predictor.predict(source.loc[rows["seller_id"]])["risk_score"].to_numpy()

    assert np.array_equal(from_database, from_file)


@real_data
def test_services_log_each_request_with_its_version(tmp_path):
    engine = make_engine(tmp_path / "log.db")
    services = Services(store=Store(engine))

    services.delivery_days("SP")

    with engine.connect() as connection:
        row = connection.execute(select(predictions)).one()
    assert row.model_name == "delivery_time_rule"
    assert row.model_version == "1.0.0"


def test_record_can_be_turned_off(engine):
    Store(engine, log_predictions=False).record("freight_cost", "1.0.0", {}, {})
    assert count(engine, predictions) == 0
