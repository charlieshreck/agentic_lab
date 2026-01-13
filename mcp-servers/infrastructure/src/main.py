#!/usr/bin/env python3
"""Infrastructure MCP server for Kubernetes and Talos management."""
import os
import subprocess
import json
import logging
from typing import List, Optional
from fastmcp import FastMCP
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp = FastMCP(
    name="infrastructure-mcp",
    instructions="""
    MCP server for infrastructure management.
    Provides tools for Kubernetes cluster operations and Talos node management.
    Use these tools to query cluster state, view logs, and restart deployments.
    """
)


class PodInfo(BaseModel):
    name: str
    namespace: str
    status: str
    ready: bool
    restarts: int


class DeploymentInfo(BaseModel):
    name: str
    namespace: str
    replicas: int
    available: int
    ready: bool


class ServiceInfo(BaseModel):
    name: str
    namespace: str
    type: str
    cluster_ip: str
    ports: List[str]


class EventInfo(BaseModel):
    type: str
    reason: str
    message: str
    object: str
    timestamp: str


def run_kubectl(args: List[str], timeout: int = 30) -> tuple[str, str, int]:
    """Execute kubectl command and return stdout, stderr, returncode."""
    try:
        result = subprocess.run(
            ["kubectl"] + args,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", 1
    except Exception as e:
        return "", str(e), 1


def run_talosctl(args: List[str], node: str = None, timeout: int = 30) -> tuple[str, str, int]:
    """Execute talosctl command and return stdout, stderr, returncode."""
    try:
        cmd = ["talosctl"]
        if node:
            cmd.extend(["-n", node])
        cmd.extend(args)
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", 1
    except Exception as e:
        return "", str(e), 1


@mcp.resource("health://status")
def health_check() -> str:
    """Health check endpoint."""
    return "healthy"


@mcp.tool()
async def kubectl_get_pods(
    namespace: str = "default",
    label_selector: Optional[str] = None
) -> List[PodInfo]:
    """
    Get pods in a Kubernetes namespace.

    Args:
        namespace: Kubernetes namespace (default: "default")
        label_selector: Optional label selector (e.g., "app=nginx")

    Returns:
        List of pod information objects
    """
    args = ["get", "pods", "-n", namespace, "-o", "json"]
    if label_selector:
        args.extend(["-l", label_selector])

    stdout, stderr, returncode = run_kubectl(args)

    if returncode != 0:
        logger.error(f"kubectl get pods failed: {stderr}")
        return []

    try:
        data = json.loads(stdout)
        pods = []
        for pod in data.get("items", []):
            container_statuses = pod.get("status", {}).get("containerStatuses", [])
            pods.append(PodInfo(
                name=pod["metadata"]["name"],
                namespace=pod["metadata"]["namespace"],
                status=pod["status"]["phase"],
                ready=all(c.get("ready", False) for c in container_statuses),
                restarts=sum(c.get("restartCount", 0) for c in container_statuses)
            ))
        return pods
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse kubectl output: {e}")
        return []


@mcp.tool()
async def kubectl_get_deployments(
    namespace: str = "default"
) -> List[DeploymentInfo]:
    """
    Get deployments in a Kubernetes namespace.

    Args:
        namespace: Kubernetes namespace (default: "default")

    Returns:
        List of deployment information objects
    """
    stdout, stderr, returncode = run_kubectl(
        ["get", "deployments", "-n", namespace, "-o", "json"]
    )

    if returncode != 0:
        logger.error(f"kubectl get deployments failed: {stderr}")
        return []

    try:
        data = json.loads(stdout)
        deployments = []
        for deploy in data.get("items", []):
            spec = deploy.get("spec", {})
            status = deploy.get("status", {})
            deployments.append(DeploymentInfo(
                name=deploy["metadata"]["name"],
                namespace=deploy["metadata"]["namespace"],
                replicas=spec.get("replicas", 0),
                available=status.get("availableReplicas", 0),
                ready=status.get("availableReplicas", 0) == spec.get("replicas", 0)
            ))
        return deployments
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse kubectl output: {e}")
        return []


@mcp.tool()
async def kubectl_get_services(
    namespace: str = None
) -> List[ServiceInfo]:
    """
    Get services in a Kubernetes namespace or all namespaces.

    Args:
        namespace: Kubernetes namespace (default: all namespaces)

    Returns:
        List of service information objects
    """
    args = ["get", "services", "-o", "json"]
    if namespace:
        args.extend(["-n", namespace])
    else:
        args.append("-A")

    stdout, stderr, returncode = run_kubectl(args)

    if returncode != 0:
        logger.error(f"kubectl get services failed: {stderr}")
        return []

    try:
        data = json.loads(stdout)
        services = []
        for svc in data.get("items", []):
            spec = svc.get("spec", {})
            ports = []
            for port in spec.get("ports", []):
                port_str = f"{port.get('port', 0)}/{port.get('protocol', 'TCP')}"
                if port.get("nodePort"):
                    port_str += f":{port['nodePort']}"
                ports.append(port_str)
            services.append(ServiceInfo(
                name=svc["metadata"]["name"],
                namespace=svc["metadata"]["namespace"],
                type=spec.get("type", "ClusterIP"),
                cluster_ip=spec.get("clusterIP", "None"),
                ports=ports
            ))
        return services
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse kubectl output: {e}")
        return []


@mcp.tool()
async def kubectl_logs(
    pod_name: str,
    namespace: str = "default",
    container: Optional[str] = None,
    tail_lines: int = 50
) -> str:
    """
    Get logs from a Kubernetes pod.

    Args:
        pod_name: Name of the pod
        namespace: Kubernetes namespace (default: "default")
        container: Optional container name for multi-container pods
        tail_lines: Number of lines to return (default: 50)

    Returns:
        Log output as string
    """
    args = ["logs", pod_name, "-n", namespace, f"--tail={tail_lines}"]
    if container:
        args.extend(["-c", container])

    stdout, stderr, returncode = run_kubectl(args)

    if returncode != 0:
        return f"Error: {stderr}"
    return stdout


@mcp.tool()
async def kubectl_restart_deployment(
    deployment_name: str,
    namespace: str = "default"
) -> str:
    """
    Restart a Kubernetes deployment by triggering a rollout.

    Args:
        deployment_name: Name of the deployment to restart
        namespace: Kubernetes namespace (default: "default")

    Returns:
        Status message
    """
    stdout, stderr, returncode = run_kubectl(
        ["rollout", "restart", "deployment", deployment_name, "-n", namespace]
    )

    if returncode != 0:
        return f"Error: {stderr}"
    return f"Deployment {deployment_name} restart triggered: {stdout}"


@mcp.tool()
async def kubectl_get_events(
    namespace: str = "default",
    field_selector: Optional[str] = None,
    limit: int = 20
) -> List[EventInfo]:
    """
    Get Kubernetes events in a namespace.

    Args:
        namespace: Kubernetes namespace (default: "default")
        field_selector: Optional field selector (e.g., "type=Warning")
        limit: Maximum number of events to return (default: 20)

    Returns:
        List of event information objects
    """
    args = ["get", "events", "-n", namespace, "-o", "json", "--sort-by=.lastTimestamp"]
    if field_selector:
        args.extend(["--field-selector", field_selector])

    stdout, stderr, returncode = run_kubectl(args)

    if returncode != 0:
        logger.error(f"kubectl get events failed: {stderr}")
        return []

    try:
        data = json.loads(stdout)
        events = []
        for event in data.get("items", [])[-limit:]:
            events.append(EventInfo(
                type=event.get("type", "Unknown"),
                reason=event.get("reason", "Unknown"),
                message=event.get("message", "No message"),
                object=event.get("involvedObject", {}).get("name", "Unknown"),
                timestamp=event.get("lastTimestamp", "Unknown")
            ))
        return events
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse kubectl output: {e}")
        return []


@mcp.tool()
async def talosctl_health(node: str = "10.20.0.40") -> dict:
    """
    Check Talos node health.

    Args:
        node: Talos node IP address (default: "10.20.0.40")

    Returns:
        Health check results
    """
    stdout, stderr, returncode = run_talosctl(["health"], node=node, timeout=60)

    if returncode != 0:
        return {"healthy": False, "error": stderr}
    return {"healthy": True, "output": stdout}


@mcp.tool()
async def talosctl_services(node: str = "10.20.0.40") -> List[dict]:
    """
    List Talos services and their status.

    Args:
        node: Talos node IP address (default: "10.20.0.40")

    Returns:
        List of service status objects
    """
    stdout, stderr, returncode = run_talosctl(["services"], node=node)

    if returncode != 0:
        return [{"error": stderr}]

    services = []
    lines = stdout.strip().split("\n")
    for line in lines[1:]:  # Skip header
        parts = line.split()
        if len(parts) >= 3:
            services.append({
                "name": parts[0],
                "state": parts[1],
                "health": parts[2] if len(parts) > 2 else "unknown"
            })
    return services


# HTTP endpoint for runbook executor
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel as PydanticBaseModel

class ExecuteRequest(PydanticBaseModel):
    command: str
    timeout: int = 30

class ExecuteResponse(PydanticBaseModel):
    success: bool
    output: str
    error: Optional[str] = None

http_app = FastAPI()

@http_app.get("/health")
async def http_health():
    return {"status": "healthy"}

@http_app.post("/execute", response_model=ExecuteResponse)
async def execute_command(request: ExecuteRequest):
    """
    Execute a kubectl command for runbook automation.
    Only allows kubectl commands for safety.
    """
    command = request.command.strip()

    # Safety check - only allow kubectl commands
    if not command.startswith("kubectl "):
        raise HTTPException(status_code=400, detail="Only kubectl commands are allowed")

    # Parse command into args
    import shlex
    try:
        parts = shlex.split(command)
        if parts[0] != "kubectl":
            raise HTTPException(status_code=400, detail="Only kubectl commands are allowed")
        kubectl_args = parts[1:]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid command syntax: {e}")

    stdout, stderr, returncode = run_kubectl(kubectl_args, timeout=request.timeout)

    return ExecuteResponse(
        success=(returncode == 0),
        output=stdout,
        error=stderr if returncode != 0 else None
    )


# =============================================================================
# REST API Endpoints (for CronJobs - bypass MCP session protocol)
# =============================================================================

@http_app.get("/api/pods")
async def rest_list_pods(namespace: str = None):
    """REST endpoint for listing all pods - used by graph-sync CronJob."""
    try:
        args = ["get", "pods", "-o", "json"]
        if namespace:
            args.extend(["-n", namespace])
        else:
            args.append("-A")

        stdout, stderr, returncode = run_kubectl(args)

        if returncode != 0:
            logger.error(f"REST list_pods failed: {stderr}")
            return {"error": stderr, "pods": []}

        data = json.loads(stdout)
        pods = []
        for pod in data.get("items", []):
            container_statuses = pod.get("status", {}).get("containerStatuses", [])
            pods.append({
                "name": pod["metadata"]["name"],
                "namespace": pod["metadata"]["namespace"],
                "status": pod["status"]["phase"],
                "ready": all(c.get("ready", False) for c in container_statuses),
                "restarts": sum(c.get("restartCount", 0) for c in container_statuses),
                "node": pod.get("spec", {}).get("nodeName", ""),
                "ip": pod.get("status", {}).get("podIP", "")
            })
        return {"pods": pods}
    except Exception as e:
        logger.error(f"REST list_pods error: {e}")
        return {"error": str(e), "pods": []}


@http_app.get("/api/services")
async def rest_list_services(namespace: str = None):
    """REST endpoint for listing all services - used by graph-sync CronJob."""
    try:
        services = await kubectl_get_services(namespace)
        return {"services": [s.model_dump() for s in services]}
    except Exception as e:
        logger.error(f"REST list_services error: {e}")
        return {"error": str(e), "services": []}


@http_app.get("/api/nodes")
async def rest_list_nodes():
    """REST endpoint for listing all nodes."""
    try:
        stdout, stderr, returncode = run_kubectl(["get", "nodes", "-o", "json"])

        if returncode != 0:
            return {"error": stderr, "nodes": []}

        data = json.loads(stdout)
        nodes = []
        for node in data.get("items", []):
            conditions = {c["type"]: c["status"] for c in node.get("status", {}).get("conditions", [])}
            nodes.append({
                "name": node["metadata"]["name"],
                "ready": conditions.get("Ready") == "True",
                "roles": [k.replace("node-role.kubernetes.io/", "") for k in node["metadata"].get("labels", {}) if k.startswith("node-role.kubernetes.io/")],
                "version": node.get("status", {}).get("nodeInfo", {}).get("kubeletVersion", ""),
                "internal_ip": next((addr["address"] for addr in node.get("status", {}).get("addresses", []) if addr["type"] == "InternalIP"), "")
            })
        return {"nodes": nodes}
    except Exception as e:
        logger.error(f"REST list_nodes error: {e}")
        return {"error": str(e), "nodes": []}


def main():
    port = int(os.environ.get("PORT", "8000"))
    transport = os.environ.get("MCP_TRANSPORT", "sse")

    logger.info(f"Starting infrastructure MCP server on port {port} with {transport} transport")

    if transport == "http":
        from starlette.middleware.cors import CORSMiddleware
        # Use http_app which has the /execute endpoint
        http_app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        )
        # Mount MCP routes on the http_app
        mcp_app = mcp.streamable_http_app()
        http_app.mount("/mcp", mcp_app)
        import uvicorn
        uvicorn.run(http_app, host="0.0.0.0", port=port)
    else:
        mcp.run(transport="sse", host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
