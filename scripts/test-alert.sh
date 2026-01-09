#!/bin/bash
# Test script to verify end-to-end alert flow
# Usage: ./test-alert.sh [severity]
# Severity: warning (default), critical

set -e

SEVERITY="${1:-warning}"
LANGGRAPH_URL="${LANGGRAPH_URL:-http://langgraph:8000}"
ALERT_ID="test-alert-$(date +%s)"

echo "=== Agentic Platform E2E Test ==="
echo "Sending test alert: ${ALERT_ID}"
echo "Severity: ${SEVERITY}"
echo ""

# Send test alert to LangGraph
RESPONSE=$(curl -s -X POST "${LANGGRAPH_URL}/alert" \
  -H "Content-Type: application/json" \
  -d "{
    \"id\": \"${ALERT_ID}\",
    \"alertname\": \"TestPodMemoryHigh\",
    \"severity\": \"${SEVERITY}\",
    \"namespace\": \"test-namespace\",
    \"description\": \"Test alert: Pod test-pod memory usage is at 85%\",
    \"labels\": {
      \"pod\": \"test-pod-abc123\",
      \"service\": \"test-service\",
      \"cluster\": \"agentic\"
    },
    \"annotations\": {
      \"summary\": \"High memory usage detected\",
      \"runbook_url\": \"https://runbooks.example.com/memory-high\"
    }
  }")

echo "Response from LangGraph:"
echo "${RESPONSE}" | jq . 2>/dev/null || echo "${RESPONSE}"
echo ""

# Check status
STATUS=$(echo "${RESPONSE}" | jq -r '.status' 2>/dev/null || echo "unknown")
ASSESSMENT=$(echo "${RESPONSE}" | jq -r '.assessment' 2>/dev/null || echo "{}")

echo "=== Alert Processing Result ==="
echo "Status: ${STATUS}"
echo "Assessment:"
echo "${ASSESSMENT}" | jq . 2>/dev/null || echo "${ASSESSMENT}"
echo ""

# Provide next steps based on status
case "${STATUS}" in
  "pending")
    echo "=== Next Steps ==="
    echo "1. Check Matrix #infrastructure room for approval request"
    echo "2. React with ✅ to approve or ❌ to reject"
    echo "3. Monitor decision outcome in Qdrant"
    ;;
  "approved")
    echo "=== Auto-Approved ==="
    echo "Alert was auto-approved based on runbook confidence."
    echo "Check execution results in Qdrant decisions collection."
    ;;
  "error")
    echo "=== Error ==="
    echo "Alert processing failed. Check LangGraph logs."
    ;;
  *)
    echo "=== Unknown Status ==="
    echo "Received unexpected status: ${STATUS}"
    ;;
esac

echo ""
echo "=== Verification Commands ==="
echo "# Check pending approvals:"
echo "curl -s ${LANGGRAPH_URL}/pending/${ALERT_ID} | jq ."
echo ""
echo "# Check LangGraph status:"
echo "curl -s ${LANGGRAPH_URL}/status | jq ."
echo ""
echo "# Query decisions in Qdrant:"
echo "curl -s -X POST 'http://qdrant:6333/collections/decisions/points/scroll' \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -d '{\"limit\": 5, \"with_payload\": true}' | jq ."
