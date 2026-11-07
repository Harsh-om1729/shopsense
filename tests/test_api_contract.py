"""Check the parts of the API that the frontend relies on."""

import pytest
from fastapi.testclient import TestClient

from api.export_openapi import OPENAPI_PATH, schema_text
from api.main import create_app
from tests.test_api import FakeServices, packaged

DEV_ORIGIN = "http://localhost:5173"


def test_frontend_schema_matches_the_api():
    """Fails when the API changes without regenerating the frontend's types."""
    assert OPENAPI_PATH.read_text() == schema_text(), (
        "Run: uv run python -m api.export_openapi, then npm run generate:api in frontend/"
    )


def preflight(client, origin):
    return client.options(
        "/health",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )


def test_cors_allows_a_listed_origin():
    with TestClient(create_app(FakeServices(), cors_origins=[DEV_ORIGIN])) as client:
        response = preflight(client, DEV_ORIGIN)
    assert response.headers["access-control-allow-origin"] == DEV_ORIGIN


def test_cors_ignores_an_unlisted_origin():
    with TestClient(create_app(FakeServices(), cors_origins=[DEV_ORIGIN])) as client:
        response = preflight(client, "https://example.com")
    assert "access-control-allow-origin" not in response.headers


@packaged
def test_forecast_options_describe_the_rules():
    from api.services import Services

    services = Services()
    services.store.record = lambda *arguments: None
    with TestClient(create_app(services)) as client:
        options = client.get("/forecast/options").json()
        last_day = client.get("/forecast/orders", params={"start": options["latest_daily_date"]})
        after = client.get("/forecast/orders", params={"start": "2018-09-19"})
        week = client.get(
            "/forecast/category",
            params={"week_end": options["latest_week_end"], "category": options["categories"][0]},
        )

    assert options["data_end_date"] == "2018-08-21"
    assert options["latest_daily_date"] == "2018-09-18"
    assert len(options["categories"]) == 10
    assert last_day.status_code == 200
    assert after.status_code == 422
    assert week.status_code == 200


@pytest.mark.parametrize("path", ["/health", "/models", "/forecast/options"])
def test_frontend_paths_exist(path):
    assert path in create_app().openapi()["paths"]
