"""Request and response shapes. FastAPI validates these and documents them at /docs."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.data.preprocess import LAT_BOUNDS, LNG_BOUNDS

BrazilState = Literal[
    "AC",
    "AL",
    "AM",
    "AP",
    "BA",
    "CE",
    "DF",
    "ES",
    "GO",
    "MA",
    "MG",
    "MS",
    "MT",
    "PA",
    "PB",
    "PE",
    "PI",
    "PR",
    "RJ",
    "RN",
    "RO",
    "RR",
    "RS",
    "SC",
    "SE",
    "SP",
    "TO",
]


class Request(BaseModel):
    """Reject unknown fields, so a misspelled field can't be silently ignored."""

    model_config = ConfigDict(extra="forbid")


class FreightRequest(Request):
    customer_state: BrazilState
    seller_state: BrazilState
    customer_lat: float | None = Field(None, ge=LAT_BOUNDS[0], le=LAT_BOUNDS[1])
    customer_lng: float | None = Field(None, ge=LNG_BOUNDS[0], le=LNG_BOUNDS[1])
    seller_lat: float | None = Field(None, ge=LAT_BOUNDS[0], le=LAT_BOUNDS[1])
    seller_lng: float | None = Field(None, ge=LNG_BOUNDS[0], le=LNG_BOUNDS[1])
    customer_zip_prefix: int | None = Field(None, ge=0, le=99999)
    seller_zip_prefix: int | None = Field(None, ge=0, le=99999)
    product_weight_g: float | None = Field(None, gt=0)
    product_length_cm: float | None = Field(None, gt=0)
    product_height_cm: float | None = Field(None, gt=0)
    product_width_cm: float | None = Field(None, gt=0)
    price: float = Field(gt=0)
    quantity: int = Field(1, ge=1)
    category: str | None = None

    @model_validator(mode="after")
    def one_location_per_party(self):
        """Refuse a zip plus coordinates, since they could disagree."""
        for party in ("customer", "seller"):
            has_zip = getattr(self, f"{party}_zip_prefix") is not None
            has_coordinates = (
                getattr(self, f"{party}_lat") is not None
                or getattr(self, f"{party}_lng") is not None
            )
            if has_zip and has_coordinates:
                raise ValueError(f"Send {party} coordinates or a zip prefix, not both.")
        return self


class FreightResponse(BaseModel):
    predicted_freight: float
    distance_known: bool


class DeliveryRequest(Request):
    customer_state: BrazilState


class DeliveryResponse(BaseModel):
    customer_state: str
    predicted_days: float
    note: str


class DailyForecast(BaseModel):
    date: date
    predicted_orders: float


class CategoryForecast(BaseModel):
    week_end: date
    category: str
    predicted_items: float


class ReviewRisk(BaseModel):
    rank: int
    order_id: str
    risk_score: float
    is_overdue: bool
    customer_state: str
    seller_id: str


class ReviewQueue(BaseModel):
    window_start: date
    window_end: date
    orders_in_window: int
    scored_on_training_data: bool
    orders: list[ReviewRisk]


class SellerRisk(BaseModel):
    seller_id: str
    seller_state: str | None
    risk_score: float
    is_alert: bool
    days_since_last_sale: float
    revenue_90d: float | None


class SellerRiskList(BaseModel):
    snapshot_date: date
    sellers_in_snapshot: int
    alerts_in_snapshot: int
    scored_on_training_data: bool
    sellers: list[SellerRisk]


class ModelInfo(BaseModel):
    name: str
    problem: str
    status: str
    kind: str | None
    version: str
    verdict: str
    note: str | None


class Health(BaseModel):
    status: str
    database_ready: bool
    loaded: list[str]
    unavailable: dict[str, str]
