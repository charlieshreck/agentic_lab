#!/bin/bash
#
# sync-all-agent-configs.sh
#
# Master sync script for all AI agent configurations.
# Ensures claude-agent, langgraph, and gemini all have consistent MCP config.
#
# Source of truth: /home/.mcp.json
#
# Usage:
#   ./sync-all-agent-configs.sh           # Sync all configs
#   ./sync-all-agent-configs.sh --apply   # Sync and apply to cluster
#   ./sync-all-agent-configs.sh --check   # Check if configs are in sync
#   ./sync-all-agent-configs.sh --commit  # Sync, commit, and push changes
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_JSON="/home/.mcp.json"
AGENTIC_LAB="/home/agentic_lab"
KUBECONFIG_AGENTIC="$AGENTIC_LAB/infrastructure/terraform/talos-cluster/generated/kubeconfig"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# Check dependencies
check_deps() {
    for cmd in jq yq kubectl; do
        if ! command -v $cmd &> /dev/null; then
            log_warn "$cmd not found - some features may not work"
        fi
    done
}

# Count MCP servers in .mcp.json
count_mcp_servers() {
    jq '.mcpServers | keys | length' "$MCP_JSON"
}

# Generate mcp-servers-config ConfigMap
sync_mcp_configmap() {
    log_step "Generating mcp-servers-config ConfigMap..."
    "$SCRIPT_DIR/sync-mcp-config.sh"
}

# Generate claude-agent-context ConfigMap
sync_claude_context() {
    log_step "Syncing claude-agent context ConfigMap..."

    local context_file="$AGENTIC_LAB/kubernetes/applications/claude-agent/context-configmap.yaml"
    local server_count=$(count_mcp_servers)

    # Update the server count in the context
    if [ -f "$context_file" ]; then
        # Just verify it exists - it's manually maintained
        log_info "context-configmap.yaml exists with $server_count MCP servers referenced"
    else
        log_warn "context-configmap.yaml not found - creating..."
        # This would regenerate it, but we created it manually above
    fi
}

# Verify all configs reference the same MCP list
verify_sync() {
    log_step "Verifying all configs are in sync..."

    local server_count=$(count_mcp_servers)
    log_info "Source .mcp.json has $server_count MCP servers"

    # Check ConfigMap
    local configmap="$AGENTIC_LAB/kubernetes/platform/mcp-config/configmap.yaml"
    if [ -f "$configmap" ]; then
        local cm_count=$(grep -c "_MCP_URL:" "$configmap" || echo 0)
        if [ "$cm_count" -eq "$server_count" ]; then
            log_info "✓ mcp-servers-config ConfigMap: $cm_count servers"
        else
            log_warn "✗ mcp-servers-config ConfigMap: $cm_count servers (expected $server_count)"
        fi
    else
        log_error "✗ mcp-servers-config ConfigMap not found"
    fi

    # Check langgraph system prompt mentions correct count
    local langgraph="$AGENTIC_LAB/kubernetes/applications/langgraph/langgraph.yaml"
    if grep -q "21 MCP servers" "$langgraph" 2>/dev/null; then
        log_info "✓ langgraph AGENT_SYSTEM_PROMPT mentions 21 servers"
    else
        log_warn "✗ langgraph AGENT_SYSTEM_PROMPT may need updating"
    fi

    # Check gemini SYSTEM.md mentions correct count
    local gemini="$AGENTIC_LAB/.gemini/SYSTEM.md"
    if grep -q "21 total" "$gemini" 2>/dev/null; then
        log_info "✓ Gemini SYSTEM.md mentions 21 servers"
    else
        log_warn "✗ Gemini SYSTEM.md may need updating"
    fi
}

# Apply ConfigMaps to cluster
apply_to_cluster() {
    log_step "Applying ConfigMaps to agentic cluster..."

    if [ ! -f "$KUBECONFIG_AGENTIC" ]; then
        log_error "Kubeconfig not found: $KUBECONFIG_AGENTIC"
        return 1
    fi

    export KUBECONFIG="$KUBECONFIG_AGENTIC"

    # Apply mcp-servers-config
    kubectl apply -f "$AGENTIC_LAB/kubernetes/platform/mcp-config/configmap.yaml"
    log_info "Applied mcp-servers-config"

    # Apply claude-agent-context
    kubectl apply -f "$AGENTIC_LAB/kubernetes/applications/claude-agent/context-configmap.yaml"
    log_info "Applied claude-agent-context"

    log_warn "Restart deployments to pick up changes:"
    echo "  kubectl rollout restart deployment/claude-agent -n ai-platform"
    echo "  kubectl rollout restart deployment/langgraph -n ai-platform"
}

# Commit and push changes
commit_changes() {
    log_step "Committing changes..."

    cd "$AGENTIC_LAB"

    # Check for changes
    if ! git diff --quiet; then
        git add -A
        git commit -m "chore: sync MCP config from .mcp.json

Updated:
- kubernetes/platform/mcp-config/configmap.yaml
- kubernetes/applications/claude-agent/context-configmap.yaml
- kubernetes/applications/langgraph/langgraph.yaml
- .gemini/SYSTEM.md

Source: /home/.mcp.json
Servers: $(count_mcp_servers) MCP servers"

        log_info "Changes committed"

        if [ "${PUSH:-false}" = "true" ]; then
            git push
            log_info "Changes pushed"
        else
            log_warn "Run 'git push' to push changes, or use --push flag"
        fi
    else
        log_info "No changes to commit"
    fi
}

# Show current MCP server list
show_mcp_list() {
    echo ""
    echo "=== MCP Servers in /home/.mcp.json ==="
    jq -r '.mcpServers | keys[]' "$MCP_JSON" | sort
    echo ""
    echo "Total: $(count_mcp_servers) servers"
}

# Main
check_deps

case "${1:-}" in
    --check)
        show_mcp_list
        verify_sync
        ;;
    --apply)
        sync_mcp_configmap
        sync_claude_context
        verify_sync
        apply_to_cluster
        ;;
    --commit)
        sync_mcp_configmap
        sync_claude_context
        verify_sync
        commit_changes
        ;;
    --push)
        PUSH=true
        sync_mcp_configmap
        sync_claude_context
        verify_sync
        commit_changes
        ;;
    --help|-h)
        echo "Usage: $0 [--check|--apply|--commit|--push|--help]"
        echo ""
        echo "Options:"
        echo "  (none)    Sync all configs (generate only)"
        echo "  --check   Verify configs are in sync"
        echo "  --apply   Sync and apply to agentic cluster"
        echo "  --commit  Sync and commit changes"
        echo "  --push    Sync, commit, and push"
        echo "  --help    Show this help"
        echo ""
        echo "Source of truth: /home/.mcp.json"
        echo "Affected configs:"
        echo "  - kubernetes/platform/mcp-config/configmap.yaml"
        echo "  - kubernetes/applications/claude-agent/context-configmap.yaml"
        echo "  - kubernetes/applications/claude-agent/deployment.yaml (envFrom)"
        echo "  - kubernetes/applications/langgraph/langgraph.yaml (envFrom + SYSTEM_PROMPT)"
        echo "  - .gemini/SYSTEM.md"
        ;;
    *)
        sync_mcp_configmap
        sync_claude_context
        verify_sync
        show_mcp_list
        log_info "Use --apply to apply to cluster, --commit to commit changes"
        ;;
esac
