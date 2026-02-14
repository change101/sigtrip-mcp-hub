# SigTrip MCP Wrapper

MCP wrapper server for a configurable upstream MCP (default: `https://hotel.sigtrip.ai/mcp`).

It normalizes Sigtrip's mixed SSE/JSON tool responses into stable hotel-search and booking contracts suitable for AI agents.

## Repository and Access Model

- Repository visibility: private by default (company internal).
- Endpoint visibility: can be public network-reachable, but should be authenticated and rate-limited.
- Users/agents consume the deployed MCP endpoint; they do not need repository access.

## Governance Docs

- License: `/Users/workhard/Desktop/research/mcp/LICENSE`
- Security policy: `/Users/workhard/Desktop/research/mcp/SECURITY.md`
- Privacy notice (draft): `/Users/workhard/Desktop/research/mcp/PRIVACY.md`
- API terms (draft): `/Users/workhard/Desktop/research/mcp/TERMS.md`
- Frozen contract spec: `/Users/workhard/Desktop/research/mcp/contracts/CONTRACT_v1.md`
- Contract fixtures: `/Users/workhard/Desktop/research/mcp/contracts/fixtures/`

Error contract:
- All failures should use standardized envelope: `{ \"ok\": false, \"error\": { \"code\", \"message\", \"retryable\", \"details\" } }`.

## Current Public Tools

- `search_hotel_offers`
  - Returns multiple hotels immediately with:
    - image thumbnail + image list
    - `price_preview` (`from_total`, `from_nightly`, `currency`)
    - top offers (bookable `offer_id`s)
  - `check_in` / `check_out` are optional and accept `YYYY-MM-DD` or `MM/DD/YYYY`
  - if dates are omitted, defaults to tomorrow -> day-after-tomorrow
  - response includes `metadata` with defaults/warnings and data source summary
- `plan_hotel_options`
  - Natural-language entrypoint for user-style requests
  - Example: `"Show me hotels in Denver"` or `"Find hotels in Denver for 2 guests from 2026-03-01 to 2026-03-03"`
- `compare_hotels`
  - Compares hotels by `from_total` price and availability
  - Supports optional `hotel_ids` filtering when user wants side-by-side decisioning
- `compare_hotels_from_query`
  - Natural-language comparison entrypoint
  - Example: `"Compare hotels in Denver for 2 guests"`
- `create_booking_request`
  - Takes `offer_id` + guest JSON and returns payment URL or failure reason
- `cancel_booking`
  - Attempts cancellation by provider booking reference
  - Returns `unsupported` gracefully if upstream provider lacks cancellation capability
  - If upstream requires additional fields (e.g. `reservationId`, `email`, `description`), returns standardized error envelope with `MISSING_CANCELLATION_FIELDS`
- `get_booking_status`
  - Retrieves booking status by provider booking reference
  - Returns `unsupported` gracefully if upstream provider lacks status capability

Deprecated compatibility tools are still available:
- `discover_hotels`
- `get_availability`

## Architecture (Maintainable Layout)

- `src/server.py` MCP tool surface
- `src/service.py` orchestration + schema validation
- `src/providers/sigtrip.py` provider adapter (Sigtrip-specific upstream mapping)
- `src/client.py` resilient upstream caller + parser
- `src/models.py` typed schemas (Pydantic)
- `src/property_master.py` canonical static data + provider mapping table

This split is intentionally provider-ready so additional upstream MCP providers can be added later without changing the public contract.

Canonical identity model:
- `property_id`: stable internal property identity (cross-provider dedupe key)
- `hotel_id`: provider namespaced id (`provider:external_id`) used for routing
- `provider_ids`: list of provider ids mapped to the same canonical property

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set environment values in `.env`:

- `MCP_PROVIDER_SIGTRIP_URL=<upstream mcp url>`
- `MCP_PROVIDER_SIGTRIP_API_KEY=<upstream mcp key>`
- optional `MCP_HOST=0.0.0.0`
- optional `MCP_PORT=8000`
- optional `MCP_STRICT_PROVIDER_CONFIG=true` (force startup failure if provider env is missing)

Scalable naming pattern for future providers:
- `MCP_PROVIDER_<PROVIDER>_URL`
- `MCP_PROVIDER_<PROVIDER>_API_KEY`
Example: `MCP_PROVIDER_EXPEDIA_URL`, `MCP_PROVIDER_EXPEDIA_API_KEY`

## Run

```bash
python -m src.server
```

Docker:

```bash
docker build -t sigtrip-wrapper .
docker run --rm -p 8000:8000 --env-file .env sigtrip-wrapper
```

## Tests

Run unit + service tests:

```bash
python -m unittest discover -s tests -v
```

## Upstream Diagnostics

Use snapshots to record each upstream MCP's supported tools and real responses (including error states).

Run:

```bash
python scripts/upstream_diagnostics_snapshot.py --url-env MCP_PROVIDER_SIGTRIP_URL
```

Optional chained cancellation probe:

```bash
python scripts/upstream_diagnostics_snapshot.py --url-env MCP_PROVIDER_SIGTRIP_URL --run-cancel-chain
```

This attempts: `setup_booking -> extract booking reference -> cancel_booking` and writes:
- `scenarios/chain.setup_booking.json`
- `scenarios/chain.cancel_booking.json`

Folder naming rule (auto-generated from URL env):
- remove `https://` (or `http://`)
- replace `/` with `-`
- replace `.` with `_`

Example:
- `https://hotel.sigtrip.ai/mcp` -> `/Users/workhard/Desktop/research/mcp/upstream_diagnostics/hotel_sigtrip_ai-mcp`

## Before UI Checklist

Before building the end-user web UI, complete these minimum backend gates:

1. Freeze response contracts for search/compare/planning tools.
2. Standardize error envelopes and retryability hints.
3. Add readiness/liveness checks for deployment environments.
4. Add basic auth/rate limits for public endpoint exposure.
5. Confirm API behavior with MCP Inspector on happy + failure paths.
6. Track remaining items in `/Users/workhard/Desktop/research/mcp/TODO.md`.
7. Complete platform launch checklist in `/Users/workhard/Desktop/research/mcp/DEPLOYMENT_CHECKLIST.md`.
8. Use Docker-first platform runbook in `/Users/workhard/Desktop/research/mcp/DEPLOYMENT_CHECKLIST.md` for Railway/Render/Fly.io.

## Ops Endpoints

- `GET /healthz` -> process health
- `GET /readyz` -> config readiness (`MCP_PROVIDER_SIGTRIP_API_KEY`, provider URL presence)

Startup validation behavior:
- `APP_ENV=prod`: missing provider config fails startup.
- non-prod: service starts, but `/readyz` reports issues.

## MCP Inspector Checklist

1. Start server on `http://localhost:8000`.
2. In Inspector, connect via SSE transport.
3. Call `tools/list` and verify `search_hotel_offers`, `plan_hotel_options`, `compare_hotels`, and `compare_hotels_from_query` are present.
4. Call `plan_hotel_options` with:
   - `query="Show me hotels in Denver"`
5. Call `search_hotel_offers` with:
   - `location=denver`
   - valid `check_in/check_out`
   - `guests=1`
6. Verify each hotel includes:
   - `thumbnail_url`
   - `price_preview.from_total`
   - `top_offers[*].offer_id`
7. Call `compare_hotels` with:
   - `location=denver`
   - optional `hotel_ids=["sigtrip:The_Rally_Hotel"]`
8. Call `compare_hotels_from_query` with:
   - `query="Compare hotels in Denver for 2 guests"`
9. Call `create_booking_request` with one returned `offer_id` and valid `guest_details` JSON.
10. Call `cancel_booking` with:
   - `provider_booking_ref=<provider booking reference>`
11. Call `get_booking_status` with:
   - `provider_booking_ref=<provider booking reference>`
12. Validate malformed payload behavior:
   - invalid `guest_details` JSON
   - missing required guest fields
   - invalid `offer_id`

## FAQ

### QQ1: Will MCP work without DT/DB?
Yes.

Current behavior without an external DB:
- Dynamic availability/pricing/images still come from upstream MCP (`hotel.sigtrip.ai`).
- Static canonical info currently comes from in-repo Property Master (`src/property_master.py`).
- If a hotel is not in the Property Master mapping, the wrapper falls back to upstream/basic generated values and marks this in metadata.

So the MCP works now without a real DB. A DB is recommended for scale, curation workflow, and multi-provider identity quality.

### QQ2: UI for MCP?
You have two practical UI layers:

1. Protocol/Dev UI: MCP Inspector
- Best for validating tools and payloads.

2. End-user UI (recommended)
- Build a thin web app (Next.js/React or similar) that calls your Aggregator/Brain.
- UI should render hotel cards from wrapper output (`image`, `price_preview`, `top_offers`, `comparison`).
- Suggested first screens:
  - search + filters
  - compare view
  - booking handoff (payment link)

### QQ3: Publish and make accessible?
Recommended production path:

1. Containerize (already done)
2. Push image to registry (GHCR/ECR/GCR)
3. Deploy as public HTTPS endpoint on one:
- Railway / Render / Fly.io (quick)
- Cloud Run / ECS / Kubernetes (scalable)
4. Put reverse proxy + TLS in front
5. Set env vars securely (`MCP_PROVIDER_SIGTRIP_API_KEY`, etc.)
6. Add health checks and basic monitoring

Minimal example flow:

```bash
# build
cd /Users/workhard/Desktop/research/mcp
docker build -t sigtrip-wrapper:latest .

# run locally exposed on 8000
docker run --rm -p 8000:8000 --env-file .env sigtrip-wrapper:latest
```

Then point MCP Inspector (or your Aggregator) to:
- SSE endpoint: `http://<host>:8000/sse`

For internet exposure, replace `<host>` with your deployed HTTPS domain.
