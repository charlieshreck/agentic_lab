"""Configuration loaded from environment variables."""

import os

# Neo4j connection (Bolt driver)
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")

# Consolidated MCP endpoints
MCP_SERVERS = {
    "infrastructure": os.environ.get("INFRASTRUCTURE_MCP_URL", "http://infrastructure-mcp:8000"),
    "knowledge": os.environ.get("KNOWLEDGE_MCP_URL", "http://knowledge-mcp:8000"),
    "observability": os.environ.get("OBSERVABILITY_MCP_URL", "http://observability-mcp:8000"),
    "home": os.environ.get("HOME_MCP_URL", "http://home-mcp:8000"),
    "media": os.environ.get("MEDIA_MCP_URL", "http://media-mcp:8000"),
}

# Multi-cluster configuration
K8S_CLUSTERS = ["agentic", "prod", "monit"]

# Multi-cluster kubeconfig paths (matches infrastructure-mcp pattern)
KUBECONFIGS: dict[str, str | None] = {
    "agentic": None,  # In-cluster service account
    "prod": os.environ.get("KUBECONFIG_PROD", "/kubeconfigs/prod/kubeconfig"),
    "monit": os.environ.get("KUBECONFIG_MONIT", "/kubeconfigs/monit/kubeconfig"),
}

# Direct API access (cross-cluster)
GATUS_URL = os.environ.get("GATUS_URL", "http://gatus.monit.kernow.io")

# Node labels managed by lifecycle (Mark & Sweep)
SYNCABLE_LABELS = [
    "Pod", "Deployment", "StatefulSet", "Service", "Ingress", "PersistentVolumeClaim",
    "ArgoApp", "VM", "Host", "UptimeMonitor", "Alert",
    "StoragePool", "Dataset", "Share", "DNSRecord",
    "AccessPoint", "Switch", "NetworkDevice", "Dashboard",
]
