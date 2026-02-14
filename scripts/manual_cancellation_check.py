import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.client import call_upstream_method

load_dotenv()

CANCEL_CANDIDATES = ["cancel_booking", "cancel_reservation", "cancel_booking_request"]
STATUS_CANDIDATES = ["get_booking_status", "booking_status", "get_reservation_status"]


async def main():
    url = os.getenv("MCP_PROVIDER_SIGTRIP_URL", "https://hotel.sigtrip.ai/mcp")
    key_set = bool(os.getenv("MCP_PROVIDER_SIGTRIP_API_KEY"))
    print(f"Upstream URL: {url}")
    print(f"API key configured: {key_set}")

    payload = await call_upstream_method("tools/list")
    if not isinstance(payload, dict):
        print("Failed to fetch tools/list from upstream.")
        return

    result = payload.get("result", {})
    tools = result.get("tools", []) if isinstance(result, dict) else []
    names = []
    if isinstance(tools, list):
        for item in tools:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                names.append(item["name"])

    print(f"Total tools discovered: {len(names)}")
    if names:
        print("Tools:")
        for name in names:
            print(f"- {name}")

    cancel_supported = [c for c in CANCEL_CANDIDATES if c in names]
    status_supported = [c for c in STATUS_CANDIDATES if c in names]

    print("\nCancellation support:")
    if cancel_supported:
        print(f"SUPPORTED via: {cancel_supported}")
    else:
        print("NOT SUPPORTED by known cancellation tool names")

    print("\nBooking status support:")
    if status_supported:
        print(f"SUPPORTED via: {status_supported}")
    else:
        print("NOT SUPPORTED by known status tool names")


if __name__ == "__main__":
    asyncio.run(main())
