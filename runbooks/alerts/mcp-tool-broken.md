# McpToolBroken

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | McpToolBroken |
| **Severity** | Warning |
| **Source** | error-hunter canary checks / PrometheusRule (MCP up metric) |
| **Clusters Affected** | Agentic (all MCP servers run in ai-platform namespace) |

## Description

This alert fires when an MCP domain server tool fails validation, returns an error, or is unreachable. The error-hunter validates each MCP server by calling canary tools — not just checking HTTP health, but verifying the tool can actually call its backend API.

Common failure modes:
- **Validation errors**: Tool argument schema mismatch (e.g., REST bridge auto-wrapping issue)
- **Backend connectivity**: MCP server can't reach its backend API (Coroot, Grafana, etc.)
- **Auth failures**: Expired or invalid API tokens from Infisical
- **Tool code bugs**: Python exceptions in tool implementation

## Quick Diagnosis

### 1. Check MCP server health

```
# Via MCP tool (preferred)
mcp__observability__gatus_get_endpoint_status()
# Look for MCP server endpoints

# Direct health check
curl http://<mcp-name>-mcp.ai-platform.svc.cluster.local:8000/health
```

### 2. Check MCP server logs

```
mcp__infrastructure__kubectl_logs(
    pod_selector="app=<mcp-name>-mcp",
    namespace="ai-platform",
    cluster="agentic",
    tail_lines=50
)
```

### 3. Test the specific tool via REST bridge

```bash
curl -s -X POST http://<mcp-name>-mcp:8000/api/call \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $A2A_API_TOKEN" \
  -d '{"tool": "<tool_name>", "arguments": {}}'
```

### 4. Check MCP pod status

```
mcp__infrastructure__kubectl_get_pods(namespace="ai-platform", cluster="agentic")
```

## Common Causes

### 1. REST Bridge Auto-Wrapping False Positive

**Symptoms:**
- Error contains "Unexpected keyword argument" and "params"
- Tool works when called directly via MCP protocol but fails via REST bridge
- Error like: `1 validation error for call[tool_name]\nparams\n  Unexpected keyword argument`

**Verification:**
- Check if the tool uses simple keyword arguments (not Pydantic model)
- Test via MCP protocol directly (Claude Code MCP tools)

**Resolution:**
- Fix the `_call_tool` auto-retry logic in `mcp-servers/shared/kernow_mcp_common/base.py`
- The condition should only trigger for tools that genuinely expect a `params` Pydantic model wrapper
- Rebuild and redeploy the affected MCP server image

### 2. Backend API Unreachable

**Symptoms:**
- Error contains "Connection refused" or "timeout"
- Health endpoint returns 200 but tool calls fail

**Verification:**
```
# Check if the backend service is running
mcp__infrastructure__kubectl_get_pods(namespace="monitoring", cluster="monit")
# For observability-mcp backends (Coroot, Grafana, etc.)
```

**Resolution:**
- Verify backend service is running
- Check network connectivity from agentic cluster to backend
- Verify DNS resolution (CoreDNS config)

### 3. Expired/Invalid API Tokens

**Symptoms:**
- Error contains "401" or "403" or "Unauthorized"
- Tool was working before and suddenly failed

**Verification:**
```
# Check Infisical secrets for the MCP domain
mcp__infrastructure__list_secrets(path="/<domain>/<service>")
```

**Resolution:**
- Rotate the API token in Infisical
- Restart the MCP deployment to pick up new secrets:
  `kubectl rollout restart deployment/<mcp-name>-mcp -n ai-platform` (via GitOps or direct)

### 4. FastMCP Version Incompatibility

**Symptoms:**
- Tool validation errors after MCP server image rebuild
- Errors mentioning argument types or schema validation

**Verification:**
- Check `pyproject.toml` for FastMCP version constraint
- Check deployed image version vs source

**Resolution:**
- Pin FastMCP version in `pyproject.toml` if needed
- Test locally before deploying: `cd domains/<name> && uv run python -m <name>_mcp.server`

## Resolution Steps

### Step 1: Identify the broken tool and MCP domain

Check error-hunter findings or alert details for the specific tool name and MCP domain.

### Step 2: Check MCP server logs

```
mcp__infrastructure__kubectl_logs(
    pod_selector="app=<mcp-name>-mcp",
    namespace="ai-platform",
    cluster="agentic",
    tail_lines=100
)
```

### Step 3: Test the tool directly

Call the tool via Claude Code MCP tools to see if it works through the MCP protocol (bypassing REST bridge).

### Step 4: Fix the issue

- If REST bridge issue: fix in `mcp-servers/shared/kernow_mcp_common/base.py`
- If backend issue: fix backend connectivity
- If auth issue: rotate tokens in Infisical
- If code bug: fix in `mcp-servers/domains/<domain>/src/<domain>_mcp/tools/<tool>.py`

### Step 5: Rebuild and deploy

```bash
# Push fix to git
git -C /home/mcp-servers add <files>
git -C /home/mcp-servers commit -m "fix: <description>"
git -C /home/mcp-servers push origin main

# CI builds new image, ArgoCD syncs, restart if ConfigMap-based
```

### Step 6: Verify fix

```bash
# Test via REST bridge
curl -s -X POST http://<mcp-name>-mcp:8000/api/call \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $A2A_API_TOKEN" \
  -d '{"tool": "<tool_name>", "arguments": {}}'
```

## Prevention

1. **Test tools locally** before deploying changes
2. **Pin FastMCP version** to avoid breaking changes
3. **Monitor REST bridge logs** for auto-retry warnings
4. **Keep canary tools in error-hunter** up to date with tool schema changes
5. **Use Gatus** to monitor MCP health endpoints

## MCP Server Reference

| Domain | Source | Key Backends |
|--------|--------|-------------|
| observability | mcp-servers/domains/observability/ | Coroot, Grafana, VictoriaMetrics, AlertManager, Gatus, ntopng |
| infrastructure | mcp-servers/domains/infrastructure/ | K8s, ArgoCD, Proxmox, TrueNAS, Cloudflare, OPNsense, Caddy, Infisical |
| knowledge | mcp-servers/domains/knowledge/ | Qdrant, Neo4j, Outline, SilverBullet |
| home | mcp-servers/domains/home/ | Home Assistant, Tasmota, UniFi, AdGuard |
| media | mcp-servers/domains/media/ | Plex, Sonarr, Radarr, Prowlarr, Overseerr, Tautulli |
| external | mcp-servers/domains/external/ | SearXNG, GitHub, Reddit, Wikipedia, Playwright |

## Related Alerts

- `McpToolBroken` (PrometheusRule) — MCP server process down
- `KubeDeploymentRolloutStuck` — MCP deployment not progressing
- `HomelabPodCrashLooping` — MCP pod restart loop
