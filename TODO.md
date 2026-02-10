# TODO

Prioritized backlog for production readiness and end-user UI enablement.

## P0 - Before End-User UI

1. Freeze API response contracts for UI consumption.
- What: Finalize stable response fields for `search_hotel_offers`, `compare_hotels`, `plan_hotel_options`, and `compare_hotels_from_query`.
- Why: UI and Aggregator need non-breaking payloads to avoid regressions.

2. Add explicit health/readiness endpoints and runtime checks.
- What: Expose readiness/liveness signal and include upstream connectivity diagnostics in metadata when possible.
- Why: UI/aggregator reliability depends on graceful failure handling.

3. Add structured error envelope across all tools.
- What: Standardize error shape (`code`, `message`, `retryable`, `details`) and apply consistently.
- Why: UI can render deterministic error states and recovery hints.

4. Add production security basics.
- What: API auth strategy (service-to-service token), rate limiting, and request logging/redaction.
- Why: Public exposure requires abuse and secret-safety controls.

## P1 - Real DB/DT (Data Tier)

5. Implement real Property Master DB and mapping tables.
- What:
  - Create persistent tables (or equivalent data store):
    - `properties` (canonical static hotel profile)
    - `provider_property_mappings` (provider hotel id -> canonical property id)
    - `property_aliases` (name/address aliases)
    - `mapping_review_queue` (ambiguous matches for manual review)
  - Add repository layer and swap `src/property_master.py` from in-memory static data to DB-backed reads.
  - Keep fallback behavior if DB is unavailable.
- Why:
  - In-memory mappings do not scale and cannot support curation workflows.
  - Multi-provider dedupe quality depends on persistent identity mapping.
  - Enables operational tooling (manual corrections, audits, and history).

6. Add mapping confidence + provenance tracking.
- What: Persist match method (`provider_id_map`, `name_city_match`, `manual`) and confidence scores.
- Why: Essential for trust, debugging, and safe auto-merge behavior across providers.

## P1 - Multi-Provider Readiness

7. Add provider registry and routing layer.
- What: Register multiple provider adapters and aggregate offers per canonical property.
- Why: Current design is provider-ready; this operationalizes it for >1 upstream MCP.

8. Add cross-provider offer ranking policy.
- What: Ranking by total price, cancellation terms, and availability confidence.
- Why: Comparison should be deterministic and business-aligned.

## P2 - Observability and Operations

9. Add metrics and tracing.
- What: Request latency, upstream error rates, fallback rates, and mapping miss rate.
- Why: Needed for production SLOs and debugging provider incidents.

10. Add deployment runbooks.
- What: Environment matrix, rollout process, rollback steps, and incident checklist.
- Why: Reduces deployment risk and support time.

## P2 - UI Enablement

11. Create UI integration contract examples.
- What: Provide sample payload fixtures and UI field mapping docs for card/search/compare/booking views.
- Why: Speeds frontend integration and avoids interpretation drift.

12. Add smoke tests for UI-critical paths.
- What: End-to-end checks for search -> compare -> booking handoff.
- Why: Prevents regressions on the exact user journey.
