# MCP Server Development Guide for Homelab Applications

## Overview

Most homelab applications don't have official MCP servers or Docker-approved images. This guide covers building custom MCP servers using **FastMCP** (Python) to expose your applications to the AI agent layer.

## Architecture Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                    LangGraph Orchestrator                    │
└─────────────────────────┬───────────────────────────────────┘
                          │ MCP Protocol (HTTP/SSE)
┌─────────────────────────▼───────────────────────────────────┐
│                   MCP Gateway (Optional)                     │
│              Aggregates multiple MCP servers                 │
└──┬──────────┬──────────┬──────────┬──────────┬─────────────┘
   │          │          │          │          │
┌──▼──┐   ┌──▼──┐   ┌──▼──┐   ┌──▼──┐   ┌──▼──┐
│ HA  │   │ Arr │   │Plex │   │ NAS │   │Infra│
│ MCP │   │ MCP │   │ MCP │   │ MCP │   │ MCP │
└──┬──┘   └──┬──┘   └──┬──┘   └──┬──┘   └──┬──┘
   │          │          │          │          │
┌──▼──┐   ┌──▼──┐   ┌──▼──┐   ┌──▼──┐   ┌──▼──┐
│Home │   │Sonarr│  │Plex │   │True │   │Prox │
│Asst │   │Radarr│  │ API │   │ NAS │   │ mox │
└─────┘   └─────┘   └─────┘   └─────┘   └─────┘
```

---

## FastMCP Project Structure

```
mcp-servers/
├── base/                          # Shared base image
│   ├── Dockerfile
│   └── requirements-base.txt
├── home-assistant/
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main.py               # MCP server entry
│   │   └── tools/
│   │       ├── lights.py
│   │       ├── climate.py
│   │       └── automation.py
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── k8s/
│       ├── deployment.yaml
│       └── service.yaml
├── arr-suite/
│   ├── src/
│   │   ├── main.py
│   │   └── tools/
│   │       ├── sonarr.py
│   │       ├── radarr.py
│   │       └── prowlarr.py
│   ├── Dockerfile
│   └── k8s/
├── plex/
├── truenas/
├── infrastructure/               # K8s, Docker, Proxmox tools
└── docker-compose.dev.yaml       # Local development
```

---

## Base MCP Server Template

### pyproject.toml
```toml
[project]
name = "homelab-mcp-server"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastmcp>=2.7.0",
    "httpx>=0.28.0",
    "pydantic>=2.11.0",
    "pydantic-settings>=2.9.0",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-asyncio", "ruff"]
```

### Base Dockerfile
```dockerfile
FROM python:3.11-slim AS base

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install uv for fast package management
RUN pip install uv

# Copy and install dependencies
COPY pyproject.toml .
RUN uv sync --no-dev

# Copy source
COPY src/ ./src/

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Run MCP server
EXPOSE 8000
CMD ["uv", "run", "python", "src/main.py"]
```

### Base Server Template (src/main.py)

**IMPORTANT**: All MCP servers MUST follow this standardized pattern that combines:
1. **REST endpoints** - For health checks and context building (langgraph)
2. **MCP protocol** - Mounted at `/mcp` for tool execution

```python
#!/usr/bin/env python3
"""Base MCP server template for homelab applications."""
import os
import logging
from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize MCP server
mcp = FastMCP(
    name="homelab-mcp",
    instructions="""
    MCP server for homelab automation.
    Provide clear, structured responses.
    """
)

# Define your MCP tools here using @mcp.tool() decorator
# Example:
# @mcp.tool()
# async def my_tool(param: str) -> str:
#     """Tool description."""
#     return "result"

# ============================================================================
# REST API (REQUIRED)
# ============================================================================

async def rest_health(request):
    """Health check endpoint - REQUIRED for K8s probes."""
    return JSONResponse({"status": "healthy"})

# Optional: Add REST endpoints for langgraph context building
# These provide quick access to data without MCP protocol overhead
async def rest_api_example(request):
    """REST endpoint for langgraph context."""
    try:
        # Your logic here
        return JSONResponse({"status": "ok", "data": {}})
    except Exception as e:
        logger.error(f"REST api error: {e}")
        return JSONResponse({"status": "error", "error": str(e)}, status_code=500)

# ============================================================================
# MAIN - Starlette App Combining REST + MCP
# ============================================================================

def main():
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting MCP server on port {port}")

    # Define REST routes (MUST include /health)
    rest_routes = [
        Route("/health", rest_health, methods=["GET"]),
        # Add optional REST endpoints for langgraph context:
        # Route("/api/example", rest_api_example, methods=["GET"]),
    ]

    # Get MCP app with HTTP transport
    mcp_app = mcp.http_app()

    # Combine REST routes + MCP into single Starlette app
    # IMPORTANT: Mount at "/" so FastMCP's /mcp endpoint is accessible
    # IMPORTANT: Pass lifespan to initialize FastMCP's task group
    app = Starlette(
        routes=rest_routes + [Mount("/", app=mcp_app)],
        lifespan=mcp_app.lifespan
    )

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
```

### Why This Pattern?

The standardized pattern solves several problems:

1. **Health checks**: Kubernetes needs `/health` for liveness/readiness probes
2. **LangGraph context**: The orchestrator can quickly fetch data via REST `/api/*` endpoints without MCP overhead
3. **MCP tools**: Full MCP protocol available at `/mcp` for tool execution
4. **Single port**: Everything runs on port 8000, simplifying networking

### Endpoint Summary

| Endpoint | Purpose |
|----------|---------|
| `/health` | K8s probes, returns `{"status": "healthy"}` |
| `/api/*` | REST endpoints for context building (optional) |
| `/mcp` | MCP protocol (SSE transport) |

### Dependencies

All MCP servers require these packages in their pip install:
```
fastmcp httpx uvicorn starlette
```

For servers using Pydantic models, add `pydantic` as well.

---

## Example: Home Assistant MCP Server

### src/tools/home_assistant.py
```python
"""Home Assistant MCP tools."""
import os
import httpx
from fastmcp import FastMCP
from pydantic import BaseModel
from typing import Optional, List

# Configuration from environment
HA_URL = os.environ.get("HA_URL", "http://homeassistant.local:8123")
HA_TOKEN = os.environ.get("HA_TOKEN")

mcp = FastMCP(name="home-assistant-mcp")

class LightState(BaseModel):
    entity_id: str
    state: str
    brightness: Optional[int] = None
    color_temp: Optional[int] = None

async def _ha_request(method: str, endpoint: str, data: dict = None) -> dict:
    """Make authenticated request to Home Assistant API."""
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method,
            f"{HA_URL}/api/{endpoint}",
            headers={"Authorization": f"Bearer {HA_TOKEN}"},
            json=data,
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()

@mcp.tool()
async def list_lights() -> List[LightState]:
    """List all light entities and their current state."""
    states = await _ha_request("GET", "states")
    lights = [
        LightState(
            entity_id=s["entity_id"],
            state=s["state"],
            brightness=s.get("attributes", {}).get("brightness"),
            color_temp=s.get("attributes", {}).get("color_temp")
        )
        for s in states
        if s["entity_id"].startswith("light.")
    ]
    return lights

@mcp.tool()
async def turn_on_light(
    entity_id: str,
    brightness: Optional[int] = None,
    color_temp: Optional[int] = None
) -> str:
    """
    Turn on a light with optional brightness and color temperature.
    
    Args:
        entity_id: The light entity ID (e.g., light.living_room)
        brightness: Brightness level 0-255
        color_temp: Color temperature in mireds
    """
    data = {"entity_id": entity_id}
    if brightness is not None:
        data["brightness"] = brightness
    if color_temp is not None:
        data["color_temp"] = color_temp
    
    await _ha_request("POST", "services/light/turn_on", data)
    return f"Turned on {entity_id}"

@mcp.tool()
async def turn_off_light(entity_id: str) -> str:
    """Turn off a light."""
    await _ha_request("POST", "services/light/turn_off", {"entity_id": entity_id})
    return f"Turned off {entity_id}"

@mcp.tool()
async def run_automation(automation_id: str) -> str:
    """
    Trigger a Home Assistant automation.
    
    Args:
        automation_id: The automation entity ID
    """
    await _ha_request("POST", "services/automation/trigger", {"entity_id": automation_id})
    return f"Triggered automation {automation_id}"

@mcp.tool()
async def get_sensor_state(entity_id: str) -> dict:
    """Get the current state of any sensor or entity."""
    states = await _ha_request("GET", f"states/{entity_id}")
    return {
        "entity_id": states["entity_id"],
        "state": states["state"],
        "attributes": states.get("attributes", {}),
        "last_changed": states.get("last_changed")
    }

@mcp.tool()
async def set_climate(
    entity_id: str,
    temperature: float,
    hvac_mode: Optional[str] = None
) -> str:
    """
    Set climate/thermostat temperature.
    
    Args:
        entity_id: Climate entity ID
        temperature: Target temperature
        hvac_mode: Optional mode (heat, cool, auto, off)
    """
    data = {"entity_id": entity_id, "temperature": temperature}
    if hvac_mode:
        data["hvac_mode"] = hvac_mode
    
    await _ha_request("POST", "services/climate/set_temperature", data)
    return f"Set {entity_id} to {temperature}°"
```

---

## Example: *arr Suite MCP Server

### src/tools/arr_suite.py
```python
"""Sonarr/Radarr/Prowlarr MCP tools."""
import os
import httpx
from fastmcp import FastMCP
from typing import List, Optional
from pydantic import BaseModel

mcp = FastMCP(name="arr-suite-mcp")

# Configuration
SONARR_URL = os.environ.get("SONARR_URL", "http://sonarr:8989")
SONARR_API_KEY = os.environ.get("SONARR_API_KEY")
RADARR_URL = os.environ.get("RADARR_URL", "http://radarr:7878")
RADARR_API_KEY = os.environ.get("RADARR_API_KEY")

class MediaItem(BaseModel):
    id: int
    title: str
    year: Optional[int]
    status: str
    monitored: bool
    size_on_disk: int

async def _arr_request(
    base_url: str, 
    api_key: str, 
    endpoint: str,
    method: str = "GET",
    data: dict = None
) -> dict:
    """Make request to *arr API."""
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method,
            f"{base_url}/api/v3/{endpoint}",
            headers={"X-Api-Key": api_key},
            json=data,
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()

# Sonarr Tools
@mcp.tool()
async def list_tv_shows(monitored_only: bool = True) -> List[MediaItem]:
    """List all TV shows in Sonarr."""
    shows = await _arr_request(SONARR_URL, SONARR_API_KEY, "series")
    result = [
        MediaItem(
            id=s["id"],
            title=s["title"],
            year=s.get("year"),
            status=s["status"],
            monitored=s["monitored"],
            size_on_disk=s.get("sizeOnDisk", 0)
        )
        for s in shows
        if not monitored_only or s["monitored"]
    ]
    return result

@mcp.tool()
async def search_tv_show(query: str) -> List[dict]:
    """Search for a TV show to add to Sonarr."""
    results = await _arr_request(
        SONARR_URL, SONARR_API_KEY, 
        f"series/lookup?term={query}"
    )
    return [
        {
            "tvdbId": r.get("tvdbId"),
            "title": r["title"],
            "year": r.get("year"),
            "overview": r.get("overview", "")[:200]
        }
        for r in results[:5]
    ]

@mcp.tool()
async def trigger_show_search(series_id: int) -> str:
    """Trigger a search for missing episodes of a show."""
    await _arr_request(
        SONARR_URL, SONARR_API_KEY,
        "command",
        method="POST",
        data={"name": "SeriesSearch", "seriesId": series_id}
    )
    return f"Triggered search for series {series_id}"

# Radarr Tools
@mcp.tool()
async def list_movies(monitored_only: bool = True) -> List[MediaItem]:
    """List all movies in Radarr."""
    movies = await _arr_request(RADARR_URL, RADARR_API_KEY, "movie")
    result = [
        MediaItem(
            id=m["id"],
            title=m["title"],
            year=m.get("year"),
            status="downloaded" if m.get("hasFile") else "missing",
            monitored=m["monitored"],
            size_on_disk=m.get("sizeOnDisk", 0)
        )
        for m in movies
        if not monitored_only or m["monitored"]
    ]
    return result

@mcp.tool()
async def search_movie(query: str) -> List[dict]:
    """Search for a movie to add to Radarr."""
    results = await _arr_request(
        RADARR_URL, RADARR_API_KEY,
        f"movie/lookup?term={query}"
    )
    return [
        {
            "tmdbId": r.get("tmdbId"),
            "title": r["title"],
            "year": r.get("year"),
            "overview": r.get("overview", "")[:200]
        }
        for r in results[:5]
    ]

@mcp.tool()
async def add_movie(
    tmdb_id: int,
    quality_profile_id: int = 1,
    root_folder_path: str = "/movies"
) -> str:
    """
    Add a movie to Radarr.
    
    Args:
        tmdb_id: TMDB ID from search results
        quality_profile_id: Quality profile (1=Any, adjust as needed)
        root_folder_path: Where to store the movie
    """
    # First lookup the movie details
    results = await _arr_request(
        RADARR_URL, RADARR_API_KEY,
        f"movie/lookup/tmdb?tmdbId={tmdb_id}"
    )
    
    movie_data = results
    movie_data["qualityProfileId"] = quality_profile_id
    movie_data["rootFolderPath"] = root_folder_path
    movie_data["monitored"] = True
    movie_data["addOptions"] = {"searchForMovie": True}
    
    await _arr_request(
        RADARR_URL, RADARR_API_KEY,
        "movie",
        method="POST",
        data=movie_data
    )
    return f"Added movie: {movie_data['title']}"

@mcp.tool()
async def get_download_queue() -> List[dict]:
    """Get current download queue from Sonarr and Radarr."""
    sonarr_queue = await _arr_request(SONARR_URL, SONARR_API_KEY, "queue")
    radarr_queue = await _arr_request(RADARR_URL, RADARR_API_KEY, "queue")
    
    combined = []
    for item in sonarr_queue.get("records", []):
        combined.append({
            "type": "tv",
            "title": item.get("title"),
            "status": item.get("status"),
            "progress": item.get("sizeleft", 0) / max(item.get("size", 1), 1) * 100
        })
    for item in radarr_queue.get("records", []):
        combined.append({
            "type": "movie",
            "title": item.get("title"),
            "status": item.get("status"),
            "progress": item.get("sizeleft", 0) / max(item.get("size", 1), 1) * 100
        })
    return combined
```

---

## Example: Infrastructure MCP Server

### src/tools/infrastructure.py
```python
"""Infrastructure management MCP tools (K8s, Docker)."""
import os
import subprocess
import json
from fastmcp import FastMCP
from typing import List, Optional

mcp = FastMCP(name="infrastructure-mcp")

@mcp.tool()
async def kubectl_get_pods(namespace: str = "default") -> List[dict]:
    """Get pods in a Kubernetes namespace."""
    result = subprocess.run(
        ["kubectl", "get", "pods", "-n", namespace, "-o", "json"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return {"error": result.stderr}
    
    data = json.loads(result.stdout)
    return [
        {
            "name": pod["metadata"]["name"],
            "status": pod["status"]["phase"],
            "ready": all(
                c.get("ready", False) 
                for c in pod["status"].get("containerStatuses", [])
            ),
            "restarts": sum(
                c.get("restartCount", 0)
                for c in pod["status"].get("containerStatuses", [])
            )
        }
        for pod in data.get("items", [])
    ]

@mcp.tool()
async def kubectl_logs(
    pod_name: str,
    namespace: str = "default",
    tail_lines: int = 50
) -> str:
    """Get logs from a Kubernetes pod."""
    result = subprocess.run(
        ["kubectl", "logs", pod_name, "-n", namespace, f"--tail={tail_lines}"],
        capture_output=True, text=True
    )
    return result.stdout if result.returncode == 0 else result.stderr

@mcp.tool()
async def kubectl_restart_deployment(
    deployment_name: str,
    namespace: str = "default"
) -> str:
    """Restart a Kubernetes deployment."""
    result = subprocess.run(
        ["kubectl", "rollout", "restart", "deployment", deployment_name, "-n", namespace],
        capture_output=True, text=True
    )
    return result.stdout if result.returncode == 0 else result.stderr

@mcp.tool()
async def argocd_sync_app(app_name: str) -> str:
    """Trigger ArgoCD sync for an application."""
    result = subprocess.run(
        ["argocd", "app", "sync", app_name, "--prune"],
        capture_output=True, text=True
    )
    return result.stdout if result.returncode == 0 else result.stderr

@mcp.tool()
async def get_node_resources() -> dict:
    """Get resource usage across Kubernetes nodes."""
    result = subprocess.run(
        ["kubectl", "top", "nodes", "--no-headers"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return {"error": result.stderr}
    
    nodes = []
    for line in result.stdout.strip().split("\n"):
        parts = line.split()
        if len(parts) >= 5:
            nodes.append({
                "name": parts[0],
                "cpu_usage": parts[1],
                "cpu_percent": parts[2],
                "memory_usage": parts[3],
                "memory_percent": parts[4]
            })
    return {"nodes": nodes}
```

---

## Kubernetes Deployment

### k8s/mcp-server-deployment.yaml
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: home-assistant-mcp
  namespace: ai-platform
  labels:
    app: home-assistant-mcp
spec:
  replicas: 1
  selector:
    matchLabels:
      app: home-assistant-mcp
  template:
    metadata:
      labels:
        app: home-assistant-mcp
    spec:
      containers:
        - name: mcp-server
          image: ghcr.io/yourrepo/home-assistant-mcp:latest
          ports:
            - containerPort: 8000
              name: http
          env:
            - name: PORT
              value: "8000"
            - name: MCP_TRANSPORT
              value: "sse"
            - name: HA_URL
              value: "http://home-assistant.home-automation:8123"
            - name: HA_TOKEN
              valueFrom:
                secretKeyRef:
                  name: mcp-secrets
                  key: ha-token
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "256Mi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: home-assistant-mcp
  namespace: ai-platform
spec:
  selector:
    app: home-assistant-mcp
  ports:
    - port: 8000
      targetPort: 8000
      name: http
```

### k8s/mcp-secrets.yaml (SOPS encrypted)
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mcp-secrets
  namespace: ai-platform
type: Opaque
stringData:
  ha-token: ENC[AES256_GCM,data:...,type:str]
  sonarr-api-key: ENC[AES256_GCM,data:...,type:str]
  radarr-api-key: ENC[AES256_GCM,data:...,type:str]
```

---

## CI/CD Pipeline (GitHub Actions)

### .github/workflows/mcp-server.yaml
```yaml
name: Build MCP Servers

on:
  push:
    paths:
      - 'mcp-servers/**'
    branches: [main]
  pull_request:
    paths:
      - 'mcp-servers/**'

jobs:
  build:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        server: [home-assistant, arr-suite, plex, infrastructure]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3
      
      - name: Login to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      
      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: ./mcp-servers/${{ matrix.server }}
          push: ${{ github.event_name != 'pull_request' }}
          tags: |
            ghcr.io/${{ github.repository }}/mcp-${{ matrix.server }}:latest
            ghcr.io/${{ github.repository }}/mcp-${{ matrix.server }}:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  test:
    runs-on: ubuntu-latest
    needs: build
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install uv
          uv sync --all-extras
      
      - name: Run tests
        run: pytest mcp-servers/*/tests/
```

---

## LangGraph Integration

### Connecting MCP servers to LangGraph router
```python
"""LangGraph node for MCP tool execution."""
from fastmcp import Client
from langgraph.graph import StateGraph
from typing import TypedDict, List

class AgentState(TypedDict):
    messages: List[dict]
    mcp_results: List[dict]
    current_tool: str

# MCP client configuration
MCP_SERVERS = {
    "home_assistant": {
        "transport": "sse",
        "url": "http://home-assistant-mcp:8000/mcp"
    },
    "arr_suite": {
        "transport": "sse",
        "url": "http://arr-suite-mcp:8000/mcp"
    },
    "infrastructure": {
        "transport": "sse",
        "url": "http://infrastructure-mcp:8000/mcp"
    }
}

async def execute_mcp_tool(state: AgentState) -> AgentState:
    """Execute tool via appropriate MCP server."""
    tool_request = state["messages"][-1]
    server_name = route_to_mcp_server(tool_request)
    
    config = MCP_SERVERS[server_name]
    client = Client(config)
    
    async with client:
        result = await client.call_tool(
            tool_request["tool_name"],
            tool_request["tool_args"]
        )
    
    state["mcp_results"].append({
        "server": server_name,
        "tool": tool_request["tool_name"],
        "result": result
    })
    return state

def route_to_mcp_server(request: dict) -> str:
    """Route tool call to appropriate MCP server."""
    tool_name = request.get("tool_name", "")
    
    if tool_name.startswith(("light_", "climate_", "automation_")):
        return "home_assistant"
    elif tool_name.startswith(("movie_", "tv_", "download_")):
        return "arr_suite"
    elif tool_name.startswith(("kubectl_", "argocd_")):
        return "infrastructure"
    else:
        return "home_assistant"  # Default
```

---

## Your Homelab MCP Server Inventory

Based on your setup, here are the MCP servers to build:

| Server | Applications | Priority | Complexity |
|--------|-------------|----------|------------|
| **home-assistant-mcp** | HA, Tasmota switches, Google Home | High | Medium |
| **arr-suite-mcp** | Sonarr, Radarr, Prowlarr, SABnzbd | High | Medium |
| **plex-mcp** | Plex, Tautulli | Medium | Low |
| **truenas-mcp** | TrueNAS API, ZFS datasets | Medium | Medium |
| **infrastructure-mcp** | K8s, ArgoCD, MinIO | High | High |
| **network-mcp** | Cloudflare tunnels, DNS | Low | Medium |

### Existing Community Servers to Evaluate

- **berrykuipers/radarr-sonarr** - May cover basic *arr needs
- **mcp-server-docker** - Docker management
- **mcp-server-kubernetes** - K8s management

Check https://www.pulsemcp.com/ and https://smithery.ai/ for community servers before building custom.
