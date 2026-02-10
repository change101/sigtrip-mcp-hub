# AGENTS.md

Project-level instructions for humans and coding agents working in this repository.

## Objective
Build and maintain an MCP wrapper node that:
- connects to upstream MCP providers (currently Sigtrip)
- normalizes responses into stable, provider-agnostic contracts
- supports booking routing via namespaced provider IDs
- is ready for multi-provider extension

## Architecture Rules
- Keep layers separated:
  - `src/server.py`: MCP tool entrypoints only
  - `src/service.py`: orchestration, defaults, normalization, metadata
  - `src/providers/`: provider-specific integrations and mappings
  - `src/models.py`: schema/contracts
  - `src/property_master.py`: canonical property identity and enrichment
- Never put provider-specific parsing logic in `server.py`.
- Preserve namespaced IDs for routing (`provider:external_id`).
- Keep canonical identity (`property_id`) independent from provider IDs.

## Contract Rules
- Public tool contracts should be backward compatible when possible.
- Additive changes are preferred over breaking changes.
- Every search/compare response should include metadata for:
  - normalized/defaulted inputs
  - warnings
  - source transparency (`upstream` vs `fallback`)

## Data Rules
- If static data is missing upstream, fallback to Property Master values.
- If Property Master also lacks data, return safe defaults and mark source in metadata.
- Do not drop provider IDs when deduplicating by canonical `property_id`.

## Testing Rules
- Add/update tests for every behavior change.
- Minimum checks before shipping:
  - `python -m py_compile` on changed modules
  - `python -m unittest discover -s tests -v`
- Prefer deterministic unit tests with fake providers over flaky network tests.

## MCP Inspector Rules
- Verify at least:
  - `tools/list`
  - `search_hotel_offers`
  - `plan_hotel_options`
  - `compare_hotels`
  - `compare_hotels_from_query`
  - `create_booking_request`

## Multi-Provider Readiness
When adding a new provider:
1. create new adapter under `src/providers/`
2. map provider hotel IDs to `property_id`
3. ensure offers keep provider routing IDs
4. add tests covering dedupe and comparison behavior

## Coding Style
- Keep functions small and explicit.
- Prefer typed data models over loose dict manipulation where practical.
- Avoid hidden side effects in provider adapters.
