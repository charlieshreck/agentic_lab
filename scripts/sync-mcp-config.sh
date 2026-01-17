#!/bin/bash
#
# sync-mcp-config.sh
#
# Generates Kubernetes ConfigMap from /home/.mcp.json
# This ensures all agents (claude-agent, langgraph, gemini) use the same MCP config
#
# Usage:
#   ./sync-mcp-config.sh           # Generate ConfigMap YAML
#   ./sync-mcp-config.sh --apply   # Generate and apply to cluster
#   ./sync-mcp-config.sh --env     # Generate shell exports for local use
#
# Source of truth: /home/.mcp.json
# Output: /home/agentic_lab/kubernetes/platform/mcp-config/configmap.yaml
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_JSON="/home/.mcp.json"
OUTPUT_DIR="/home/agentic_lab/kubernetes/platform/mcp-config"
OUTPUT_FILE="${OUTPUT_DIR}/configmap.yaml"
KUBECONFIG_AGENTIC="/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check dependencies
check_deps() {
    if ! command -v jq &> /dev/null; then
        log_error "jq is required but not installed"
        exit 1
    fi
}

# Parse .mcp.json and generate environment variable format
parse_mcp_json() {
    if [[ ! -f "$MCP_JSON" ]]; then
        log_error "MCP config not found: $MCP_JSON"
        exit 1
    fi

    # Extract server names and URLs
    jq -r '.mcpServers | to_entries[] | "\(.key)=\(.value.url)"' "$MCP_JSON" | \
    while IFS='=' read -r name url; do
        # Convert to uppercase and replace - with _
        env_name=$(echo "${name}" | tr '[:lower:]' '[:upper:]' | tr '-' '_')
        # Remove /mcp suffix for base URL
        base_url="${url%/mcp}"
        echo "${env_name}_MCP_URL=${base_url}"
    done
}

# Generate Kubernetes ConfigMap
generate_configmap() {
    mkdir -p "$OUTPUT_DIR"

    log_info "Parsing $MCP_JSON..."

    # Start ConfigMap
    cat > "$OUTPUT_FILE" << 'EOF'
# AUTO-GENERATED - DO NOT EDIT MANUALLY
# Source: /home/.mcp.json
# Generator: /home/agentic_lab/scripts/sync-mcp-config.sh
#
# This ConfigMap provides MCP server URLs for all agents.
# Update .mcp.json and run sync-mcp-config.sh to regenerate.
#
apiVersion: v1
kind: ConfigMap
metadata:
  name: mcp-servers-config
  namespace: ai-platform
  labels:
    app.kubernetes.io/name: mcp-config
    app.kubernetes.io/component: shared-config
  annotations:
    description: "Shared MCP server configuration for all AI agents"
EOF

    # Add generation timestamp
    echo "    generated-at: \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"" >> "$OUTPUT_FILE"
    echo "    source-file: \"/home/.mcp.json\"" >> "$OUTPUT_FILE"
    echo "data:" >> "$OUTPUT_FILE"

    # Parse .mcp.json and add each server
    jq -r '.mcpServers | to_entries[] | "\(.key)|\(.value.url)"' "$MCP_JSON" | \
    while IFS='|' read -r name url; do
        # Convert name to env var format (uppercase, - to _)
        env_name=$(echo "${name}" | tr '[:lower:]' '[:upper:]' | tr '-' '_')
        # Remove /mcp suffix for base URL (services use :8000 internally)
        base_url="${url%/mcp}"
        # Convert external IP to internal service name
        internal_url=$(echo "$base_url" | sed 's|http://10.20.0.40:[0-9]*|http://'"${name}"'-mcp:8000|')

        echo "  ${env_name}_MCP_URL: \"${internal_url}\"" >> "$OUTPUT_FILE"
    done

    # Add the full JSON for reference
    echo "  # Full MCP config as JSON (for dynamic parsing)" >> "$OUTPUT_FILE"
    echo "  MCP_SERVERS_JSON: |" >> "$OUTPUT_FILE"
    jq -c '.mcpServers | to_entries | map({name: .key, url: (.value.url | sub("/mcp$"; "") | sub("http://10.20.0.40:[0-9]+"; "http://\(.key)-mcp:8000"))}) | {servers: .}' "$MCP_JSON" | \
        sed 's/^/    /' >> "$OUTPUT_FILE"

    log_info "Generated: $OUTPUT_FILE"

    # Show server count
    server_count=$(jq '.mcpServers | keys | length' "$MCP_JSON")
    log_info "Configured $server_count MCP servers"
}

# Generate shell exports for local development
generate_env_exports() {
    echo "# MCP Server Environment Variables"
    echo "# Source: $MCP_JSON"
    echo "# Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo ""

    jq -r '.mcpServers | to_entries[] | "\(.key)|\(.value.url)"' "$MCP_JSON" | \
    while IFS='|' read -r name url; do
        env_name=$(echo "${name}" | tr '[:lower:]' '[:upper:]' | tr '-' '_')
        base_url="${url%/mcp}"
        echo "export ${env_name}_MCP_URL=\"${base_url}\""
    done
}

# Apply ConfigMap to cluster
apply_configmap() {
    if [[ ! -f "$OUTPUT_FILE" ]]; then
        log_error "ConfigMap not found. Run without --apply first."
        exit 1
    fi

    log_info "Applying ConfigMap to agentic cluster..."
    KUBECONFIG="$KUBECONFIG_AGENTIC" kubectl apply -f "$OUTPUT_FILE"

    log_info "ConfigMap applied successfully"
    log_warn "Restart deployments to pick up changes:"
    echo "  kubectl rollout restart deployment/claude-agent -n ai-platform"
    echo "  kubectl rollout restart deployment/langgraph -n ai-platform"
}

# Generate list of MCP servers for documentation
generate_mcp_list() {
    echo "## Available MCP Servers"
    echo ""
    echo "| Server | Internal URL | External Port |"
    echo "|--------|--------------|---------------|"

    jq -r '.mcpServers | to_entries[] | "\(.key)|\(.value.url)"' "$MCP_JSON" | \
    while IFS='|' read -r name url; do
        # Extract port from URL
        port=$(echo "$url" | grep -oP ':\K[0-9]+' || echo "N/A")
        internal="http://${name}-mcp:8000"
        echo "| ${name} | ${internal} | ${port} |"
    done
}

# Main
check_deps

case "${1:-}" in
    --apply)
        generate_configmap
        apply_configmap
        ;;
    --env)
        generate_env_exports
        ;;
    --list)
        generate_mcp_list
        ;;
    --help|-h)
        echo "Usage: $0 [--apply|--env|--list|--help]"
        echo ""
        echo "Options:"
        echo "  (none)    Generate ConfigMap YAML only"
        echo "  --apply   Generate and apply to agentic cluster"
        echo "  --env     Output shell export commands"
        echo "  --list    Output markdown table of MCP servers"
        echo "  --help    Show this help"
        ;;
    *)
        generate_configmap
        ;;
esac
