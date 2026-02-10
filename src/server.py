from __future__ import annotations

import datetime as dt
import os

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from src.service import HotelWrapperService

load_dotenv()

MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8000"))
APP_ENV = os.getenv("APP_ENV", "dev")
APP_VERSION = os.getenv("APP_VERSION", "0.1.0")
SIGTRIP_UPSTREAM_URL = os.getenv("SIGTRIP_UPSTREAM_URL", "https://hotel.sigtrip.ai/mcp")
SIGTRIP_API_KEY_SET = bool(os.getenv("SIGTRIP_API_KEY"))

mcp = FastMCP("SigTrip_Wrapper_Node", host=MCP_HOST, port=MCP_PORT)
service = HotelWrapperService()


@mcp.custom_route("/healthz", methods=["GET"], include_in_schema=False)
async def healthz(_request: Request) -> Response:
    return JSONResponse(
        {
            "status": "ok",
            "service": "sigtrip-wrapper-mcp",
            "env": APP_ENV,
            "version": APP_VERSION,
        },
        status_code=200,
    )


@mcp.custom_route("/readyz", methods=["GET"], include_in_schema=False)
async def readyz(_request: Request) -> Response:
    issues: list[str] = []
    if not SIGTRIP_API_KEY_SET:
        issues.append("SIGTRIP_API_KEY is not set")
    if not SIGTRIP_UPSTREAM_URL:
        issues.append("SIGTRIP_UPSTREAM_URL is not set")

    if issues:
        return JSONResponse(
            {
                "status": "not_ready",
                "service": "sigtrip-wrapper-mcp",
                "issues": issues,
            },
            status_code=503,
        )

    return JSONResponse(
        {
            "status": "ready",
            "service": "sigtrip-wrapper-mcp",
            "upstream": SIGTRIP_UPSTREAM_URL,
            "api_key_configured": SIGTRIP_API_KEY_SET,
        },
        status_code=200,
    )


@mcp.tool()
async def search_hotel_offers(
    location: str,
    check_in: str | None = None,
    check_out: str | None = None,
    guests: int = 1,
    max_hotels: int = 5,
    max_offers_per_hotel: int = 3,
    ) -> dict:
    """Return multiple hotels with images and upfront 'price from' previews."""
    return await service.search_hotel_offers(
        location=location,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        max_hotels=max_hotels,
        max_offers_per_hotel=max_offers_per_hotel,
    )


@mcp.tool()
async def plan_hotel_options(
    query: str,
    max_hotels: int = 5,
    max_offers_per_hotel: int = 3,
) -> dict:
    """Natural-language entrypoint. Example: 'Show me hotels in Denver'."""
    return await service.plan_hotel_options(
        query=query,
        max_hotels=max_hotels,
        max_offers_per_hotel=max_offers_per_hotel,
    )


@mcp.tool()
async def compare_hotels(
    location: str,
    hotel_ids: list[str] | None = None,
    check_in: str | None = None,
    check_out: str | None = None,
    guests: int = 1,
    max_hotels: int = 8,
) -> dict:
    """Compare hotels by upfront price and availability."""
    return await service.compare_hotels(
        location=location,
        hotel_ids=hotel_ids,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        max_hotels=max_hotels,
    )


@mcp.tool()
async def compare_hotels_from_query(
    query: str,
    hotel_ids: list[str] | None = None,
    max_hotels: int = 8,
) -> dict:
    """Natural-language comparison entrypoint. Example: 'Compare hotels in Denver for 2 guests'."""
    return await service.compare_hotels_from_query(
        query=query,
        hotel_ids=hotel_ids,
        max_hotels=max_hotels,
    )


@mcp.tool()
async def create_booking_request(
    guest_details: str,
    offer_id: str | None = None,
    room_id: str | None = None,
    hotel_id: str | None = None,
) -> dict:
    """Create booking payment request. Supports new offer_id and legacy room_id inputs."""
    del hotel_id
    effective_offer_id = offer_id or room_id
    if not effective_offer_id:
        return {"status": "failed", "error": "offer_id (or legacy room_id) is required"}
    return await service.create_booking_request(offer_id=effective_offer_id, guest_details=guest_details)


# Backward-compatible aliases for existing integrations.
@mcp.tool()
async def discover_hotels(location: str) -> dict:
    """Deprecated alias. Use search_hotel_offers instead."""
    check_in, check_out = _default_dates()
    result = await service.search_hotel_offers(
        location=location,
        check_in=check_in,
        check_out=check_out,
        guests=1,
        max_hotels=5,
        max_offers_per_hotel=1,
    )

    hotels = []
    for item in result.get("hotels", []):
        offers = item.get("top_offers", [])
        room_names = ", ".join(offer.get("room_name", "Room") for offer in offers[:3])
        hotels.append(
            {
                "id": item.get("hotel_id"),
                "name": item.get("name"),
                "location": {
                    "city": location.title(),
                    "country_code": "US",
                    "address": "Address provided at booking",
                },
                "description": f"Available rooms: {room_names}." if room_names else "No offers currently available.",
                "amenities": ["wifi_free"],
                "images": item.get("image_urls", []),
            }
        )
    return hotels


@mcp.tool()
async def get_availability(hotel_id: str, check_in: str, check_out: str, guests: int = 1) -> list[dict]:
    """Deprecated alias. Use search_hotel_offers and read top_offers instead."""
    location_guess = _location_from_hotel_id(hotel_id)
    result = await service.search_hotel_offers(
        location=location_guess,
        check_in=check_in,
        check_out=check_out,
        guests=guests,
        max_hotels=10,
        max_offers_per_hotel=10,
    )

    for item in result.get("hotels", []):
        if item.get("hotel_id") == hotel_id:
            legacy_rooms = []
            for offer in item.get("top_offers", []):
                legacy_rooms.append(
                    {
                        "room_id": offer.get("offer_id"),
                        "name": offer.get("room_name"),
                        "price": {
                            "amount": offer.get("total_amount"),
                            "currency": offer.get("currency"),
                        },
                        "category": offer.get("category", "Standard"),
                    }
                )
            return legacy_rooms

    return []


def _default_dates() -> tuple[str, str]:
    today = dt.date.today()
    check_in = today + dt.timedelta(days=1)
    check_out = today + dt.timedelta(days=2)
    return check_in.isoformat(), check_out.isoformat()


def _location_from_hotel_id(hotel_id: str) -> str:
    if hotel_id == "sigtrip:The_Rally_Hotel":
        return "denver"
    if hotel_id == "sigtrip:Club_Quarters,_Trafalgar_Square":
        return "london"
    if hotel_id == "sigtrip:Club_Quarters,_Grand_Central":
        return "new york"

    if hotel_id.startswith("sigtrip:"):
        return hotel_id.removeprefix("sigtrip:").replace("_", " ")
    return "unknown"


if __name__ == "__main__":
    mcp.run(transport="sse")
