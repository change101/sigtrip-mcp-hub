from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any

from pydantic import ValidationError

from src.models import ApiError, BookingResponse, CompareHotelsResponse, ErrorEnvelope, GuestDetails, HotelComparisonItem, SearchHotelsResponse
from src.providers.base import HotelProvider
from src.providers.sigtrip import SigtripProvider


class HotelWrapperService:
    def __init__(self, provider: HotelProvider | None = None):
        self.provider: HotelProvider = provider or SigtripProvider()

    async def search_hotel_offers(
        self,
        location: str,
        check_in: str | None = None,
        check_out: str | None = None,
        guests: int = 1,
        max_hotels: int = 5,
        max_offers_per_hotel: int = 3,
    ) -> dict[str, Any]:
        normalized_check_in, normalized_check_out, date_metadata = _normalize_or_default_dates(check_in, check_out)
        safe_guests = max(1, guests)
        response: SearchHotelsResponse = await self.provider.search_hotel_offers(
            location=location,
            check_in=normalized_check_in,
            check_out=normalized_check_out,
            guests=safe_guests,
            max_hotels=max_hotels,
            max_offers_per_hotel=max_offers_per_hotel,
        )
        output = response.model_dump(mode="json")
        provider_metadata = output.get("metadata", {})
        metadata = _build_metadata(
            raw_location=location,
            raw_check_in=check_in,
            raw_check_out=check_out,
            raw_guests=guests,
            normalized_location=location,
            normalized_check_in=normalized_check_in,
            normalized_check_out=normalized_check_out,
            normalized_guests=safe_guests,
            hotels=output.get("hotels", []),
            date_metadata=date_metadata,
            interpreted_from_query=False,
        )
        metadata["provider_metadata"] = provider_metadata
        metadata["contract_version"] = "v1"
        output["metadata"] = metadata
        return output

    async def plan_hotel_options(
        self,
        query: str,
        max_hotels: int = 5,
        max_offers_per_hotel: int = 3,
    ) -> dict[str, Any]:
        parsed = _parse_natural_query(query)
        result = await self.search_hotel_offers(
            location=parsed["location"],
            check_in=parsed.get("check_in"),
            check_out=parsed.get("check_out"),
            guests=parsed.get("guests", 1),
            max_hotels=max_hotels,
            max_offers_per_hotel=max_offers_per_hotel,
        )
        metadata = result.get("metadata", {})
        metadata["interpreted_from_query"] = True
        metadata["query_parse"] = {
            "raw_query": query,
            "location": parsed.get("location"),
            "check_in": parsed.get("check_in"),
            "check_out": parsed.get("check_out"),
            "guests": parsed.get("guests", 1),
        }
        result["metadata"] = metadata
        return result

    async def create_booking_request(self, offer_id: str, guest_details: str) -> dict[str, Any]:
        guest = self._parse_guest_details(guest_details)
        if isinstance(guest, dict):
            return guest

        response: BookingResponse = await self.provider.create_booking_request(offer_id, guest)
        payload = response.model_dump(mode="json")
        if payload.get("status") == "failed":
            return error_envelope(
                code="BOOKING_FAILED",
                message=payload.get("error") or "Booking failed",
                retryable=False,
                details={"offer_id": offer_id},
            )
        payload["contract_version"] = "v1"
        return payload

    async def compare_hotels(
        self,
        location: str,
        hotel_ids: list[str] | None = None,
        check_in: str | None = None,
        check_out: str | None = None,
        guests: int = 1,
        max_hotels: int = 8,
    ) -> dict[str, Any]:
        search = await self.search_hotel_offers(
            location=location,
            check_in=check_in,
            check_out=check_out,
            guests=guests,
            max_hotels=max_hotels,
            max_offers_per_hotel=5,
        )
        hotels = search.get("hotels", [])
        if hotel_ids:
            requested = set(hotel_ids)
            hotels = [hotel for hotel in hotels if hotel.get("hotel_id") in requested]

        grouped = _group_hotels_by_property(hotels)
        ranked = sorted(grouped, key=lambda h: h.get("price_preview", {}).get("from_total") or float("inf"))
        comparison_items: list[HotelComparisonItem] = []
        for idx, hotel in enumerate(ranked, start=1):
            preview = hotel.get("price_preview", {})
            rank = idx if preview.get("from_total") is not None else None
            comparison_items.append(
                HotelComparisonItem(
                    property_id=hotel.get("property_id"),
                    hotel_id=hotel.get("hotel_id"),
                    provider_ids=hotel.get("provider_ids", [hotel.get("hotel_id")]),
                    name=hotel.get("name"),
                    availability_status=hotel.get("availability_status", "unavailable"),
                    from_total=preview.get("from_total"),
                    currency=preview.get("currency"),
                    image_url=hotel.get("thumbnail_url"),
                    offer_count=len(hotel.get("top_offers", [])),
                    rank_by_price=rank,
                )
            )

        response = CompareHotelsResponse(
            provider=str(search.get("provider", "sigtrip")),
            query=dict(search.get("query", {})),
            metadata=dict(search.get("metadata", {})),
            comparison=comparison_items,
        )
        payload = response.model_dump(mode="json")
        payload["metadata"]["comparison_count"] = len(comparison_items)
        payload["metadata"]["filtered_by_hotel_ids"] = bool(hotel_ids)
        payload["metadata"]["dedupe_strategy"] = "group_by_property_id"
        payload["metadata"]["contract_version"] = "v1"
        return payload

    async def compare_hotels_from_query(
        self,
        query: str,
        hotel_ids: list[str] | None = None,
        max_hotels: int = 8,
    ) -> dict[str, Any]:
        parsed = _parse_natural_query(query)
        result = await self.compare_hotels(
            location=parsed["location"],
            hotel_ids=hotel_ids,
            check_in=parsed.get("check_in"),
            check_out=parsed.get("check_out"),
            guests=parsed.get("guests", 1),
            max_hotels=max_hotels,
        )
        metadata = result.get("metadata", {})
        metadata["interpreted_from_query"] = True
        metadata["query_parse"] = {
            "raw_query": query,
            "location": parsed.get("location"),
            "check_in": parsed.get("check_in"),
            "check_out": parsed.get("check_out"),
            "guests": parsed.get("guests", 1),
        }
        result["metadata"] = metadata
        return result

    async def cancel_booking(
        self,
        provider_booking_ref: str,
        reason: str | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        if not provider_booking_ref.strip():
            return error_envelope(
                code="INVALID_PROVIDER_BOOKING_REF",
                message="provider_booking_ref is required",
                retryable=False,
            )
        response = await self.provider.cancel_booking(
            provider_booking_ref=provider_booking_ref,
            reason=reason,
            email=email,
        )
        payload = response.model_dump(mode="json")
        if payload.get("status") == "failed" and payload.get("required_fields"):
            return error_envelope(
                code="MISSING_CANCELLATION_FIELDS",
                message=payload.get("message") or "Cancellation requires additional fields.",
                retryable=False,
                details={
                    "required_fields": payload.get("required_fields"),
                    "next_action": payload.get("next_action"),
                    "provider_booking_ref": provider_booking_ref,
                },
            )
        payload["contract_version"] = "v1"
        return payload

    async def get_booking_status(self, provider_booking_ref: str) -> dict[str, Any]:
        if not provider_booking_ref.strip():
            return error_envelope(
                code="INVALID_PROVIDER_BOOKING_REF",
                message="provider_booking_ref is required",
                retryable=False,
            )
        response = await self.provider.get_booking_status(provider_booking_ref=provider_booking_ref)
        payload = response.model_dump(mode="json")
        payload["contract_version"] = "v1"
        return payload

    def _parse_guest_details(self, guest_details: str) -> GuestDetails | dict[str, Any]:
        try:
            raw = json.loads(guest_details)
        except json.JSONDecodeError:
            return error_envelope(
                code="INVALID_GUEST_DETAILS_JSON",
                message="guest_details must be valid JSON string",
                retryable=False,
            )

        try:
            return GuestDetails.model_validate(raw)
        except ValidationError as exc:
            return error_envelope(
                code="INVALID_GUEST_DETAILS_SCHEMA",
                message="guest_details schema validation failed",
                retryable=False,
                details={"validation_errors": exc.errors()},
            )


def _normalize_or_default_dates(check_in: str | None, check_out: str | None) -> tuple[str, str, dict[str, bool]]:
    metadata = {"used_default_dates": False, "normalized_dates": False}
    if not check_in or not check_out:
        today = dt.date.today()
        metadata["used_default_dates"] = True
        return (today + dt.timedelta(days=1)).isoformat(), (today + dt.timedelta(days=2)).isoformat(), metadata

    parsed_in = _parse_date(check_in)
    parsed_out = _parse_date(check_out)
    if parsed_in is None or parsed_out is None:
        today = dt.date.today()
        metadata["used_default_dates"] = True
        return (today + dt.timedelta(days=1)).isoformat(), (today + dt.timedelta(days=2)).isoformat(), metadata
    metadata["normalized_dates"] = (check_in != parsed_in.isoformat()) or (check_out != parsed_out.isoformat())
    if parsed_out <= parsed_in:
        parsed_out = parsed_in + dt.timedelta(days=1)
        metadata["normalized_dates"] = True
    return parsed_in.isoformat(), parsed_out.isoformat(), metadata


def _parse_date(raw: str) -> dt.date | None:
    candidates = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%m-%d-%Y",
        "%Y/%m/%d",
    ]
    value = raw.strip()
    for fmt in candidates:
        try:
            return dt.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _parse_natural_query(query: str) -> dict[str, Any]:
    location = _extract_location(query) or query.strip()
    guests = _extract_guests(query) or 1
    check_in, check_out = _extract_dates(query)
    return {
        "location": location,
        "guests": guests,
        "check_in": check_in,
        "check_out": check_out,
    }


def _extract_location(query: str) -> str | None:
    match = re.search(r"\bin\s+([a-zA-Z][a-zA-Z\s]+?)(?:\s+(?:for|from|with|check|on)\b|$)", query, re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip(" .,!?\t")


def _extract_guests(query: str) -> int | None:
    match = re.search(r"\b(\d+)\s*(?:guest|guests|adult|adults)\b", query, re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def _extract_dates(query: str) -> tuple[str | None, str | None]:
    patterns = [
        r"\b(\d{4}-\d{2}-\d{2})\s*(?:to|-)\s*(\d{4}-\d{2}-\d{2})\b",
        r"\b(\d{1,2}/\d{1,2}/\d{4})\s*(?:to|-)\s*(\d{1,2}/\d{1,2}/\d{4})\b",
        r"\bfrom\s+(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})\s+to\s+(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4})\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            return match.group(1), match.group(2)
    return None, None


def _build_metadata(
    raw_location: str,
    raw_check_in: str | None,
    raw_check_out: str | None,
    raw_guests: int,
    normalized_location: str,
    normalized_check_in: str,
    normalized_check_out: str,
    normalized_guests: int,
    hotels: list[dict[str, Any]],
    date_metadata: dict[str, bool],
    interpreted_from_query: bool,
) -> dict[str, Any]:
    warnings: list[str] = []
    defaults_applied: list[str] = []
    if date_metadata.get("used_default_dates"):
        defaults_applied.append("dates")
        warnings.append("Dates were missing or invalid; default date range was applied.")
    if raw_guests < 1:
        defaults_applied.append("guests")
        warnings.append("Guests must be >= 1; guests was set to 1.")

    source_summary = {
        "image": "upstream",
        "pricing": "upstream",
    }
    if any(h.get("image_source") != "upstream" for h in hotels):
        source_summary["image"] = "mixed"
    if any(h.get("pricing_source") != "upstream" for h in hotels):
        source_summary["pricing"] = "mixed"

    return {
        "interpreted_from_query": interpreted_from_query,
        "raw_input": {
            "location": raw_location,
            "check_in": raw_check_in,
            "check_out": raw_check_out,
            "guests": raw_guests,
        },
        "normalized_input": {
            "location": normalized_location,
            "check_in": normalized_check_in,
            "check_out": normalized_check_out,
            "guests": normalized_guests,
        },
        "defaults_applied": defaults_applied,
        "warnings": warnings,
        "data_source": source_summary,
    }


def error_envelope(code: str, message: str, retryable: bool = False, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return ErrorEnvelope(
        error=ApiError(code=code, message=message, retryable=retryable, details=details),
    ).model_dump(mode="json")


def _group_hotels_by_property(hotels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for hotel in hotels:
        key = hotel.get("property_id") or hotel.get("hotel_id")
        groups.setdefault(str(key), []).append(hotel)

    deduped: list[dict[str, Any]] = []
    for group_hotels in groups.values():
        best = min(group_hotels, key=lambda h: h.get("price_preview", {}).get("from_total") or float("inf"))
        all_provider_ids: list[str] = []
        for candidate in group_hotels:
            ids = candidate.get("provider_ids", [])
            if not ids and candidate.get("hotel_id"):
                ids = [candidate["hotel_id"]]
            for provider_id in ids:
                if provider_id not in all_provider_ids:
                    all_provider_ids.append(provider_id)
        best = dict(best)
        best["provider_ids"] = all_provider_ids
        deduped.append(best)

    return deduped
