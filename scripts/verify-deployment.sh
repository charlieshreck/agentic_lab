#!/bin/bash
# Verification script for Gemini + Claude Validator architecture deployment
# Run this after ArgoCD has synced all applications

set -e

echo "=== Agentic Platform Deployment Verification ==="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_service() {
    local name=$1
    local url=$2
    local endpoint=${3:-/health}

    printf "Checking %-25s ... " "${name}"

    response=$(curl -s -o /dev/null -w "%{http_code}" "${url}${endpoint}" 2>/dev/null || echo "000")

    if [ "$response" = "200" ]; then
        echo -e "${GREEN}OK${NC}"
        return 0
    else
        echo -e "${RED}FAIL (HTTP ${response})${NC}"
        return 1
    fi
}

echo "=== Service Health Checks ==="
echo ""

# Core Services
check_service "LiteLLM" "http://litellm:4000" "/health" || true
check_service "Qdrant" "http://qdrant:6333" "/" || true
check_service "LangGraph" "http://langgraph:8000" "/health" || true
check_service "Claude Agent" "http://claude-agent:8000" "/health" || true
check_service "Claude Validator" "http://claude-validator:8000" "/health" || true

# MCP Servers
echo ""
echo "=== MCP Servers ==="
check_service "Knowledge MCP" "http://knowledge-mcp:8000" "/health" || true
check_service "Infrastructure MCP" "http://infrastructure-mcp:8000" "/health" || true
check_service "NetBox MCP" "http://netbox-mcp:8000" "/health" || true
check_service "Coroot MCP" "http://coroot-mcp:8000" "/health" || true

# Matrix Services
echo ""
echo "=== Matrix Services ==="
check_service "Conduit (Matrix)" "http://conduit:8000" "/_matrix/client/versions" || true
check_service "Matrix Bot" "http://matrix-bot:8000" "/health" || true

echo ""
echo "=== Qdrant Collections ==="
collections=$(curl -s "http://qdrant:6333/collections" 2>/dev/null | jq -r '.result.collections[].name' 2>/dev/null || echo "ERROR")

if [ "$collections" = "ERROR" ]; then
    echo -e "${RED}Failed to query Qdrant collections${NC}"
else
    expected="runbooks decisions documentation agent_events tool_knowledge validations capability_gaps skill_gaps user_feedback"
    for col in $expected; do
        if echo "$collections" | grep -q "^${col}$"; then
            echo -e "  ${GREEN}✓${NC} ${col}"
        else
            echo -e "  ${RED}✗${NC} ${col} (missing)"
        fi
    done
fi

echo ""
echo "=== LiteLLM Model Check ==="
models=$(curl -s "http://litellm:4000/v1/models" 2>/dev/null | jq -r '.data[].id' 2>/dev/null || echo "ERROR")

if [ "$models" = "ERROR" ]; then
    echo -e "${RED}Failed to query LiteLLM models${NC}"
else
    echo "Available models:"
    echo "$models" | while read model; do
        echo "  - $model"
    done
fi

echo ""
echo "=== Secrets Check ==="
echo "Verify these secrets exist in Kubernetes:"
echo "  kubectl get secret -n ai-platform gemini-credentials"
echo "  kubectl get secret -n ai-platform claude-validator-credentials"
echo "  kubectl get secret -n ai-platform matrix-bot-credentials"

echo ""
echo "=== Test Alert ==="
echo "To test the end-to-end flow, run:"
echo "  ./scripts/test-alert.sh"
echo ""
echo "=== Verification Complete ==="
