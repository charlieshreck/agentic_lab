# MCP Tool Broken

## Issue Details

| Field | Value |
|-------|-------|
| **Issue Type** | MCP tool invocation failure |
| **Severity** | Warning |
| **Source** | error-hunter sweep / manual testing |
| **Clusters Affected** | Agentic (ai-platform namespace) |

## Description

An MCP domain tool returns an error when called via the REST bridge (`/api/call` endpoint). Common causes include parameter wrapping mismatches, backend API unavailability, or tool code bugs.

## Quick Diagnosis

### 1. Test the tool directly via MCP protocol

```
# Call the tool directly from Claude Code (uses MCP protocol, not REST bridge)
mcp__observability__coroot_get_recent_anomalies(hours=1)
```

If the tool works directly but fails via REST bridge, the issue is in the calling convention.

### 2. Check error-hunter or alerting-pipeline logs

```
mcp__infrastructure__kubectl_logs(namespace="ai-platform", pod_selector="app=error-hunter", tail_lines=100)
```

### 3. Check the MCP server logs

```
mcp__infrastructure__kubectl_logs(namespace="ai-platform", pod_selector="app=observability-mcp", tail_lines=100)
```

## Common Causes

### 1. Params Wrapper Mismatch (REST Bridge)

**Symptoms:**
- Tool works via MCP protocol but fails via `/api/call` REST bridge
- Error: "Unexpected keyword argument" with `params` in the error

**Verification:**
Check how the tool is being called. Tools with **Pydantic model parameters** need wrapping:
```json
{"tool": "proxmox_list_vms", "arguments": {"params": {"host": "ruapehu"}}}
```

Tools with **flat keyword arguments** must NOT be wrapped:
```json
{"tool": "coroot_get_recent_anomalies", "arguments": {"hours": 24}}
```

**Resolution:**
Fix the calling code (error-hunter, alerting-pipeline, etc.) to use the correct format:
- Pydantic model tools (proxmox, cloudflare, truenas): use `{"params": {...}}`
- Flat keyword tools (coroot, gatus, grafana, k8s, etc.): use `{"key": "value"}` directly

**Known tools requiring `params` wrapper:**
- `proxmox_list_vms`, `proxmox_list_containers`, `proxmox_list_nodes`
- `cloudflare_list_zones`
- `truenas_list_pools`

**Known tools using flat args:**
- All `coroot_*` tools
- All `gatus_*` tools
- All `kubectl_*` tools
- All `argocd_*` tools
- `get_scrape_targets`, `query_metrics`, `list_alerts`

**Auto-unwrap fix (2026-02-22):** The REST bridge now auto-detects both directions:
- If a flat-kwargs tool is called with `{"params": {...}}`, the bridge catches `unexpected_keyword_argument` and retries by unwrapping
- If a Pydantic model tool is called without wrapping, the bridge catches `Field required` and retries by wrapping
- This makes the bridge self-healing for parameter format mismatches

### 2. Backend API Unavailable

**Symptoms:**
- Tool fails with connection error or timeout
- Backend service (e.g., Coroot, Grafana) is down

**Verification:**
```
mcp__observability__gatus_get_endpoint_status()
# Check if the relevant backend shows as down
```

**Resolution:**
- Check the backend service is running
- Verify network connectivity between agentic cluster and the backend
- Check DNS resolution (CoreDNS → AdGuard → backend)

### 3. Tool Code Bug

**Symptoms:**
- Tool fails with Python traceback
- Error in parsing response or constructing request

**Verification:**
Check MCP server source code: `/home/mcp-servers/domains/<domain>/src/<domain>_mcp/tools/`

**Resolution:**
- Fix the tool code in the MCP server source
- Rebuild and push the Docker image
- Restart the MCP deployment

## Resolution Steps

### Step 1: Identify the broken tool and error

Check error-hunter findings or test the tool directly.

### Step 2: Determine if it's a calling convention issue

Test via MCP protocol vs REST bridge. If MCP works but REST doesn't, fix the caller.

### Step 3: Fix the code

Edit the relevant file:
- Error-hunter: `/home/agentic_lab/kubernetes/applications/error-hunter/error-hunter.yaml`
- Alerting-pipeline: `/home/agentic_lab/kubernetes/applications/alerting-pipeline/`
- MCP tool: `/home/mcp-servers/domains/<domain>/src/<domain>_mcp/tools/`

### Step 4: Commit and push

```bash
git -C /home/agentic_lab add <files>
git -C /home/agentic_lab commit -m "fix: <description>"
git -C /home/agentic_lab push origin main
```

### Step 5: Verify fix

Wait for ArgoCD sync (or trigger manually), then re-test the tool.

## Prevention

1. **Test tools via both MCP protocol and REST bridge** before deploying
2. **Document parameter style** (Pydantic vs flat) for each tool in the MCP server README
3. **Use canary checks** in error-hunter to catch regressions early
4. **Keep the REST bridge auto-wrapping list accurate** — only wrap tools that actually use Pydantic models
