#!/usr/bin/env bash
# =============================================================================
# EduSim Smoke Test Script
# Boots the Docker Compose stack and tests /api/db/health and /api/rag/search
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

echo "================================================================="
echo "EduSim Stack Smoke Test"
echo "================================================================="

# 1. Export temporary fallback values for required compose variables if not already set
export JWT_SECRET="${JWT_SECRET:-edusim_smoke_test_jwt_secret_key_at_least_32_characters_long}"
export GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:-smoke-test-client-id.apps.googleusercontent.com}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-edusim_secret_password}"

# Cleanup trap on failure or exit
CLEANUP=true
if [[ "${1:-}" == "--no-cleanup" || "${1:-}" == "--keep-running" ]]; then
    CLEANUP=false
fi

cleanup() {
    if [ "$CLEANUP" = true ]; then
        echo ""
        echo "==> Cleaning up Docker Compose services..."
        docker compose down -v --remove-orphans || true
    fi
}
trap cleanup EXIT

# 2. Run docker compose config
echo "==> Validating Docker Compose configuration (docker compose config)..."
docker compose config > /dev/null
echo "✓ Docker Compose configuration is valid."

# 3. Boot the stack
echo "==> Booting EduSim services (postgres, api)..."
docker compose up -d --build postgres api

# 4. Wait for /api/db/health
echo "==> Waiting for backend healthcheck (http://localhost:8001/api/db/health)..."
MAX_ATTEMPTS=60
ATTEMPT=0
HEALTH_OK=false

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    ATTEMPT=$((ATTEMPT + 1))
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/api/db/health 2>/dev/null || echo "000")
    if [ "$HTTP_STATUS" = "200" ]; then
        echo "✓ Healthcheck passed (HTTP 200) after ${ATTEMPT} checks."
        HEALTH_OK=true
        break
    fi
    sleep 2
done

if [ "$HEALTH_OK" != true ]; then
    echo "ERROR: Backend failed to become healthy within $((MAX_ATTEMPTS * 2)) seconds."
    echo "==> Docker compose api logs:"
    docker compose logs api
    exit 1
fi

# 5. Generate a test JWT token for authenticated endpoints
echo "==> Generating student auth token..."
TOKEN=$(docker compose exec -T api python -c "
from app.src.utils.auth import create_access_token
print(create_access_token({'sub': '00000000-0000-0000-0000-000000000001', 'role': 'student'}))
" 2>/dev/null | tr -d '\r\n')

if [ -z "$TOKEN" ]; then
    echo "ERROR: Failed to generate access token inside container."
    docker compose logs api
    exit 1
fi

# 6. Test /api/rag/search endpoint
echo "==> Testing /api/rag/search endpoint..."
SEARCH_PAYLOAD='{"query": "Newton third law of motion", "subject": "physics"}'
SEARCH_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST http://localhost:8001/api/rag/search \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${TOKEN}" \
    -d "${SEARCH_PAYLOAD}")

HTTP_BODY=$(echo "$SEARCH_RESPONSE" | sed '$d')
HTTP_CODE=$(echo "$SEARCH_RESPONSE" | tail -n1)

echo "Response HTTP Status: ${HTTP_CODE}"
echo "Response Body Preview: $(echo "$HTTP_BODY" | head -c 200)..."

if [ "$HTTP_CODE" != "200" ]; then
    echo "ERROR: /api/rag/search failed with status ${HTTP_CODE}: ${HTTP_BODY}"
    docker compose logs api
    exit 1
fi

# Verify chunks returned
CHUNK_COUNT=$(echo "$HTTP_BODY" | grep -o '"chunk_id"' | wc -l || echo "0")
echo "✓ /api/rag/search returned ${CHUNK_COUNT} chunks."

echo ""
echo "================================================================="
echo "✓ ALL SMOKE TESTS PASSED SUCCESSFULLY!"
echo "================================================================="
