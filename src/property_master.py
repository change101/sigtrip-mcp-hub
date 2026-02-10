from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PropertyRecord:
    property_id: str
    name: str
    city: str
    country_code: str
    address: str
    description: str
    amenities: list[str]
    rating_score: float | None = None
    rating_provider: str | None = None
    instant_confirmation: bool = False
    pay_at_hotel: bool = True
    requires_stripe_token: bool = True
    aliases: tuple[str, ...] = ()


PROPERTY_MASTER: dict[str, PropertyRecord] = {
    "prop_us_denver_rally_hotel": PropertyRecord(
        property_id="prop_us_denver_rally_hotel",
        name="The Rally Hotel",
        city="Denver",
        country_code="US",
        address="1600 20th St, Denver, CO 80202",
        description="Boutique hotel near Coors Field with modern rooms and city-view options.",
        amenities=["wifi_free", "gym", "restaurant", "desk_work_friendly"],
        rating_score=4.4,
        rating_provider="internal_curated",
        instant_confirmation=False,
        pay_at_hotel=True,
        requires_stripe_token=True,
        aliases=("rally hotel",),
    ),
    "prop_us_nyc_clubq_grand_central": PropertyRecord(
        property_id="prop_us_nyc_clubq_grand_central",
        name="Club Quarters, Grand Central",
        city="New York",
        country_code="US",
        address="128 E 45th St, New York, NY 10017",
        description="Midtown Manhattan hotel with work-friendly amenities near Grand Central.",
        amenities=["wifi_free", "gym", "desk_work_friendly"],
        rating_score=4.1,
        rating_provider="internal_curated",
        instant_confirmation=False,
        pay_at_hotel=True,
        requires_stripe_token=True,
        aliases=("club quarters grand central",),
    ),
    "prop_uk_london_clubq_trafalgar": PropertyRecord(
        property_id="prop_uk_london_clubq_trafalgar",
        name="Club Quarters, Trafalgar Square",
        city="London",
        country_code="GB",
        address="8 Northumberland Ave, London WC2N 5BY",
        description="Central London business hotel close to Trafalgar Square.",
        amenities=["wifi_free", "gym", "desk_work_friendly", "restaurant"],
        rating_score=4.0,
        rating_provider="internal_curated",
        instant_confirmation=False,
        pay_at_hotel=True,
        requires_stripe_token=True,
        aliases=("club quarters trafalgar square",),
    ),
}


PROVIDER_TO_PROPERTY: dict[str, str] = {
    "sigtrip:The_Rally_Hotel": "prop_us_denver_rally_hotel",
    "sigtrip:Club_Quarters,_Grand_Central": "prop_us_nyc_clubq_grand_central",
    "sigtrip:Club_Quarters,_Trafalgar_Square": "prop_uk_london_clubq_trafalgar",
}


def resolve_property(
    *,
    provider_hotel_id: str,
    hotel_name: str,
    city: str,
    country_code: str = "US",
) -> tuple[dict[str, Any], dict[str, Any]]:
    if provider_hotel_id in PROVIDER_TO_PROPERTY:
        property_id = PROVIDER_TO_PROPERTY[provider_hotel_id]
        record = PROPERTY_MASTER[property_id]
        return _record_to_profile(record), {"method": "provider_id_map", "confidence": 1.0}

    candidate = _find_by_name_city(hotel_name, city)
    if candidate is not None:
        return _record_to_profile(candidate), {"method": "name_city_match", "confidence": 0.75}

    fallback = {
        "property_id": _fallback_property_id(hotel_name, city),
        "name": hotel_name,
        "location_details": {
            "address": "Unknown",
            "city": city.title(),
            "country_code": country_code.upper(),
        },
        "description": "",
        "amenities": [],
        "rating": None,
        "booking_capabilities": {
            "instant_confirmation": False,
            "pay_at_hotel": True,
            "requires_stripe_token": True,
        },
    }
    return fallback, {"method": "fallback_generated", "confidence": 0.2}


def _find_by_name_city(hotel_name: str, city: str) -> PropertyRecord | None:
    target_name = _norm(hotel_name)
    target_city = _norm(city)
    for record in PROPERTY_MASTER.values():
        names = [_norm(record.name), *[_norm(alias) for alias in record.aliases]]
        if target_city == _norm(record.city) and target_name in names:
            return record
    return None


def _record_to_profile(record: PropertyRecord) -> dict[str, Any]:
    rating = None
    if record.rating_score is not None:
        rating = {"score": record.rating_score, "provider": record.rating_provider}

    return {
        "property_id": record.property_id,
        "name": record.name,
        "location_details": {
            "address": record.address,
            "city": record.city,
            "country_code": record.country_code,
        },
        "description": record.description,
        "amenities": list(record.amenities),
        "rating": rating,
        "booking_capabilities": {
            "instant_confirmation": record.instant_confirmation,
            "pay_at_hotel": record.pay_at_hotel,
            "requires_stripe_token": record.requires_stripe_token,
        },
    }


def _fallback_property_id(hotel_name: str, city: str) -> str:
    return f"prop_unmapped_{_slug(city)}_{_slug(hotel_name)}"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
