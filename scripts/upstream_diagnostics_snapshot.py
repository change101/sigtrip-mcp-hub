from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.client import call_upstream_method  # noqa: E402


@dataclass
class Scenario:
    key: str
    tool: str
    arguments: dict[str, Any]
    note: str


def sanitize_mcp_name(url: str) -> str:
    cleaned = url.strip()
    if cleaned.startswith("https://"):
        cleaned = cleaned[len("https://") :]
    elif cleaned.startswith("http://"):
        cleaned = cleaned[len("http://") :]
    cleaned = cleaned.replace("/", "-")
    cleaned = cleaned.replace(".", "_")
    cleaned = cleaned.strip("-_")
    return cleaned or "unknown_upstream"


def _extract_booking_reference(payload: Any) -> str | None:
    keys = {"reservationId", "bookingId", "confirmationNumber", "reservation_id", "booking_id"}

    def walk(node: Any) -> str | None:
        if isinstance(node, dict):
            for k, v in node.items():
                if k in keys and isinstance(v, str) and v.strip():
                    return v.strip()
                found = walk(v)
                if found:
                    return found
            return None
        if isinstance(node, list):
            for item in node:
                found = walk(item)
                if found:
                    return found
            return None
        return None

    return walk(payload)


def _default_scenarios() -> list[Scenario]:
    now = datetime.now(timezone.utc)
    check_in = (now.date()).isoformat()
    check_out = (now.date()).isoformat()

    return [
        Scenario(
            key="get_rooms.success",
            tool="get_rooms",
            arguments={"hotelName": "The Rally Hotel", "adults": 1},
            note="Basic room discovery",
        ),
        Scenario(
            key="get_prices.success",
            tool="get_prices",
            arguments={
                "hotelName": "The Rally Hotel",
                "arrivalDate": check_in,
                "departureDate": check_out,
                "adults": 1,
            },
            note="Pricing lookup",
        ),
        Scenario(
            key="setup_booking.invalid_room_type.error",
            tool="setup_booking",
            arguments={
                "hotelName": "The Rally Hotel",
                "roomType": "Standard",
                "firstName": "Test",
                "lastName": "User",
                "email": "test@example.com",
                "phoneNumber": "+15555555555",
                "checkIn": check_in,
                "checkOut": check_out,
                "guests": 1,
            },
            note="Intentional invalid roomType to observe error state",
        ),
        Scenario(
            key="setup_booking.past_date.error",
            tool="setup_booking",
            arguments={
                "hotelName": "The Rally Hotel",
                "roomType": "ASK",
                "firstName": "Test",
                "lastName": "User",
                "email": "test@example.com",
                "phoneNumber": "+15555555555",
                "checkIn": "2020-01-01",
                "checkOut": "2020-01-02",
                "guests": 1,
            },
            note="Past date error behavior",
        ),
        Scenario(
            key="setup_booking.too_many_guests.error",
            tool="setup_booking",
            arguments={
                "hotelName": "The Rally Hotel",
                "roomType": "ASK",
                "firstName": "Test",
                "lastName": "User",
                "email": "test@example.com",
                "phoneNumber": "+15555555555",
                "checkIn": check_in,
                "checkOut": check_out,
                "guests": 99,
            },
            note="Too many guests error behavior",
        ),
        Scenario(
            key="cancel_booking.capability_check",
            tool="cancel_booking",
            arguments={"bookingId": "TEST_BOOKING_REF"},
            note="Checks whether cancellation tool exists/works upstream",
        ),
        Scenario(
            key="get_booking_status.capability_check",
            tool="get_booking_status",
            arguments={"bookingId": "TEST_BOOKING_REF"},
            note="Checks whether booking status tool exists/works upstream",
        ),
    ]


async def run_snapshot(url_env: str, run_cancel_chain: bool = False) -> int:
    load_dotenv()

    upstream_url = os.getenv(url_env)
    if not upstream_url:
        print(f"Missing env var: {url_env}")
        return 2

    folder_name = sanitize_mcp_name(upstream_url)
    base_dir = ROOT / "upstream_diagnostics" / folder_name
    scenarios_dir = base_dir / "scenarios"
    scenarios_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).isoformat()

    tools_raw = await call_upstream_method("tools/list")
    (base_dir / "tools_list.raw.json").write_text(
        json.dumps(
            {
                "captured_at": timestamp,
                "url_env": url_env,
                "upstream_url": upstream_url,
                "payload": tools_raw,
            },
            indent=2,
            ensure_ascii=False,
        )
    )

    tool_names: list[str] = []
    tool_map: dict[str, dict[str, Any]] = {}
    if isinstance(tools_raw, dict):
        result = tools_raw.get("result", {})
        tools = result.get("tools", []) if isinstance(result, dict) else []
        if isinstance(tools, list):
            for tool in tools:
                if isinstance(tool, dict) and isinstance(tool.get("name"), str):
                    tool_names.append(tool["name"])
                    tool_map[tool["name"]] = tool

    (base_dir / "tools_list.names.json").write_text(
        json.dumps(
            {
                "captured_at": timestamp,
                "upstream_url": upstream_url,
                "tool_names": sorted(tool_names),
            },
            indent=2,
            ensure_ascii=False,
        )
    )

    scenarios = _default_scenarios()
    for scenario in scenarios:
        payload = await call_upstream_method(
            "tools/call",
            params={"name": scenario.tool, "arguments": scenario.arguments},
        )
        out = {
            "captured_at": timestamp,
            "upstream_url": upstream_url,
            "scenario": scenario.key,
            "note": scenario.note,
            "request": {
                "method": "tools/call",
                "params": {"name": scenario.tool, "arguments": scenario.arguments},
            },
            "response": payload,
            "tool_list_contains_tool": scenario.tool in tool_names,
        }
        (scenarios_dir / f"{scenario.key}.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))

    if run_cancel_chain:
        diag_email = os.getenv("DIAG_BOOKING_EMAIL", "diagnostics@sigtrip.com")
        diag_phone = os.getenv("DIAG_BOOKING_PHONE", "+15555555555")
        today = datetime.now(timezone.utc).date()
        ci = str(today)
        co = str(today)

        prices_payload = await call_upstream_method(
            "tools/call",
            params={
                "name": "get_prices",
                "arguments": {
                    "hotelName": "The Rally Hotel",
                    "arrivalDate": ci,
                    "departureDate": co,
                    "adults": 1,
                },
            },
        )
        room_type = "ASK"
        try:
            prices = prices_payload["result"]["structuredContent"]["prices"]
            if isinstance(prices, list) and prices and isinstance(prices[0], dict):
                room_type = str(prices[0].get("roomType") or room_type)
        except Exception:
            pass

        setup_payload = await call_upstream_method(
            "tools/call",
            params={
                "name": "setup_booking",
                "arguments": {
                    "hotelName": "The Rally Hotel",
                    "roomType": room_type,
                    "firstName": "Diag",
                    "lastName": "Runner",
                    "email": diag_email,
                    "phoneNumber": diag_phone,
                    "checkIn": ci,
                    "checkOut": co,
                    "guests": 1,
                },
            },
        )
        booking_ref = _extract_booking_reference(setup_payload)
        (scenarios_dir / "chain.setup_booking.json").write_text(
            json.dumps(
                {
                    "captured_at": timestamp,
                    "upstream_url": upstream_url,
                    "scenario": "chain.setup_booking",
                    "note": "Automated chain booking setup before cancellation test",
                    "response": setup_payload,
                    "extracted_booking_reference": booking_ref,
                },
                indent=2,
                ensure_ascii=False,
            )
        )

        cancel_def = tool_map.get("cancel_booking", {})
        input_schema = cancel_def.get("inputSchema", {}) if isinstance(cancel_def, dict) else {}
        required = input_schema.get("required", []) if isinstance(input_schema, dict) else []
        props = input_schema.get("properties", {}) if isinstance(input_schema, dict) else {}

        cancel_args: dict[str, Any] = {}
        if "reservationId" in required or "reservationId" in props:
            cancel_args["reservationId"] = booking_ref
        if "bookingId" in required or "bookingId" in props:
            cancel_args["bookingId"] = booking_ref
        if "email" in required or "email" in props:
            cancel_args["email"] = diag_email
        if "description" in required or "description" in props:
            cancel_args["description"] = "Automated diagnostics cancellation check"

        cancel_payload: Any
        skipped_reason = None
        if "cancel_booking" not in tool_names:
            cancel_payload = None
            skipped_reason = "cancel_booking not exposed by tools/list"
        elif not booking_ref:
            cancel_payload = None
            skipped_reason = "booking reference not found in setup_booking response"
        else:
            cancel_payload = await call_upstream_method(
                "tools/call",
                params={"name": "cancel_booking", "arguments": cancel_args},
            )

        (scenarios_dir / "chain.cancel_booking.json").write_text(
            json.dumps(
                {
                    "captured_at": timestamp,
                    "upstream_url": upstream_url,
                    "scenario": "chain.cancel_booking",
                    "note": "Automated chain cancellation check after setup_booking",
                    "request_arguments": cancel_args,
                    "skipped_reason": skipped_reason,
                    "response": cancel_payload,
                },
                indent=2,
                ensure_ascii=False,
            )
        )

    summary_lines = [
        f"# Upstream Snapshot: {folder_name}",
        "",
        f"- Captured at: `{timestamp}`",
        f"- URL env: `{url_env}`",
        f"- Upstream URL: `{upstream_url}`",
        f"- Total tools detected: `{len(tool_names)}`",
        "",
        "## Tool Names",
    ]
    if tool_names:
        summary_lines.extend([f"- `{name}`" for name in sorted(tool_names)])
    else:
        summary_lines.append("- No tools parsed from tools/list (or upstream call failed).")

    summary_lines.extend(
        [
            "",
            "## Scenario Files",
            "- `scenarios/get_rooms.success.json`",
            "- `scenarios/get_prices.success.json`",
            "- `scenarios/setup_booking.invalid_room_type.error.json`",
            "- `scenarios/setup_booking.past_date.error.json`",
            "- `scenarios/setup_booking.too_many_guests.error.json`",
            "- `scenarios/cancel_booking.capability_check.json`",
            "- `scenarios/get_booking_status.capability_check.json`",
        ]
    )
    if run_cancel_chain:
        summary_lines.extend(
            [
                "- `scenarios/chain.setup_booking.json`",
                "- `scenarios/chain.cancel_booking.json`",
            ]
        )

    (base_dir / "SUMMARY.md").write_text("\n".join(summary_lines) + "\n")

    print(f"Wrote diagnostics snapshot to: {base_dir}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture upstream MCP diagnostics snapshot")
    parser.add_argument(
        "--url-env",
        default="MCP_PROVIDER_SIGTRIP_URL",
        help="Environment variable containing upstream MCP URL",
    )
    parser.add_argument(
        "--run-cancel-chain",
        action="store_true",
        help="Run automated setup_booking -> cancel_booking chain scenario",
    )
    args = parser.parse_args()
    return asyncio.run(run_snapshot(args.url_env, run_cancel_chain=args.run_cancel_chain))


if __name__ == "__main__":
    raise SystemExit(main())
