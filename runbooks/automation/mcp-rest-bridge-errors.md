# MCP REST Bridge Errors (HTTP 500 on /api/call)

## Overview

The MCP REST bridge (`/api/call`) allows A2A agents (KAO LangGraph, a2a-orchestrator) to call
MCP tools via simple HTTP POST instead of the MCP SSE protocol. Tool call failures appear as
HTTP 500 errors on the MCP service.

## Alert Pattern

- **Source**: Coroot — errors on `observability-mcp` (or any `*-mcp`) service
- **Symptom**: HTTP 500 responses on `/api/call` endpoint
- **Log message**: `Tool call failed: <tool_name> - <pydantic ValidationError>`

## Common Root Causes

### 1. Wrong parameter names

The tool API changed but the caller wasn't updated.

```
ValidationError: app_id
  Missing required argument [type=missing_argument, ...]
```

**Coroot tool mapping** (as of 2026-02):
| Tool | Required Param | Notes |
|------|----------------|-------|
| `coroot_get_service_metrics` | `app_id: str` | Format: `cluster:namespace:Kind:name` |
| `coroot_get_service_dependencies` | `app_id: str` | Same format |
| `coroot_get_recent_anomalies` | `hours: int = 24` (optional) | No `service_id` or `period` |

**Fix**: Update the caller (usually `langgraph.yaml` in KAO) to use correct param names.

### 2. Incorrect `{"params": {...}}` wrapping

Tools that use **flat kwargs** (most coroot, gatus, alerts tools) must receive flat arguments:
```json
{"tool": "coroot_get_recent_anomalies", "arguments": {"hours": 6}}
```

Tools that use **Pydantic model params** (proxmox, cloudflare, truenas, grafana) need wrapping:
```json
{"tool": "proxmox_list_vms", "arguments": {"params": {"node": "ruapehu"}}}
```

The REST bridge auto-detects and retries the other format, but it only handles one direction
of mismatch gracefully. Always prefer sending the correct format.

**Symptoms of wrong wrapping**:
```
params
  Unexpected keyword argument [type=unexpected_keyword_argument, input_value={...}, ...]
```

### 3. Tool implementation missing parameter

The tool definition is missing a parameter that callers need. This requires **fixing the MCP tool source code**, not the caller.

```
hours
  Unexpected keyword argument [type=unexpected_keyword_argument, input_value=24, input_type=int]
```

At first glance this looks like an extra/unsupported parameter (see #4 below), but the key distinction is:
- **Tool is wrong**: callers like KAO LangGraph are using a parameter that makes semantic sense (`hours` for time filtering) but the tool was never implemented to support it
- **Fix**: Add the parameter to the tool function in `/home/mcp-servers/domains/<domain>/src/<domain>_mcp/tools/*.py`, commit, push — CI rebuilds the image, ArgoCD syncs and restarts the pod

**Example (incident #153)**: `list_recent_events` in `knowledge-mcp` didn't accept `hours`, but KAO was calling it with `hours=24`. Fixed by adding `hours: Optional[int] = None` to the tool.

### 4. Extra unsupported parameters

Passing a param the tool no longer accepts:
```
period
  Extra inputs are not permitted [type=extra_forbidden, ...]
```

**Fix**: Remove the extra parameter from the call.

## Diagnosis Steps

```bash
# 1. Check pod logs for REST bridge errors
kubectl -n ai-platform logs deploy/<mcp-name> --tail=200 | grep "Tool call failed"

# 2. Find the caller — search for the failing tool name in LangGraph or other callers
grep -n "<tool_name>" /home/agentic_lab/kubernetes/applications/langgraph/langgraph.yaml

# 3. Check current tool signature in source
grep -A5 "def <tool_name>" /home/mcp-servers/domains/<domain>/src/<domain>_mcp/tools/*.py
```

## Fix Locations

| Caller | File |
|--------|------|
| KAO LangGraph | `/home/agentic_lab/kubernetes/applications/langgraph/langgraph.yaml` |
| a2a-orchestrator | `/home/agentic_lab/kubernetes/applications/a2a/` |
| alerting-pipeline | `/home/agentic_lab/kubernetes/applications/alerting-pipeline/` |

## Commit Workflow

```bash
# Fix the YAML file, then:
git -C /home/agentic_lab add kubernetes/applications/langgraph/langgraph.yaml
git -C /home/agentic_lab commit -m "fix: correct tool params in KAO LangGraph agent"
git -C /home/agentic_lab push origin main

# Update parent repo pointer
git -C /home add agentic_lab
git -C /home commit -m "chore: update agentic_lab submodule"
git -C /home push origin main
```

ArgoCD auto-syncs the ConfigMap change. The LangGraph deployment reads its Python code from the
ConfigMap, so restart the deployment after ArgoCD syncs:

```bash
# Via MCP tool (after ArgoCD sync completes)
kubectl_restart_deployment namespace=ai-platform name=langgraph cluster=agentic
```

## Incident History

- **2026-02-22**: Incident #153 — `knowledge-mcp` reporting 28 errors. Root causes:
  1. `list_recent_events` tool missing `hours` parameter — KAO was calling with `hours=24`
     causing Pydantic validation failure → 500 on `/api/call`. Fixed by adding `hours: Optional[int]`
     to the tool in `qdrant.py`.
  2. SilverBullet sync webhook returning 500 due to stale cached auth cookie returning 401.
     Fixed by clearing `_session_cookie = None` on 401 in `silverbullet.py` to force re-auth
     on next attempt.
  Both fixes committed to `mcp-servers` repo and deployed via ArgoCD/CI.

- **2026-02-22**: Incident #144 — coroot tools in KAO were using old `service_id` param
  (should be `app_id`) and wrapping flat-kwargs tools in `{"params": {...}}`. Fixed by
  updating `langgraph.yaml` calls to `coroot_get_recent_anomalies`, `coroot_get_service_metrics`,
  and `coroot_get_service_dependencies`.
