#!/usr/bin/env python3
"""Coroot MCP server for observability and anomaly detection."""
import os
import logging
from typing import List, Optional
from datetime import datetime, timedelta
import httpx
from fastmcp import FastMCP
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COROOT_URL = os.environ.get("COROOT_URL", "http://coroot.monit-homelab.svc.cluster.local:8080")
COROOT_PROJECT = os.environ.get("COROOT_PROJECT", "default")

mcp = FastMCP(
    name="coroot-mcp",
    instructions="""
    MCP server for Coroot observability platform.
    Provides tools for querying service metrics, anomalies, and dependencies.
    Use these tools to understand system health and investigate incidents.
    """
)


class ServiceMetrics(BaseModel):
    """Service metrics from Coroot."""
    service: str
    namespace: str
    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    latency_p50: Optional[float] = None
    latency_p99: Optional[float] = None
    error_rate: Optional[float] = None
    requests_per_second: Optional[float] = None


class Anomaly(BaseModel):
    """Anomaly detected by Coroot."""
    service: str
    type: str
    severity: str
    message: str
    timestamp: str
    details: Optional[dict] = None


class ServiceDependency(BaseModel):
    """Service dependency information."""
    source: str
    destination: str
    protocol: str
    requests_per_second: Optional[float] = None
    latency_p99: Optional[float] = None
    error_rate: Optional[float] = None


class CorotAlert(BaseModel):
    """Alert from Coroot."""
    id: str
    service: str
    severity: str
    title: str
    message: str
    status: str
    started_at: str
    resolved_at: Optional[str] = None


async def coroot_request(method: str, endpoint: str, **kwargs) -> dict:
    """Make a request to Coroot API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        url = f"{COROOT_URL}/api/project/{COROOT_PROJECT}/{endpoint}"
        try:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Coroot API error: {e}")
            return {"error": str(e)}
        except Exception as e:
            logger.error(f"Coroot request failed: {e}")
            return {"error": str(e)}


@mcp.resource("health://status")
def health_check() -> str:
    """Health check endpoint."""
    return "healthy"


@mcp.tool()
async def get_service_metrics(
    service: str,
    namespace: str = "ai-platform",
    timerange_hours: int = 1
) -> ServiceMetrics:
    """
    Get metrics for a specific service.

    Args:
        service: Service name (e.g., "langgraph", "litellm")
        namespace: Kubernetes namespace (default: "ai-platform")
        timerange_hours: How many hours of data to consider (default: 1)

    Returns:
        Service metrics including CPU, memory, latency, and error rate
    """
    # Calculate time range
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=timerange_hours)

    params = {
        "from": int(start_time.timestamp()),
        "to": int(end_time.timestamp()),
        "service": f"{namespace}/{service}",
    }

    data = await coroot_request("GET", "overview", params=params)

    if "error" in data:
        return ServiceMetrics(
            service=service,
            namespace=namespace,
        )

    # Parse Coroot response - structure may vary
    try:
        # Extract metrics from Coroot's response format
        service_data = data.get("services", {}).get(f"{namespace}/{service}", {})
        metrics = service_data.get("metrics", {})

        return ServiceMetrics(
            service=service,
            namespace=namespace,
            cpu_usage=metrics.get("cpu_usage"),
            memory_usage=metrics.get("memory_usage"),
            latency_p50=metrics.get("latency_p50"),
            latency_p99=metrics.get("latency_p99"),
            error_rate=metrics.get("error_rate"),
            requests_per_second=metrics.get("rps"),
        )
    except Exception as e:
        logger.error(f"Failed to parse service metrics: {e}")
        return ServiceMetrics(service=service, namespace=namespace)


@mcp.tool()
async def get_recent_anomalies(
    hours: int = 24,
    severity: Optional[str] = None
) -> List[Anomaly]:
    """
    Get recent anomalies detected by Coroot.

    Args:
        hours: How many hours to look back (default: 24)
        severity: Filter by severity (critical, warning, info)

    Returns:
        List of anomalies
    """
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=hours)

    params = {
        "from": int(start_time.timestamp()),
        "to": int(end_time.timestamp()),
    }

    data = await coroot_request("GET", "incidents", params=params)

    if "error" in data:
        return []

    anomalies = []
    try:
        for incident in data.get("incidents", []):
            # Filter by severity if specified
            inc_severity = incident.get("severity", "info")
            if severity and inc_severity != severity:
                continue

            anomalies.append(Anomaly(
                service=incident.get("service", "unknown"),
                type=incident.get("type", "unknown"),
                severity=inc_severity,
                message=incident.get("message", ""),
                timestamp=incident.get("timestamp", ""),
                details=incident.get("details"),
            ))
    except Exception as e:
        logger.error(f"Failed to parse anomalies: {e}")

    return anomalies


@mcp.tool()
async def get_service_dependencies(
    service: str,
    namespace: str = "ai-platform"
) -> List[ServiceDependency]:
    """
    Get upstream and downstream dependencies for a service.

    Args:
        service: Service name
        namespace: Kubernetes namespace (default: "ai-platform")

    Returns:
        List of service dependencies
    """
    params = {
        "service": f"{namespace}/{service}",
    }

    data = await coroot_request("GET", "service/dependencies", params=params)

    if "error" in data:
        return []

    dependencies = []
    try:
        for dep in data.get("dependencies", []):
            dependencies.append(ServiceDependency(
                source=dep.get("source", ""),
                destination=dep.get("destination", ""),
                protocol=dep.get("protocol", "unknown"),
                requests_per_second=dep.get("rps"),
                latency_p99=dep.get("latency_p99"),
                error_rate=dep.get("error_rate"),
            ))
    except Exception as e:
        logger.error(f"Failed to parse dependencies: {e}")

    return dependencies


@mcp.tool()
async def get_alerts(
    status: str = "firing"
) -> List[CorotAlert]:
    """
    Get current alerts from Coroot.

    Args:
        status: Alert status filter (firing, resolved, all)

    Returns:
        List of alerts
    """
    data = await coroot_request("GET", "alerts")

    if "error" in data:
        return []

    alerts = []
    try:
        for alert in data.get("alerts", []):
            alert_status = alert.get("status", "unknown")
            if status != "all" and alert_status != status:
                continue

            alerts.append(CorotAlert(
                id=alert.get("id", ""),
                service=alert.get("service", "unknown"),
                severity=alert.get("severity", "info"),
                title=alert.get("title", ""),
                message=alert.get("message", ""),
                status=alert_status,
                started_at=alert.get("started_at", ""),
                resolved_at=alert.get("resolved_at"),
            ))
    except Exception as e:
        logger.error(f"Failed to parse alerts: {e}")

    return alerts


@mcp.tool()
async def get_service_traces(
    service: str,
    namespace: str = "ai-platform",
    limit: int = 10
) -> List[dict]:
    """
    Get recent traces for a service.

    Args:
        service: Service name
        namespace: Kubernetes namespace (default: "ai-platform")
        limit: Maximum number of traces (default: 10)

    Returns:
        List of trace summaries
    """
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(hours=1)

    params = {
        "from": int(start_time.timestamp()),
        "to": int(end_time.timestamp()),
        "service": f"{namespace}/{service}",
        "limit": limit,
    }

    data = await coroot_request("GET", "traces", params=params)

    if "error" in data:
        return []

    try:
        return data.get("traces", [])[:limit]
    except Exception as e:
        logger.error(f"Failed to parse traces: {e}")
        return []


@mcp.tool()
async def get_infrastructure_overview() -> dict:
    """
    Get overview of all services and their health status.

    Returns:
        Dictionary with service health overview
    """
    data = await coroot_request("GET", "overview")

    if "error" in data:
        return {"error": data["error"]}

    try:
        overview = {
            "total_services": len(data.get("services", {})),
            "healthy": 0,
            "warning": 0,
            "critical": 0,
            "services": {}
        }

        for service_name, service_data in data.get("services", {}).items():
            health = service_data.get("health", "unknown")
            if health == "healthy":
                overview["healthy"] += 1
            elif health == "warning":
                overview["warning"] += 1
            elif health == "critical":
                overview["critical"] += 1

            overview["services"][service_name] = {
                "health": health,
                "anomalies": service_data.get("anomaly_count", 0),
            }

        return overview
    except Exception as e:
        logger.error(f"Failed to parse overview: {e}")
        return {"error": str(e)}


def main():
    port = int(os.environ.get("PORT", "8000"))
    transport = os.environ.get("MCP_TRANSPORT", "sse")

    logger.info(f"Starting Coroot MCP server on port {port} with {transport} transport")

    if transport == "http":
        from starlette.middleware.cors import CORSMiddleware
        from fastapi import FastAPI

        app = FastAPI()
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        )

        @app.get("/health")
        async def health():
            return {"status": "healthy"}

        mcp_app = mcp.streamable_http_app()
        app.mount("/mcp", mcp_app)

        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        mcp.run(transport="sse", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
