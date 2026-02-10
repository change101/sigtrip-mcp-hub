from __future__ import annotations

import re
from typing import Any

from src.client import call_upstream
from src.models import BookingResponse, GuestDetails, HotelCard, Offer, PricePreview, SearchHotelsResponse
from src.property_master import resolve_property


LOCATION_MAP = {
    "london": ["Club Quarters, Trafalgar Square"],
    "denver": ["The Rally Hotel"],
    "new york": ["Club Quarters, Grand Central"],
}

FALLBACK_IMAGE_BY_CITY = {
    "london": "https://images.unsplash.com/photo-1486299267070-83823f5448dd",
    "denver": "https://images.unsplash.com/photo-1514924013411-cbf25faa35bb",
    "new york": "https://images.unsplash.com/photo-1485871981521-5b1fd3805eee",
}


class SigtripProvider:
    provider_name = "sigtrip"

    async def search_hotel_offers(
        self,
        location: str,
        check_in: str,
        check_out: str,
        guests: int,
        max_hotels: int,
        max_offers_per_hotel: int,
    ) -> SearchHotelsResponse:
        hotels = self._resolve_target_hotels(location)[:max_hotels]
        hotel_cards: list[HotelCard] = []

        for hotel_name in hotels:
            provider_hotel_id = self._hotel_id(hotel_name)
            rooms_data = await call_upstream(
                "get_rooms",
                {
                    "hotelName": hotel_name,
                    "adults": guests,
                },
            )
            prices_data = await call_upstream(
                "get_prices",
                {
                    "hotelName": hotel_name,
                    "arrivalDate": check_in,
                    "departureDate": check_out,
                    "adults": guests,
                },
            )

            prices = prices_data.get("prices", []) if isinstance(prices_data, dict) else []
            offers = self._map_offers(hotel_name, prices, max_offers_per_hotel)
            price_preview = self._build_price_preview(offers)

            images = await self._fetch_image_urls(hotel_name, rooms_data)
            has_upstream_images = bool(images)
            fallback_image = self._fallback_image(location)
            thumbnail = images[0] if images else fallback_image
            if thumbnail and thumbnail not in images:
                images = [thumbnail, *images]
            image_source = "upstream" if has_upstream_images else "fallback"
            if not images and not thumbnail:
                image_source = "none"

            canonical, mapping = resolve_property(
                provider_hotel_id=provider_hotel_id,
                hotel_name=hotel_name,
                city=location,
                country_code="US",
            )

            hotel_cards.append(
                HotelCard(
                    hotel_id=provider_hotel_id,
                    property_id=canonical.get("property_id"),
                    provider_ids=[provider_hotel_id],
                    name=canonical.get("name") or hotel_name,
                    location=str(canonical.get("location_details", {}).get("city") or location.title()),
                    location_details=canonical.get("location_details"),
                    description=canonical.get("description"),
                    amenities=canonical.get("amenities", []),
                    rating=canonical.get("rating"),
                    booking_capabilities=canonical.get("booking_capabilities"),
                    thumbnail_url=thumbnail,
                    image_urls=images[:5],
                    price_preview=price_preview,
                    availability_status="available" if offers else "unavailable",
                    image_source=image_source,
                    pricing_source="upstream" if offers else "none",
                    top_offers=offers,
                )
            )

        return SearchHotelsResponse(
            provider=self.provider_name,
            query={
                "location": location,
                "check_in": check_in,
                "check_out": check_out,
                "guests": guests,
            },
            metadata={
                "canonical_mapping": {
                    "strategy": "provider_id_map_then_name_city_then_fallback",
                    "provider": self.provider_name,
                    "last_mapping_method": mapping["method"] if hotels else None,
                }
            },
            hotels=hotel_cards,
        )

    async def create_booking_request(self, offer_id: str, guest: GuestDetails) -> BookingResponse:
        parsed = self._parse_offer_id(offer_id)
        if parsed is None:
            return BookingResponse(status="failed", error="Invalid offer_id format")

        hotel_name, room_type = parsed
        data = await call_upstream(
            "setup_booking",
            {
                "hotelName": hotel_name,
                "roomType": room_type,
                "firstName": guest.first_name,
                "lastName": guest.last_name,
                "email": guest.email,
                "phoneNumber": guest.phone,
                "checkIn": guest.check_in,
                "checkOut": guest.check_out,
                "guests": guest.guests,
            },
        )

        if isinstance(data, dict) and data.get("guaranteeUrl"):
            return BookingResponse(
                status="payment_required",
                payment_url=data["guaranteeUrl"],
                session_expiration="15m",
                provider_reference=str(data.get("bookingId", "")) or None,
            )

        return BookingResponse(status="failed", error="Booking failed. Room may be unavailable.")

    def _resolve_target_hotels(self, location: str) -> list[str]:
        normalized = location.lower()
        for city_key, hotels in LOCATION_MAP.items():
            if city_key in normalized:
                return hotels
        return []

    def _hotel_id(self, hotel_name: str) -> str:
        return f"sigtrip:{hotel_name.replace(' ', '_')}"

    def _offer_id(self, hotel_name: str, room_type: str) -> str:
        return f"sigtrip:{hotel_name.replace(' ', '_')}:{room_type}"

    def _map_offers(self, hotel_name: str, prices: list[dict[str, Any]], max_offers: int) -> list[Offer]:
        offers: list[Offer] = []
        for item in prices[:max_offers]:
            room_type = str(item.get("roomType") or "UNKNOWN")
            total_amount = _to_float(item.get("totalAmount"))
            nightly_amount = _to_float(item.get("nightlyAmount"))

            offers.append(
                Offer(
                    offer_id=self._offer_id(hotel_name, room_type),
                    room_type=room_type,
                    room_name=str(item.get("roomDescription") or "Room"),
                    total_amount=total_amount,
                    nightly_amount=nightly_amount,
                    currency=item.get("currency"),
                    category=item.get("category"),
                    cancellation_policy=item.get("cancellationPolicy"),
                )
            )

        offers.sort(key=lambda x: x.total_amount if x.total_amount is not None else float("inf"))
        return offers

    def _build_price_preview(self, offers: list[Offer]) -> PricePreview:
        if not offers:
            return PricePreview()

        best = min(offers, key=lambda x: x.total_amount if x.total_amount is not None else float("inf"))
        return PricePreview(
            from_total=best.total_amount,
            from_nightly=best.nightly_amount,
            currency=best.currency,
            includes_taxes_fees=True,
        )

    async def _fetch_image_urls(self, hotel_name: str, rooms_data: dict[str, Any] | None) -> list[str]:
        rooms: list[dict[str, Any]] = []
        if isinstance(rooms_data, dict):
            rooms = rooms_data.get("rooms", []) or []

        image_query_rooms = [
            {
                "roomType": str(room.get("roomType") or room.get("roomCode") or "Standard"),
                "title": str(room.get("roomDescription") or room.get("title") or "Room"),
            }
            for room in rooms[:3]
        ]
        if not image_query_rooms:
            return []

        payload = {
            "hotelName": hotel_name,
            "expectedCount": len(image_query_rooms),
            "rooms": image_query_rooms,
        }
        gallery_data = await call_upstream("view_room_gallery", payload)
        return _extract_image_urls(gallery_data)

    def _fallback_image(self, location: str) -> str | None:
        normalized = location.lower()
        for city_key, image_url in FALLBACK_IMAGE_BY_CITY.items():
            if city_key in normalized:
                return image_url
        return None

    def _parse_offer_id(self, offer_id: str) -> tuple[str, str] | None:
        match = re.match(r"^sigtrip:([^:]+):([^:]+)$", offer_id)
        if not match:
            return None
        hotel_slug, room_type = match.groups()
        return hotel_slug.replace("_", " "), room_type


def _to_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_image_urls(data: Any) -> list[str]:
    found: list[str] = []

    def walk(node: Any):
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
            return
        if isinstance(node, list):
            for item in node:
                walk(item)
            return
        if isinstance(node, str):
            if node.startswith("http") and _looks_like_image_url(node):
                found.append(node)

    walk(data)

    deduped: list[str] = []
    for url in found:
        if url not in deduped:
            deduped.append(url)
    return deduped


def _looks_like_image_url(url: str) -> bool:
    lowered = url.lower()
    if any(ext in lowered for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif")):
        return True
    return any(token in lowered for token in ("image", "img", "cloudinary", "unsplash"))
