"""Check on the real data that development features can't see the holdout.

This corrupts everything that became known during the holdout, rebuilds the
features, and requires development rows to stay identical. It's skipped if the
processed tables haven't been built.
"""

import pandas as pd
import pytest

from src import config
from src.data.load import load_table
from src.features.build import FEATURES, build_all_features
from src.features.make_features import load_processed

HOLDOUT_START = pd.Timestamp(config.HOLDOUT_START)


def corrupt_holdout(processed, raw):
    """Return copies with every outcome known from the holdout onward changed."""
    processed = {name: table.copy() for name, table in processed.items()}
    raw = {name: table.copy() for name, table in raw.items()}

    delivery = processed["delivery"]
    known = delivery["outcome_date"] >= HOLDOUT_START
    delivery.loc[known, "is_late"] = ~delivery.loc[known, "is_late"]
    delivery.loc[known, "days_to_deliver"] += 100

    reviews = processed["reviews"]
    known = reviews["score_known_date"] >= HOLDOUT_START
    reviews.loc[known, "is_low"] = ~reviews.loc[known, "is_low"]

    daily = processed["daily_orders"]
    daily.loc[daily["date"] >= HOLDOUT_START, "orders"] *= 3

    weekly = processed["weekly_category"]
    weekly.loc[weekly["week_end"] >= HOLDOUT_START, "items"] *= 3

    orders = raw["orders"]
    later = orders.loc[orders["order_purchase_timestamp"] >= HOLDOUT_START, "order_id"]
    items = raw["order_items"]
    items.loc[items["order_id"].isin(later), "price"] *= 3
    return processed, raw


@pytest.fixture(scope="module")
def feature_pairs():
    try:
        processed = load_processed()
    except FileNotFoundError:
        pytest.skip("Processed tables haven't been built.")
    raw = {name: load_table(name) for name in ["order_items", "orders"]}

    original = build_all_features(processed, raw)
    corrupted = build_all_features(*corrupt_holdout(processed, raw))
    return original, corrupted


@pytest.mark.parametrize("name", list(FEATURES))
def test_development_features_ignore_the_holdout(feature_pairs, name):
    original, corrupted = feature_pairs
    spec = FEATURES[name]
    columns = spec["numeric"] + spec["categorical"]

    before = original[name]
    after = corrupted[name]
    before = before.loc[before["period"] == "development", columns].reset_index(drop=True)
    after = after.loc[after["period"] == "development", columns].reset_index(drop=True)

    pd.testing.assert_frame_equal(before, after)
