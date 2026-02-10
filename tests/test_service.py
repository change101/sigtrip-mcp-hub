import unittest

from src.models import BookingResponse, HotelCard, Offer, PricePreview, SearchHotelsResponse
from src.service import HotelWrapperService


class FakeProvider:
    def __init__(self):
        self.last_search = None

    async def search_hotel_offers(self, location, check_in, check_out, guests, max_hotels, max_offers_per_hotel):
        self.last_search = {
            "location": location,
            "check_in": check_in,
            "check_out": check_out,
            "guests": guests,
        }
        return SearchHotelsResponse(
            provider="sigtrip",
            query={
                "location": location,
                "check_in": check_in,
                "check_out": check_out,
                "guests": guests,
            },
            hotels=[
                HotelCard(
                    hotel_id="sigtrip:The_Rally_Hotel",
                    property_id="prop_us_denver_rally_hotel",
                    provider_ids=["sigtrip:The_Rally_Hotel"],
                    name="The Rally Hotel",
                    location="Denver",
                    thumbnail_url="https://images.unsplash.com/photo-1514924013411-cbf25faa35bb",
                    image_urls=["https://images.unsplash.com/photo-1514924013411-cbf25faa35bb"],
                    price_preview=PricePreview(from_total=199.0, from_nightly=99.5, currency="USD"),
                    availability_status="available",
                    top_offers=[
                        Offer(
                            offer_id="sigtrip:The_Rally_Hotel:ASK",
                            room_type="ASK",
                            room_name="King Room",
                            total_amount=199.0,
                            nightly_amount=99.5,
                            currency="USD",
                        )
                    ],
                ),
                HotelCard(
                    hotel_id="sigtrip:Club_Quarters,_Grand_Central",
                    property_id="prop_us_nyc_clubq_grand_central",
                    provider_ids=["sigtrip:Club_Quarters,_Grand_Central"],
                    name="Club Quarters, Grand Central",
                    location="New York",
                    thumbnail_url="https://images.unsplash.com/photo-1485871981521-5b1fd3805eee",
                    image_urls=["https://images.unsplash.com/photo-1485871981521-5b1fd3805eee"],
                    price_preview=PricePreview(from_total=299.0, from_nightly=149.5, currency="USD"),
                    availability_status="available",
                    top_offers=[
                        Offer(
                            offer_id="sigtrip:Club_Quarters,_Grand_Central:GCK",
                            room_type="GCK",
                            room_name="Grand Central King",
                            total_amount=299.0,
                            nightly_amount=149.5,
                            currency="USD",
                        )
                    ],
                ),
                HotelCard(
                    hotel_id="provider2:rally_denver",
                    property_id="prop_us_denver_rally_hotel",
                    provider="provider2",
                    provider_ids=["provider2:rally_denver"],
                    name="The Rally Hotel",
                    location="Denver",
                    thumbnail_url="https://images.unsplash.com/photo-1514924013411-cbf25faa35bb",
                    image_urls=["https://images.unsplash.com/photo-1514924013411-cbf25faa35bb"],
                    price_preview=PricePreview(from_total=189.0, from_nightly=94.5, currency="USD"),
                    availability_status="available",
                    top_offers=[
                        Offer(
                            offer_id="provider2:rally_denver:STD",
                            room_type="STD",
                            room_name="Standard Room",
                            total_amount=189.0,
                            nightly_amount=94.5,
                            currency="USD",
                        )
                    ],
                )
            ],
        )

    async def create_booking_request(self, offer_id, guest):
        if offer_id != "sigtrip:The_Rally_Hotel:ASK":
            return BookingResponse(status="failed", error="bad offer")
        return BookingResponse(
            status="payment_required",
            payment_url="https://example.com/pay/123",
            session_expiration="15m",
        )


class HotelWrapperServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_returns_price_and_images(self):
        service = HotelWrapperService(provider=FakeProvider())
        result = await service.search_hotel_offers("denver", "2026-02-11", "2026-02-12")

        self.assertEqual(result["provider"], "sigtrip")
        self.assertGreaterEqual(len(result["hotels"]), 1)
        hotel = result["hotels"][0]
        self.assertEqual(hotel["price_preview"]["from_total"], 199.0)
        self.assertTrue(hotel["thumbnail_url"].startswith("https://"))
        self.assertGreaterEqual(len(hotel["top_offers"]), 1)
        self.assertIn("metadata", result)
        self.assertIn("data_source", result["metadata"])

    async def test_booking_validates_guest_schema(self):
        service = HotelWrapperService(provider=FakeProvider())

        invalid = await service.create_booking_request(
            "sigtrip:The_Rally_Hotel:ASK",
            '{"first_name":"A"}',
        )
        self.assertEqual(invalid["status"], "failed")
        self.assertIn("validation", invalid["error"])

        valid = await service.create_booking_request(
            "sigtrip:The_Rally_Hotel:ASK",
            '{"first_name":"A","last_name":"B","email":"a@b.com","phone":"+1","check_in":"2026-02-11","check_out":"2026-02-12","guests":1}',
        )
        self.assertEqual(valid["status"], "payment_required")

    async def test_search_normalizes_us_date_format(self):
        provider = FakeProvider()
        service = HotelWrapperService(provider=provider)
        await service.search_hotel_offers("denver", "04/10/2026", "04/12/2026", guests=0)
        self.assertEqual(provider.last_search["check_in"], "2026-04-10")
        self.assertEqual(provider.last_search["check_out"], "2026-04-12")
        self.assertEqual(provider.last_search["guests"], 1)

    async def test_search_defaults_dates_when_missing(self):
        provider = FakeProvider()
        service = HotelWrapperService(provider=provider)
        result = await service.search_hotel_offers("denver")
        self.assertRegex(provider.last_search["check_in"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertRegex(provider.last_search["check_out"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertIn("dates", result["metadata"]["defaults_applied"])
        self.assertTrue(result["metadata"]["warnings"])

    async def test_plan_hotel_options_parses_query(self):
        provider = FakeProvider()
        service = HotelWrapperService(provider=provider)
        result = await service.plan_hotel_options("Show me hotels in Denver for 2 guests")
        self.assertEqual(provider.last_search["location"], "Denver")
        self.assertEqual(provider.last_search["guests"], 2)
        self.assertTrue(result["metadata"]["interpreted_from_query"])

    async def test_compare_hotels_returns_ranked_items(self):
        provider = FakeProvider()
        service = HotelWrapperService(provider=provider)
        result = await service.compare_hotels("denver")
        self.assertIn("comparison", result)
        self.assertEqual(len(result["comparison"]), 2)
        self.assertEqual(result["comparison"][0]["rank_by_price"], 1)
        self.assertEqual(result["comparison"][0]["property_id"], "prop_us_denver_rally_hotel")
        self.assertEqual(len(result["comparison"][0]["provider_ids"]), 2)
        self.assertLessEqual(
            result["comparison"][0]["from_total"],
            result["comparison"][1]["from_total"],
        )

    async def test_compare_hotels_can_filter_ids(self):
        provider = FakeProvider()
        service = HotelWrapperService(provider=provider)
        result = await service.compare_hotels("denver", hotel_ids=["sigtrip:The_Rally_Hotel"])
        self.assertEqual(len(result["comparison"]), 1)
        self.assertEqual(result["comparison"][0]["hotel_id"], "sigtrip:The_Rally_Hotel")

    async def test_compare_hotels_from_query_parses_inputs(self):
        provider = FakeProvider()
        service = HotelWrapperService(provider=provider)
        result = await service.compare_hotels_from_query("Compare hotels in Denver for 2 guests")
        self.assertEqual(provider.last_search["location"], "Denver")
        self.assertEqual(provider.last_search["guests"], 2)
        self.assertTrue(result["metadata"]["interpreted_from_query"])


if __name__ == "__main__":
    unittest.main()
