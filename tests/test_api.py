"""API tests. Fake services cover errors, and real packages cover behaviour."""

import math

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.services import LATE_DELIVERY, Services
from src import config
from src.features.build import FEATURES
from src.models.predictor import InvalidInputError, ModelNotAvailableError, load_predictor

packaged = pytest.mark.skipif(
    not (config.MODELS_DIR / "freight_cost" / "metadata.json").is_file()
    or not config.DATABASE_PATH.is_file(),
    reason="Packages or the database haven't been built.",
)

FREIGHT_BODY = {
    "customer_state": "SP",
    "seller_state": "RJ",
    "customer_lat": -23.55,
    "customer_lng": -46.63,
    "seller_lat": -22.91,
    "seller_lng": -43.17,
    "product_weight_g": 500,
    "product_length_cm": 20,
    "product_height_cm": 10,
    "product_width_cm": 15,
    "price": 80,
    "category": "toys",
}


class FakeServices:
    """Stand-in that raises a chosen error, so no real model is needed."""

    predictors = {"freight_cost": object()}
    unavailable = {}

    def __init__(self, error=None, database_ready=True):
        self.error = error
        self.is_ready = database_ready

    def database_ready(self):
        return self.is_ready

    def daily_forecast(self, start, days):
        raise self.error

    def delivery_days(self, customer_state):
        return {"customer_state": customer_state, "predicted_days": 7.5, "note": "note"}


def client_with(services):
    return TestClient(create_app(services))


@pytest.fixture(scope="module")
def client():
    services = Services()
    # Tests must not fill the real prediction log.
    services.store.record = lambda *arguments: None
    with TestClient(create_app(services)) as real_client:
        yield real_client


def test_invalid_input_becomes_a_422_with_its_reason():
    with client_with(FakeServices(InvalidInputError("too far ahead"))) as fake:
        response = fake.get("/forecast/orders", params={"start": "2018-09-01"})

    assert response.status_code == 422
    assert response.json() == {"error": "invalid_input", "detail": "too far ahead"}


def test_unavailable_model_becomes_a_503_with_its_reason():
    with client_with(FakeServices(ModelNotAvailableError("not built"))) as fake:
        response = fake.get("/forecast/orders", params={"start": "2018-09-01"})

    assert response.status_code == 503
    assert response.json()["detail"] == "not built"


def test_health_is_degraded_when_an_active_package_is_missing():
    services = FakeServices()
    services.unavailable = {"freight_cost": "missing"}
    with client_with(services) as fake:
        assert fake.get("/health").json()["status"] == "degraded"


def test_health_is_degraded_without_a_loaded_database():
    with client_with(FakeServices(database_ready=False)) as fake:
        body = fake.get("/health").json()

    assert body["status"] == "degraded"
    assert body["database_ready"] is False


def test_freight_refuses_a_zip_with_coordinates():
    with client_with(FakeServices()) as fake:
        response = fake.post("/predict/freight", json=FREIGHT_BODY | {"customer_zip_prefix": 1037})

    assert response.status_code == 422
    assert "not both" in response.text


def test_health_stays_ok_when_only_the_held_model_is_unavailable():
    services = FakeServices()
    services.unavailable = {LATE_DELIVERY: "held"}
    with client_with(services) as fake:
        assert fake.get("/health").json()["status"] == "ok"


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"customer_state": "XX"}, "unknown state"),
        ({"customer_lat": 40.0}, "outside Brazil"),
        ({"price": 0}, "free item"),
        ({"quantity": 0}, "no items"),
        ({"product_weight_g": -5}, "negative weight"),
        ({"weight": 500}, "misspelled field"),
    ],
)
def test_freight_rejects_bad_requests_before_any_model_runs(change, reason):
    with client_with(FakeServices()) as fake:
        assert fake.post("/predict/freight", json=FREIGHT_BODY | change).status_code == 422, reason


def test_forecast_days_are_limited():
    with client_with(FakeServices()) as fake:
        response = fake.get("/forecast/orders", params={"start": "2018-09-01", "days": 29})
    assert response.status_code == 422


def test_delivery_rejects_an_unknown_state():
    with client_with(FakeServices()) as fake:
        assert fake.post("/predict/delivery-time", json={"customer_state": "ZZ"}).status_code == 422


@packaged
def test_health_reports_six_packages(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert len(body["loaded"]) == 6
    assert list(body["unavailable"]) == [LATE_DELIVERY]


@packaged
def test_models_lists_all_seven_with_verdicts(client):
    body = client.get("/models").json()
    assert len(body) == 7
    held = next(item for item in body if item["name"] == LATE_DELIVERY)
    assert held["status"] == "held"


@packaged
def test_late_delivery_never_predicts(client):
    response = client.post("/predict/late-delivery")
    assert response.status_code == 503
    assert "held" in response.json()["detail"]


@packaged
def test_freight_from_the_api_matches_the_training_features(client):
    """Send one stored row's raw fields, which must give the same answer as its features."""
    table = pd.read_parquet(config.FEATURES_DIR / "freight.parquet")
    row = table.dropna(subset=FEATURES["freight"]["numeric"]).iloc[1000]
    fields = list(FREIGHT_BODY) + ["quantity"]
    body = {name: row[name] for name in fields}
    body["quantity"] = int(body["quantity"])

    response = client.post("/predict/freight", json=body)
    expected = load_predictor("freight_cost").predict(row.to_frame().T)

    assert response.status_code == 200
    assert response.json()["predicted_freight"] == pytest.approx(
        float(expected["predicted_freight"].iloc[0])
    )


@packaged
def test_freight_accepts_a_missing_route(client):
    body = {"customer_state": "SP", "seller_state": "SP", "price": 50}
    response = client.post("/predict/freight", json=body)

    assert response.status_code == 200
    predicted = response.json()["predicted_freight"]
    assert math.isfinite(predicted)
    assert predicted >= 0
    assert response.json()["distance_known"] is False


@packaged
def test_freight_from_zips_matches_the_same_coordinates(client):
    coordinates = client.app.state.services.store.coordinates_for_zip
    customer_lat, customer_lng = coordinates(1037)
    seller_lat, seller_lng = coordinates(20040)
    common = {"customer_state": "SP", "seller_state": "RJ", "price": 80}

    from_zips = client.post(
        "/predict/freight",
        json=common | {"customer_zip_prefix": 1037, "seller_zip_prefix": 20040},
    ).json()
    from_coordinates = client.post(
        "/predict/freight",
        json=common
        | {
            "customer_lat": customer_lat,
            "customer_lng": customer_lng,
            "seller_lat": seller_lat,
            "seller_lng": seller_lng,
        },
    ).json()

    assert from_zips == from_coordinates
    assert from_zips["distance_known"] is True


@packaged
def test_freight_with_an_unknown_zip_says_distance_is_unknown(client):
    body = {"customer_state": "SP", "seller_state": "RJ", "price": 80, "customer_zip_prefix": 99999}
    response = client.post("/predict/freight", json=body)

    assert response.status_code == 200
    assert response.json()["distance_known"] is False


@packaged
def test_delivery_time_comes_from_the_rule(client):
    body = client.post("/predict/delivery-time", json={"customer_state": "SP"}).json()
    assert body["predicted_days"] > 0
    assert "Olist" in body["note"]


@packaged
def test_daily_forecast_returns_each_day(client):
    response = client.get("/forecast/orders", params={"start": "2018-08-22", "days": 7})
    assert [item["date"] for item in response.json()][:2] == ["2018-08-22", "2018-08-23"]
    assert len(response.json()) == 7


@packaged
def test_daily_forecast_past_the_limit_is_refused(client):
    response = client.get("/forecast/orders", params={"start": "2018-09-18", "days": 2})
    assert response.status_code == 422
    assert "out of range" in response.json()["detail"]


@packaged
def test_category_forecast_rejects_an_unknown_category(client):
    params = {"week_end": "2018-09-09", "category": "cars"}
    assert client.get("/forecast/category", params=params).status_code == 422


@packaged
def test_review_queue_is_ranked_and_labelled(client):
    body = client.get("/reviews/queue", params={"limit": 5}).json()
    scores = [order["risk_score"] for order in body["orders"]]

    assert body["scored_on_training_data"] is True
    assert [order["rank"] for order in body["orders"]] == [1, 2, 3, 4, 5]
    assert scores == sorted(scores, reverse=True)
    assert "review_score" not in body["orders"][0]


@packaged
def test_sellers_at_risk_shows_alerts_with_revenue(client):
    body = client.get("/sellers/at-risk", params={"limit": 5}).json()

    assert body["scored_on_training_data"] is True
    assert all(seller["is_alert"] for seller in body["sellers"])
    assert "revenue_90d" in body["sellers"][0]


@packaged
def test_list_limits_are_enforced(client):
    assert client.get("/reviews/queue", params={"limit": 101}).status_code == 422
