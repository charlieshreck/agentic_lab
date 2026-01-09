# MCP Server Remediation Plan

## Executive Summary

Validation of all 14 MCP servers revealed significant inconsistencies in implementation patterns, missing health endpoints, and broken connectivity. The agentic bot (langgraph) expects REST API endpoints but most MCPs only expose MCP protocol.

## Validation Results

### Server Status Matrix

| MCP Server | MCP Protocol | REST API | /health | Status | Root Cause |
|------------|--------------|----------|---------|--------|------------|
| adguard-mcp | ✅ `mcp.http_app()` | ❌ None | ❌ 404 | Partial | Missing REST wrappers |
| arr-suite-mcp | ✅ `mcp.run(sse)` | ❌ None | ❌ 404 | Partial | Missing REST wrappers |
| cloudflare-mcp | ✅ `mcp.http_app()` | ❌ None | ❌ 404 | Partial | Missing REST wrappers |
| coroot-mcp | ❌ **Not started** | ⚠️ `/health` only | ✅ 200 | **Broken** | Runs FastAPI, no MCP |
| home-assistant-mcp | ✅ `mcp.run(sse)` | ❌ None | ❌ 404 | Partial | Missing REST wrappers |
| homepage-mcp | ✅ `mcp.http_app()` | ❌ None | ❌ 404 | Partial | Missing REST wrappers |
| infisical-mcp | ✅ `mcp.http_app()` | ❌ None | ❌ 404 | Partial | Missing REST wrappers |
| infrastructure-mcp | ❌ **Not started** | ⚠️ `/health`, `/execute` | ✅ 200 | **Broken** | Runs FastAPI, no MCP |
| knowledge-mcp | ✅ `mcp.run(sse)` | ❌ None | ❌ 404 | Partial | Missing REST wrappers |
| netbox-mcp | ✅ `mcp.http_app()` | ❌ None | ❌ 404 | Partial | Missing REST wrappers |
| opnsense-mcp | ✅ `mcp.http_app()` | ❌ None | ❌ 404 | Partial | Missing REST wrappers |
| proxmox-mcp | ✅ `mcp.http_app()` | ❌ None | ❌ 404 | Partial | Missing REST wrappers |
| truenas-mcp | ✅ `mcp.http_app()` | ❌ None | ❌ 404 | Partial | Missing REST wrappers |
| unifi-mcp | ✅ Combined app | ✅ Has routes | ❌ 404* | **Broken** | SSL error to UniFi controller |

*unifi-mcp has `/api/health` but it returns 500 due to SSL connection failure.

### Issue Categories

#### Category A: MCP Protocol Not Started (CRITICAL)
These servers define MCP tools but never start the MCP server:
- **infrastructure-mcp**: `main()` runs `uvicorn.run(http_app)` - only FastAPI, MCP tools inaccessible
- **coroot-mcp**: Same issue - `main()` runs `uvicorn.run(http_app)` - MCP tools inaccessible

#### Category B: Missing REST Wrappers (HIGH)
These servers expose MCP protocol but langgraph calls REST endpoints that don't exist:
- **arr-suite-mcp**: Langgraph needs `/api/shows`, `/api/queue` - only has MCP at `/sse`
- **knowledge-mcp**: Langgraph needs `/documentation`, `/record` - only has MCP at `/sse`
- All others lack REST wrappers for context building

#### Category C: Missing /health Endpoint (MEDIUM)
12 of 14 servers return 404 for `/health`:
- Kubernetes liveness/readiness probes may be failing silently
- No standard health check endpoint

#### Category D: Backend Connectivity Issues (HIGH)
- **unifi-mcp**: SSL TLSv1 error connecting to UniFi controller
  ```
  [SSL: TLSV1_ALERT_INTERNAL_ERROR] tlsv1 alert internal error
  ```

---

## Architecture Pattern (Target State)

All MCP servers should follow the unifi-mcp pattern (when fixed):

```python
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
from fastmcp import FastMCP
import uvicorn

mcp = FastMCP(name="example-mcp")

# MCP Tools
@mcp.tool()
async def example_tool() -> dict:
    """Example tool."""
    return {"result": "ok"}

# REST API wrappers for langgraph context
async def api_health(request):
    return JSONResponse({"status": "ok"})

async def api_data(request):
    # Call the same backend logic as MCP tools
    result = await get_data_internal()
    return JSONResponse({"status": "ok", "data": result})

def main():
    rest_routes = [
        Route("/health", api_health),
        Route("/api/data", api_data),
    ]
    mcp_app = mcp.http_app()
    app = Starlette(routes=rest_routes + [Mount("/mcp", app=mcp_app)])
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
```

---

## Remediation Plan

### Phase 1: Critical Fixes (Infrastructure & Coroot)

#### 1.1 Fix infrastructure-mcp
**Priority**: CRITICAL
**Impact**: Langgraph cannot get cluster context

Changes needed:
1. Combine FastAPI http_app with MCP server
2. Add `/api/cluster` endpoint for langgraph context
3. Keep existing `/execute` endpoint for runbook automation

```python
# Target main() function
def main():
    rest_routes = [
        Route("/health", http_health),
        Route("/api/cluster", api_cluster),  # NEW
        Route("/execute", api_execute),       # Migrate from FastAPI
    ]
    mcp_app = mcp.http_app()
    app = Starlette(routes=rest_routes + [Mount("/mcp", app=mcp_app)])
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

New endpoint needed:
```python
async def api_cluster(request):
    """Get cluster status for langgraph context."""
    pods = await kubectl_get_pods("ai-platform")
    events = await kubectl_get_events("ai-platform", limit=10)
    return JSONResponse({
        "status": "ok",
        "data": {
            "pods": [p.dict() for p in pods],
            "events": events,
            "healthy": all(p.ready for p in pods)
        }
    })
```

#### 1.2 Fix coroot-mcp
**Priority**: CRITICAL
**Impact**: Langgraph cannot get observability context

Same pattern as infrastructure-mcp - combine FastAPI with MCP.

### Phase 2: Fix unifi-mcp SSL Issue

**Priority**: HIGH
**Impact**: Network context unavailable

Root cause: UniFi controller requires specific SSL handling.

Fix in unifi-mcp:
```python
# Current (broken)
async with httpx.AsyncClient() as client:
    response = await client.get(url)

# Fixed
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

async with httpx.AsyncClient(verify=False) as client:
    response = await client.get(url, headers=headers)
```

Note: The code already has `verify=False` but may need explicit SSL context for older TLS.

### Phase 3: Add REST Wrappers to All MCPs

**Priority**: HIGH
**Impact**: Langgraph context building fails

Each MCP needs REST endpoints that mirror key MCP tools:

| MCP Server | REST Endpoints Needed |
|------------|----------------------|
| arr-suite-mcp | `/health`, `/api/shows`, `/api/movies`, `/api/queue` |
| knowledge-mcp | `/health`, `/api/search`, `/api/documentation` |
| home-assistant-mcp | `/health`, `/api/entities`, `/api/lights` |
| netbox-mcp | `/health`, `/api/services`, `/api/devices` |
| proxmox-mcp | `/health`, `/api/nodes`, `/api/vms` |
| truenas-mcp | `/health`, `/api/pools`, `/api/datasets` |
| adguard-mcp | `/health`, `/api/stats`, `/api/status` |
| cloudflare-mcp | `/health`, `/api/zones`, `/api/tunnels` |
| opnsense-mcp | `/health`, `/api/interfaces`, `/api/dhcp` |
| homepage-mcp | `/health`, `/api/services` |
| infisical-mcp | `/health`, `/api/secrets` |

### Phase 4: Standardize All MCPs

Template for consistent implementation:

```python
#!/usr/bin/env python3
"""Template MCP server."""
import os
import logging
from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP(
    name="template-mcp",
    instructions="MCP server for X. Provides tools for Y."
)

# ============================================================================
# INTERNAL HELPERS (shared by MCP tools and REST API)
# ============================================================================

async def _get_data_internal() -> dict:
    """Internal function to get data - used by both MCP and REST."""
    # Implementation here
    return {"items": []}

# ============================================================================
# MCP TOOLS
# ============================================================================

@mcp.tool()
async def get_data() -> dict:
    """Get data via MCP protocol."""
    return await _get_data_internal()

# ============================================================================
# REST API (for langgraph context building)
# ============================================================================

async def rest_health(request):
    """Health check endpoint."""
    return JSONResponse({"status": "healthy"})

async def rest_api_data(request):
    """REST wrapper for get_data."""
    try:
        data = await _get_data_internal()
        return JSONResponse({"status": "ok", "data": data})
    except Exception as e:
        logger.error(f"REST api_data error: {e}")
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)

# ============================================================================
# MAIN
# ============================================================================

def main():
    port = int(os.environ.get("PORT", "8000"))
    logger.info(f"Starting template-mcp on port {port}")

    rest_routes = [
        Route("/health", rest_health),
        Route("/api/data", rest_api_data),
    ]

    mcp_app = mcp.http_app()
    app = Starlette(routes=rest_routes + [Mount("/mcp", app=mcp_app)])
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
```

---

## Implementation Order

| Order | Server | Effort | Impact |
|-------|--------|--------|--------|
| 1 | infrastructure-mcp | Medium | Critical - K8s context |
| 2 | coroot-mcp | Medium | Critical - Observability |
| 3 | unifi-mcp | Low | High - SSL fix only |
| 4 | arr-suite-mcp | Medium | High - Media queries |
| 5 | knowledge-mcp | Medium | High - RAG context |
| 6 | netbox-mcp | Medium | Medium - Service discovery |
| 7 | proxmox-mcp | Medium | Medium - VM context |
| 8 | truenas-mcp | Medium | Medium - Storage context |
| 9 | home-assistant-mcp | Medium | Medium - HA context |
| 10 | adguard-mcp | Low | Low - DNS stats |
| 11 | cloudflare-mcp | Low | Low - DNS/tunnels |
| 12 | opnsense-mcp | Low | Low - Firewall |
| 13 | homepage-mcp | Low | Low - Dashboard |
| 14 | infisical-mcp | Low | Low - Secrets |

---

## Alternative: Update Langgraph to Use MCP Protocol

Instead of adding REST wrappers to all MCPs, langgraph could be updated to use the MCP protocol directly:

```python
from fastmcp import Client

async def build_query_context(prompt: str) -> dict:
    context = {}

    if "sonarr" in prompt.lower():
        async with Client("http://arr-suite-mcp:8000/sse") as client:
            tools = await client.list_tools()
            result = await client.call_tool("list_tv_shows", {})
            context["tv_shows"] = result

    return context
```

**Pros**:
- Less code duplication
- MCPs stay focused on MCP protocol
- Consistent interface

**Cons**:
- Requires langgraph refactor
- MCP protocol has more overhead than REST for simple context fetching

**Recommendation**: Hybrid approach
- Fix critical MCPs (infrastructure, coroot) immediately
- Add `/health` to all MCPs for K8s probes
- Gradually migrate langgraph to use MCP protocol for tool calls
- Keep REST wrappers for high-frequency context building

---

## Files to Modify

```
kubernetes/applications/
├── infrastructure-mcp/
│   └── infrastructure-mcp.yaml    # ConfigMap with fixed main.py
├── coroot-mcp/
│   └── coroot-mcp.yaml           # ConfigMap with fixed main.py
├── unifi-mcp/
│   └── unifi-mcp.yaml            # SSL context fix
├── arr-suite-mcp/
│   └── arr-suite-mcp.yaml        # Add REST wrappers
├── knowledge-mcp/
│   └── knowledge-mcp.yaml        # Add REST wrappers
└── ... (all others)
```

After updating ConfigMaps:
1. Commit to git
2. ArgoCD auto-syncs
3. Pods restart with new code

---

## Success Criteria

After remediation:
- [ ] All MCPs respond 200 to `/health`
- [ ] `infrastructure-mcp /api/cluster` returns cluster state
- [ ] `coroot-mcp` exposes MCP protocol at `/mcp`
- [ ] `unifi-mcp /api/devices` returns device list (no SSL error)
- [ ] Langgraph can build context without 404/500 errors
- [ ] Agentic bot can answer questions about Sonarr, K8s, etc.
