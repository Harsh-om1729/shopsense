"""The ShopSense API.

Run with: uv run uvicorn api.main:app --reload
Interactive docs are at http://127.0.0.1:8000/docs
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.schemas import (
    CategoryForecast,
    DailyForecast,
    DeliveryRequest,
    DeliveryResponse,
    ForecastOptions,
    FreightRequest,
    FreightResponse,
    Health,
    ModelInfo,
    ReviewQueue,
    SellerRiskList,
)
from api.services import LATE_DELIVERY, Services
from src import config
from src.models.predictor import InvalidInputError, ModelNotAvailableError

MAX_FORECAST_DAYS = 28
MAX_LIST_ROWS = 100


def create_app(services: Services | None = None, cors_origins: list[str] | None = None) -> FastAPI:
    """Return the app. Tests pass fake services, and real ones load at startup."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.services = services or Services()
        yield

    app = FastAPI(
        title="ShopSense API",
        description="Predict problems before they happen.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Browsers block calls from another address unless the API allows it.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS if cors_origins is None else cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.exception_handler(InvalidInputError)
    async def invalid_input(request: Request, error: InvalidInputError) -> JSONResponse:
        return JSONResponse(
            status_code=422, content={"error": "invalid_input", "detail": str(error)}
        )

    @app.exception_handler(ModelNotAvailableError)
    async def not_available(request: Request, error: ModelNotAvailableError) -> JSONResponse:
        return JSONResponse(
            status_code=503, content={"error": "model_not_available", "detail": str(error)}
        )

    def get_services(request: Request) -> Services:
        return request.app.state.services

    @app.get("/health", response_model=Health, tags=["System"])
    def health(request: Request):
        """Report what's loaded. The held model is expected to be unavailable."""
        loaded = get_services(request)
        problems = set(loaded.unavailable) - {LATE_DELIVERY}
        database_ready = loaded.database_ready()
        return {
            "status": "degraded" if problems or not database_ready else "ok",
            "database_ready": database_ready,
            "loaded": sorted(loaded.predictors),
            "unavailable": loaded.unavailable,
        }

    @app.get("/models", response_model=list[ModelInfo], tags=["System"])
    def models(request: Request):
        """List every package with its status and holdout verdict."""
        return get_services(request).models()

    @app.post("/predict/freight", response_model=FreightResponse, tags=["Predictions"])
    def predict_freight(body: FreightRequest, request: Request):
        """Estimate the freight for one product on a route."""
        return get_services(request).freight(body.model_dump())

    @app.post("/predict/delivery-time", response_model=DeliveryResponse, tags=["Predictions"])
    def predict_delivery_time(body: DeliveryRequest, request: Request):
        """Estimate delivery days from a simple rule, the median by customer state."""
        return get_services(request).delivery_days(body.customer_state)

    @app.post("/predict/late-delivery", tags=["Predictions"])
    def predict_late_delivery(request: Request):
        """Always returns 503, because this model failed its holdout test."""
        get_services(request).late_delivery()

    @app.get("/forecast/orders", response_model=list[DailyForecast], tags=["Forecasts"])
    def forecast_orders(
        request: Request,
        start: date,
        days: int = Query(1, ge=1, le=MAX_FORECAST_DAYS),
    ):
        """Forecast daily orders with a simple rule."""
        return get_services(request).daily_forecast(start, days)

    @app.get("/forecast/options", response_model=ForecastOptions, tags=["Forecasts"])
    def forecast_options(request: Request):
        """Return the forecastable date range and categories."""
        return get_services(request).forecast_options()

    @app.get("/forecast/category", response_model=CategoryForecast, tags=["Forecasts"])
    def forecast_category(request: Request, week_end: date, category: str):
        """Forecast a top-10 category's items for the week ending on a Sunday."""
        return get_services(request).category_forecast(week_end, category)

    @app.get("/reviews/queue", response_model=ReviewQueue, tags=["Queues"])
    def review_queue(request: Request, limit: int = Query(20, ge=1, le=MAX_LIST_ROWS)):
        """Rank recent orders by low-review risk, for support to contact first."""
        return get_services(request).review_queue(limit)

    @app.get("/sellers/at-risk", response_model=SellerRiskList, tags=["Queues"])
    def sellers_at_risk(
        request: Request,
        limit: int = Query(20, ge=1, le=MAX_LIST_ROWS),
        alerts_only: bool = True,
    ):
        """List sellers likely to stop selling. Check revenue and recency too."""
        return get_services(request).sellers_at_risk(limit, alerts_only)

    return app


app = create_app()
