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

# Multi-cluster kubeconfig paths (matches infrastructure-mcp pattern)
KUBECONFIGS: dict[str, str | None] = {
    "agentic": None,  # In-cluster service account
    "prod": os.environ.get("KUBECONFIG_PROD", "/kubeconfigs/prod/kubeconfig"),
    "monit": os.environ.get("KUBECONFIG_MONIT", "/kubeconfigs/monit/kubeconfig"),
}

# Direct API access (cross-cluster)
GATUS_URL = os.environ.get("GATUS_URL", "http://gatus.monit.kernow.io")

# Multi-host Proxmox configuration (standalone hosts, not clustered)
PROXMOX_HOSTS = {
    "ruapehu": {
        "url": os.environ.get("PROXMOX_RUAPEHU_URL", "https://10.10.0.10:8006"),
        "token_id": os.environ.get("PROXMOX_RUAPEHU_TOKEN_ID", ""),
        "token_secret": os.environ.get("PROXMOX_RUAPEHU_TOKEN_SECRET", ""),
    },
    "carrick": {
        "url": os.environ.get("PROXMOX_CARRICK_URL", "https://10.30.0.10:8006"),
        "token_id": os.environ.get("PROXMOX_CARRICK_TOKEN_ID", ""),
        "token_secret": os.environ.get("PROXMOX_CARRICK_TOKEN_SECRET", ""),
    },
}

# Multi-instance TrueNAS configuration
TRUENAS_INSTANCES = {
    "hdd": {
        "url": os.environ.get("TRUENAS_HDD_URL", "https://truenas.hdd.kernow.io"),
        "api_key": os.environ.get("TRUENAS_HDD_API_KEY", ""),
    },
    "media": {
        "url": os.environ.get("TRUENAS_MEDIA_URL", "https://truenas.kernow.io"),
        "api_key": os.environ.get("TRUENAS_MEDIA_API_KEY", ""),
    },
}

# Node labels managed by lifecycle (Mark & Sweep)
SYNCABLE_LABELS = [
    "Pod", "Deployment", "StatefulSet", "DaemonSet", "Service", "Ingress",
    "PersistentVolumeClaim",
    "ArgoApp", "VM", "Host", "UptimeMonitor", "Alert",
    "StoragePool", "Dataset", "Share", "StorageAlert", "App", "DNSRecord",
    "AccessPoint", "Switch", "NetworkDevice", "Dashboard",
]
