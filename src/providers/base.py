from __future__ import annotations

from typing import Protocol
from src.models import BookingResponse, GuestDetails, SearchHotelsResponse


class HotelProvider(Protocol):
    async def search_hotel_offers(
        self,
        location: str,
        check_in: str,
        check_out: str,
        guests: int,
        max_hotels: int,
        max_offers_per_hotel: int,
    ) -> SearchHotelsResponse:
        ...

    async def create_booking_request(self, offer_id: str, guest: GuestDetails) -> BookingResponse:
        ...
