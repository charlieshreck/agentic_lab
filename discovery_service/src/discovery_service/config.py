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
        "url": os.environ.get("PROXMOX_RUAPEHU_URL", "https://proxmox.kernow.io"),
        "token_id": os.environ.get("PROXMOX_RUAPEHU_TOKEN_ID", ""),
        "token_secret": os.environ.get("PROXMOX_RUAPEHU_TOKEN_SECRET", ""),
    },
    "carrick": {
        "url": os.environ.get("PROXMOX_CARRICK_URL", "https://proxmox.monit.kernow.io"),
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
    # Phase 3
    "ReverseProxy", "Device", "HAEntity", "TasmotaDevice", "CloudflareTunnel",
]

# DHCP network name mapping (OPNsense interface descriptions -> graph network names)
DHCP_NETWORK_MAP: dict[str, str] = {
    "Production": "prod",
    "ArtificialIntelligence": "agentic",
    "Monit": "monit",
}

# DHCP manufacturer -> device type classification
MANUFACTURER_DEVICE_TYPE: dict[str, str] = {
    "espressif": "iot",
    "google": "smart_home",
    "nest": "smart_home",
    "apple": "personal",
    "ubiquiti": "network",
    "sonos": "media",
    "samsung": "smart_home",
    "amazon": "smart_home",
    "hp": "printer",
    "brother": "printer",
    "intel": "compute",
    "dell": "compute",
    "lenovo": "compute",
    "proxmox": "hypervisor",
}

# HA entity domains to sync (Gemini ruling: filter sensors aggressively)
HA_SYNC_DOMAINS = [
    "light", "switch", "automation", "binary_sensor",
    "climate", "cover", "fan", "lock", "media_player",
    "sensor",  # filtered further by SENSOR_DEVICE_CLASSES
]

# Sensor device_classes to sync (Gemini ruling: battery, power, temperature only)
SENSOR_DEVICE_CLASSES = ["battery", "power", "temperature", "energy"]

# DNS noise patterns to filter during sync (Phase 0: Graph Connectivity)
# These patterns bloat the graph without providing operational value
DNS_NOISE_PATTERNS = [
    "wpad",                    # Web Proxy Auto-Discovery
    "isatap",                  # Intra-Site Automatic Tunnel
    "teredo",                  # IPv6 tunneling
    "_acme-challenge",         # Let's Encrypt validation
    "_dmarc",                  # Email authentication
    "_spf",                    # Email authentication
    "_mta-sts",                # Email security
    "autoconfig",              # Mail client auto-config
    "autodiscover",            # Exchange auto-discovery
    "_domainkey",              # DKIM records
    "_kerberos",               # Kerberos service records
    "gc._msdcs",               # Active Directory
    "domaindnszones",          # Active Directory
    "forestdnszones",          # Active Directory
]
