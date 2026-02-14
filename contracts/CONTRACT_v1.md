# Contract v1

This file freezes the public response contract for core MCP tools.

Version: `v1`
Status: active

## Error Envelope (standardized)

All tool failures should return:

```json
{
  "ok": false,
  "error": {
    "code": "STRING_CODE",
    "message": "Human-readable message",
    "retryable": false,
    "details": {}
  }
}
```

## Tool Contracts

## `search_hotel_offers`
- Success: object with `provider`, `query`, `metadata`, `hotels`.
- `metadata.contract_version` must be `v1`.

## `plan_hotel_options`
- Success: same shape as `search_hotel_offers`.
- `metadata.interpreted_from_query` should be `true`.

## `compare_hotels`
- Success: object with `provider`, `query`, `metadata`, `comparison`.
- `metadata.contract_version` must be `v1`.

## `compare_hotels_from_query`
- Success: same shape as `compare_hotels`.
- `metadata.interpreted_from_query` should be `true`.

## `create_booking_request`
- Success: booking object with `status="payment_required"` and `payment_url`.
- Failure: standardized error envelope.

## `cancel_booking`
- Success states: `cancelled`, `pending`, `unsupported`, `failed`.
- Must return structured response even when upstream does not support cancellation.
- If upstream requires fields not provided by client, return standardized error envelope with:
  - `error.code = "MISSING_CANCELLATION_FIELDS"`
  - `error.details.required_fields`
  - `error.details.next_action`

## `get_booking_status`
- Success states: `confirmed`, `cancelled`, `pending`, `unknown`, `unsupported`.
- Must return `unsupported` when upstream does not expose a booking-status tool.

## Startup/Env Validation
- Runtime validates provider env configuration.
- In `APP_ENV=prod`, missing provider config raises startup error.
- In non-prod, readiness endpoint surfaces issues.
