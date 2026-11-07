"""The real API when parts are missing. Each case must fail clearly, never crash."""

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.services import Services
from src.db.schema import make_engine
from src.db.store import Store
from tests.test_api import FREIGHT_BODY, packaged


def client_for(services):
    return TestClient(create_app(services))


@pytest.fixture
def empty_store(tmp_path):
    return Store(make_engine(tmp_path / "empty.db"), log_predictions=False)


@packaged
def test_empty_database_degrades_health_and_explains_queues(empty_store):
    with client_for(Services(store=empty_store)) as client:
        health = client.get("/health").json()
        queue = client.get("/reviews/queue")
        sellers = client.get("/sellers/at-risk")
        zip_freight = client.post(
            "/predict/freight",
            json={
                "customer_state": "SP",
                "seller_state": "RJ",
                "price": 80,
                "customer_zip_prefix": 1037,
            },
        )
        delivery = client.post("/predict/delivery-time", json={"customer_state": "SP"})

    assert health["status"] == "degraded"
    assert health["database_ready"] is False
    for response in (queue, sellers, zip_freight):
        assert response.status_code == 503
        assert "src.db.load" in response.json()["detail"]
    # Rules that don't need the database keep working.
    assert delivery.status_code == 200


def test_missing_packages_explain_themselves(tmp_path, empty_store):
    services = Services(models_dir=tmp_path / "no_models", store=empty_store)
    with client_for(services) as client:
        health = client.get("/health").json()
        freight = client.post("/predict/freight", json=FREIGHT_BODY)
        forecast = client.get("/forecast/options")
        models = client.get("/models")

    assert health["status"] == "degraded"
    assert health["loaded"] == []
    assert freight.status_code == 503
    assert "src.models.package" in freight.json()["detail"]
    assert forecast.status_code == 503
    assert models.json() == []


@packaged
def test_unexpected_errors_return_500_without_internal_details(empty_store):
    services = Services(store=empty_store)

    def broken(*arguments):
        raise RuntimeError("secret internal detail")

    services.delivery_days = broken
    with TestClient(create_app(services), raise_server_exceptions=False) as client:
        response = client.post("/predict/delivery-time", json={"customer_state": "SP"})

    assert response.status_code == 500
    assert "secret internal detail" not in response.text
