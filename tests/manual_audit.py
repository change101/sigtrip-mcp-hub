import asyncio
import httpx
import os
import json
import datetime
from dotenv import load_dotenv

load_dotenv()

# CONFIGURATION
UPSTREAM_URL = "https://hotel.sigtrip.ai/mcp"
API_KEY = os.getenv("SIGTRIP_API_KEY")
if API_KEY == "None" or API_KEY == "": API_KEY = None

# HELPER: Get dynamic dates so calls don't fail
today = datetime.date.today()
tomorrow = today + datetime.timedelta(days=1)
next_day = today + datetime.timedelta(days=2)
check_in = tomorrow.strftime("%Y-%m-%d")
check_out = next_day.strftime("%Y-%m-%d")

async def call_raw(tool_name: str, args: dict):
    print(f"\n--- TESTING TOOL: {tool_name} ---")
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream, application/json"
    }
    if API_KEY:
        headers["apikey"] = API_KEY
        headers["Authorization"] = f"Bearer {API_KEY}"

    payload = {
        "jsonrpc": "2.0", 
        "id": 1, 
        "method": "tools/call", 
        "params": {
            "name": tool_name,
            "arguments": args
        }
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(UPSTREAM_URL, json=payload, headers=headers, timeout=20.0)
            print(f"Status Code: {resp.status_code}")
            
            # RAW DUMP
            raw_text = resp.text
            print("RAW BODY START ==>")
            print(raw_text[:1000] + "..." if len(raw_text) > 1000 else raw_text)
            print("<== RAW BODY END")

            # ATTEMPT PARSE (Just to help us read)
            if "data:" in raw_text:
                for line in raw_text.splitlines():
                    if line.startswith("data:"):
                        clean = line.replace("data: ", "").strip()
                        if clean and clean != "[DONE]":
                            try:
                                data = json.loads(clean)
                                content = data.get("result", {}).get("content", [])
                                if content:
                                    text_content = content[0].get("text")
                                    print(f"\n[PARSED CONTENT]:\n{text_content}")
                            except:
                                pass
        except Exception as e:
            print(f"CRITICAL FAIL: {e}")

async def main():
    print(f"Target: {UPSTREAM_URL}")
    print(f"Dates: {check_in} to {check_out}")

    # 1. DISCOVERY (We know this returns text)
    await call_raw("get_rooms", {
        "hotelName": "The Rally Hotel",
        "adults": 1
    })

    # 2. PRICING (Does this return JSON or Text?)
    await call_raw("get_prices", {
        "hotelName": "The Rally Hotel",
        "arrivalDate": check_in,
        "departureDate": check_out,
        "adults": 1
    })

    # 3. BOOKING (Let's see the Stripe link format)
    # We use fake data, expecting a valid link or a specific error
    await call_raw("setup_booking", {
        "hotelName": "The Rally Hotel",
        "roomType": "Standard", # Guessing a type, might error but will show schema
        "firstName": "Test",
        "lastName": "User",
        "email": "test@example.com",
        "phoneNumber": "+15555555555",
        "checkIn": check_in,
        "checkOut": check_out,
        "guests": 1
    })

    # 4. IMAGES (Does this return a list of URLs?)
    await call_raw("view_room_gallery", {
        "hotelName": "The Rally Hotel",
        "expectedCount": 3,
        "rooms": [{"roomType": "Standard", "title": "Standard Room"}]
    })

if __name__ == "__main__":
    asyncio.run(main())