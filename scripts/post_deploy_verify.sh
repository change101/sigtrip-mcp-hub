#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-}"
if [[ -z "$BASE_URL" ]]; then
  echo "Usage: $0 <base_url>"
  echo "Example: $0 https://your-app.onrender.com"
  exit 1
fi

if [[ "$BASE_URL" == */ ]]; then
  BASE_URL="${BASE_URL%/}"
fi

echo "[1/4] Checking health endpoint..."
curl -fsS "$BASE_URL/healthz" | sed -n '1,120p'

echo "[2/4] Checking readiness endpoint..."
curl -fsS "$BASE_URL/readyz" | sed -n '1,200p'

echo "[3/4] Checking SSE endpoint reachability..."
# Expect either a 200 or protocol-level response body, depending on proxy behavior
curl -i -sS "$BASE_URL/sse" | sed -n '1,40p'

echo "[4/4] Manual MCP verification required in Inspector:"
echo "  - Connect SSE: $BASE_URL/sse"
echo "  - Run tools/list"
echo "  - Run plan_hotel_options query=\"Show me hotels in Denver\""
echo "  - Run compare_hotels_from_query query=\"Compare hotels in Denver for 2 guests\""

echo "Done."
