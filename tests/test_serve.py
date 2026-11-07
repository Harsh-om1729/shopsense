"""Tests for serving the site and API together."""

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from api.serve import create_production_app
from tests.test_api import FakeServices


@pytest.fixture
def site(tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>ShopSense</title>")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('app')")
    return tmp_path


@pytest.fixture
def client(site):
    app = create_production_app(site, api=create_app(FakeServices()))
    with TestClient(app) as test_client:
        yield test_client


def test_api_is_under_api(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_site_is_at_the_root(client):
    response = client.get("/")
    assert "<title>ShopSense</title>" in response.text


def test_site_files_are_served(client):
    assert client.get("/assets/app.js").text == "console.log('app')"


def test_refreshing_a_site_page_returns_the_app(client):
    response = client.get("/reviews")
    assert response.status_code == 200
    assert "<title>ShopSense</title>" in response.text


def test_unknown_api_paths_stay_errors(client):
    assert client.get("/api/not-a-real-endpoint").status_code == 404


def test_api_docs_still_work(client):
    assert client.get("/api/openapi.json").status_code == 200


def test_missing_site_gives_a_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="npm run build"):
        create_production_app(tmp_path)
