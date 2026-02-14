from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, HttpUrl


class PricePreview(BaseModel):
    from_total: float | None = None
    from_nightly: float | None = None
    currency: str | None = None
    includes_taxes_fees: bool = True


class Offer(BaseModel):
    offer_id: str
    room_type: str | None = None
    room_name: str
    total_amount: float | None = None
    nightly_amount: float | None = None
    currency: str | None = None
    category: str | None = None
    cancellation_policy: str | None = None


class HotelCard(BaseModel):
    hotel_id: str
    property_id: str | None = None
    provider: str = "sigtrip"
    provider_ids: list[str] = Field(default_factory=list)
    name: str
    location: str
    location_details: dict | None = None
    description: str | None = None
    amenities: list[str] = Field(default_factory=list)
    rating: dict | None = None
    booking_capabilities: dict | None = None
    thumbnail_url: HttpUrl | None = None
    image_urls: list[HttpUrl] = Field(default_factory=list)
    price_preview: PricePreview
    availability_status: Literal["available", "unavailable"]
    image_source: Literal["upstream", "fallback", "none"] = "none"
    pricing_source: Literal["upstream", "none"] = "none"
    top_offers: list[Offer] = Field(default_factory=list)


class SearchHotelsResponse(BaseModel):
    provider: str = "sigtrip"
    query: dict
    metadata: dict = Field(default_factory=dict)
    hotels: list[HotelCard] = Field(default_factory=list)


class HotelComparisonItem(BaseModel):
    property_id: str | None = None
    hotel_id: str
    provider_ids: list[str] = Field(default_factory=list)
    name: str
    availability_status: Literal["available", "unavailable"]
    from_total: float | None = None
    currency: str | None = None
    image_url: HttpUrl | None = None
    offer_count: int = 0
    rank_by_price: int | None = None


class CompareHotelsResponse(BaseModel):
    provider: str = "sigtrip"
    query: dict
    metadata: dict = Field(default_factory=dict)
    comparison: list[HotelComparisonItem] = Field(default_factory=list)


class GuestDetails(BaseModel):
    first_name: str
    last_name: str
    email: str
    phone: str
    check_in: str
    check_out: str
    guests: int = 1


class BookingResponse(BaseModel):
    status: Literal["payment_required", "failed"]
    payment_url: HttpUrl | None = None
    session_expiration: str | None = None
    provider_reference: str | None = None
    error: str | None = None


class ApiError(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: dict | None = None


class ErrorEnvelope(BaseModel):
    ok: Literal[False] = False
    error: ApiError


class BookingCancellationResponse(BaseModel):
    status: Literal["cancelled", "pending", "failed", "unsupported"]
    provider: str = "sigtrip"
    provider_reference: str | None = None
    message: str | None = None
    required_fields: list[str] | None = None
    next_action: str | None = None


class BookingStatusResponse(BaseModel):
    status: Literal["confirmed", "cancelled", "pending", "unknown", "unsupported"]
    provider: str = "sigtrip"
    provider_reference: str | None = None
    message: str | None = None
