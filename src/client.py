from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx

UPSTREAM_URL = os.getenv("SIGTRIP_UPSTREAM_URL", "https://hotel.sigtrip.ai/mcp")
API_KEY = os.getenv("SIGTRIP_API_KEY") or None
REQUEST_TIMEOUT_SECONDS = float(os.getenv("SIGTRIP_TIMEOUT_SECONDS", "30"))
RETRY_ATTEMPTS = int(os.getenv("SIGTRIP_RETRY_ATTEMPTS", "2"))

logger = logging.getLogger(__name__)


async def call_upstream(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream, application/json",
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
            "arguments": arguments,
        },
    }

    last_error: Exception | None = None
    for attempt in range(RETRY_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = await client.post(UPSTREAM_URL, json=payload, headers=headers)
                response.raise_for_status()
                structured = parse_upstream_response(response.text, response.headers.get("content-type", ""))
                if structured is not None:
                    return structured
                logger.warning("upstream_response_unparsed", extra={"tool": tool_name})
                return None
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            last_error = exc
            logger.warning(
                "upstream_call_failed",
                extra={"tool": tool_name, "attempt": attempt + 1, "error": str(exc)},
            )

    logger.error(
        "upstream_call_exhausted",
        extra={"tool": tool_name, "attempts": RETRY_ATTEMPTS + 1, "error": str(last_error)},
    )
    return None


def parse_upstream_response(response_text: str, content_type: str = "") -> dict[str, Any] | None:
    payload = None
    if "text/event-stream" in content_type or "data:" in response_text:
        payload = _parse_sse_payload(response_text)
    if payload is None:
        payload = _parse_json_payload(response_text)
    if payload is None:
        return None
    return _extract_structured_result(payload)


def _parse_sse_payload(response_text: str) -> dict[str, Any] | None:
    for line in response_text.splitlines():
        if not line.startswith("data:"):
            continue

        clean = line.removeprefix("data:").strip()
        if not clean or clean == "[DONE]":
            continue

        try:
            maybe = json.loads(clean)
            if isinstance(maybe, dict):
                return maybe
        except json.JSONDecodeError:
            continue
    return None


def _parse_json_payload(response_text: str) -> dict[str, Any] | None:
    try:
        raw = json.loads(response_text)
    except json.JSONDecodeError:
        return None
    return raw if isinstance(raw, dict) else None


def _extract_structured_result(payload: dict[str, Any]) -> dict[str, Any] | None:
    result = payload.get("result", {}) if isinstance(payload, dict) else {}

    if isinstance(result, dict) and "structuredContent" in result:
        structured = result["structuredContent"]
        if isinstance(structured, dict):
            return structured

    text_fallback = _extract_text_fallback(result)
    if text_fallback is None:
        return None

    parsed_json = _extract_json_from_text(text_fallback)
    if isinstance(parsed_json, dict):
        return parsed_json

    return {"text_fallback": text_fallback}


def _extract_text_fallback(result: Any) -> str | None:
    if not isinstance(result, dict):
        return None

    content = result.get("content")
    if not isinstance(content, list) or not content:
        return None

    first = content[0]
    if not isinstance(first, dict):
        return None
    text = first.get("text")
    return text if isinstance(text, str) and text.strip() else None


def _extract_json_from_text(text: str) -> dict[str, Any] | list[Any] | None:
    stripped = text.strip()
    if not stripped:
        return None

    for candidate in _json_candidates(stripped):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def _json_candidates(text: str) -> list[str]:
    candidates = [text]

    obj_start = text.find("{")
    obj_end = text.rfind("}")
    if obj_start != -1 and obj_end != -1 and obj_end > obj_start:
        candidates.append(text[obj_start : obj_end + 1])

    arr_start = text.find("[")
    arr_end = text.rfind("]")
    if arr_start != -1 and arr_end != -1 and arr_end > arr_start:
        candidates.append(text[arr_start : arr_end + 1])

    return candidates
