# Infisical Secrets Structure

> **This document defines the canonical structure for all secrets in Infisical.**
> **All new secrets MUST follow this structure. No exceptions.**

---

## Design Principles

1. **Single Source of Truth**: Each credential stored exactly ONCE
2. **Domain-Aligned**: Structure mirrors MCP domain architecture
3. **Predictable Paths**: Derivable programmatically: `/{domain}/{service}/{KEY}`
4. **Consistent Naming**: Strict conventions for paths and keys
5. **Consumer-Agnostic**: Organized by credential owner, not by who consumes it

---

## Naming Conventions

### Path Format
```
/{domain}/{service}
```

| Rule | Example | Anti-pattern |
|------|---------|--------------|
| Lowercase everything | `/infrastructure/proxmox-ruapehu` | `/Infrastructure/Proxmox` |
| Hyphens for multi-word | `/media/truenas-hdd` | `/media/truenas_hdd` |
| No trailing slashes | `/observability/grafana` | `/observability/grafana/` |
| No abbreviations | `/infrastructure/cloudflare` | `/infra/cf` |

### Secret Key Format
```
SCREAMING_SNAKE_CASE
```

| Rule | Example | Anti-pattern |
|------|---------|--------------|
| All caps with underscores | `API_KEY` | `api_key`, `apiKey`, `Api_Key` |
| Descriptive but concise | `TOKEN_SECRET` | `secret`, `s`, `the_secret_token_value` |
| Prefix only for disambiguation | `PROD_API_KEY` | `API_KEY_FOR_PROD` |

### Standard Key Names

Use these standard names across all services for consistency:

| Key | Usage | Notes |
|-----|-------|-------|
| `HOST` | Service URL/endpoint | Include protocol: `https://...` |
| `API_KEY` | Single API key authentication | Preferred over `API_TOKEN` |
| `USERNAME` | Username for basic auth | |
| `PASSWORD` | Password for basic auth | |
| `TOKEN_ID` | Token identifier | Proxmox-style auth |
| `TOKEN_SECRET` | Token secret value | Proxmox-style auth |
| `CLIENT_ID` | OAuth/machine identity ID | |
| `CLIENT_SECRET` | OAuth/machine identity secret | |
| `JWT_SECRET` | JWT signing secret | |
| `SECRET_KEY` | Application secret key | Django/Flask style |
| `SSH_PRIVATE_KEY` | SSH private key (PEM format) | |
| `SSH_PUBLIC_KEY` | SSH public key | |
| `WEBHOOK_SECRET` | Webhook validation secret | |

---

## Domain Structure

### Overview

```
/
├── infrastructure/    # Physical/virtual infrastructure, network
├── observability/     # Monitoring, alerting, metrics
├── knowledge/         # Data stores, wikis, knowledge systems
├── home/              # Smart home, IoT, network management
├── media/             # Media servers, arr suite, downloads
├── external/          # External APIs and services
├── platform/          # Cross-cutting platform services
└── backups/           # Backup infrastructure
```

### Domain Descriptions

| Domain | Purpose | MCP |
|--------|---------|-----|
| `infrastructure` | Hypervisors, NAS, DNS, firewall, tunnels | infrastructure-mcp |
| `observability` | Grafana, Keep, Coroot, AlertManager | observability-mcp |
| `knowledge` | Qdrant, Neo4j, Outline, Vikunja, PostgreSQL | knowledge-mcp |
| `home` | Home Assistant, Tasmota, UniFi, Homepage | home-mcp |
| `media` | Plex, Sonarr, Radarr, Transmission, etc. | media-mcp |
| `external` | GitHub, OpenRouter, Gemini, SearXNG | external-mcp |
| `platform` | ArgoCD, OpenWebUI, LiteLLM | (no dedicated MCP) |
| `backups` | Garage S3, Backrest, Velero credentials | (no MCP) |

---

## Complete Structure

### /infrastructure

Physical and virtual infrastructure, networking, DNS.

```
/infrastructure/
├── proxmox-ruapehu/           # Primary Proxmox host
│   ├── HOST                   # https://10.10.0.6:8006
│   ├── TOKEN_ID               # root@pam!<token-name>
│   └── TOKEN_SECRET
├── proxmox-carrick/           # Secondary Proxmox host
│   ├── HOST                   # https://10.10.0.7:8006
│   ├── TOKEN_ID
│   └── TOKEN_SECRET
├── truenas-hdd/               # TrueNAS HDD storage
│   ├── HOST                   # https://10.10.0.51
│   └── API_KEY
├── truenas-media/             # TrueNAS Media storage
│   ├── HOST                   # https://10.10.0.52
│   └── API_KEY
├── cloudflare/
│   ├── API_TOKEN
│   ├── ACCOUNT_ID
│   ├── EMAIL
│   ├── TUNNEL_ID
│   ├── TUNNEL_NAME
│   └── TUNNEL_TOKEN
├── opnsense/
│   ├── HOST                   # https://10.10.0.1
│   ├── API_KEY
│   └── API_SECRET
├── adguard/                   # AdGuard on OPNsense (network DNS)
│   ├── HOST                   # http://10.10.0.1:3000
│   ├── USERNAME
│   └── PASSWORD
└── infisical/
    ├── HOST                   # https://app.infisical.com
    ├── CLIENT_ID
    ├── CLIENT_SECRET
    └── WORKSPACE_ID
```

### /observability

Monitoring, alerting, and metrics systems.

```
/observability/
├── grafana/
│   ├── HOST                   # http://10.30.0.20:30081
│   ├── USERNAME               # admin
│   └── PASSWORD
├── keep/
│   ├── HOST                   # http://keep.keep.svc.cluster.local:8080
│   ├── API_KEY
│   ├── JWT_SECRET
│   ├── NEXTAUTH_SECRET
│   └── WEBHOOK_ENDPOINT
├── coroot/
│   ├── HOST                   # http://10.30.0.20:32702
│   ├── AGENTIC_API_KEY        # Per-cluster API keys
│   ├── PROD_API_KEY
│   └── MONIT_API_KEY
├── alertmanager/
│   └── HOST                   # http://10.30.0.20:30083
└── victoriametrics/
    └── HOST                   # http://10.30.0.20:30084
```

### /knowledge

Data stores, knowledge bases, and documentation systems.

```
/knowledge/
├── qdrant/
│   ├── HOST                   # http://qdrant.ai-platform.svc.cluster.local:6333
│   └── API_KEY                # (if auth enabled)
├── neo4j/
│   ├── HOST                   # http://neo4j.ai-platform.svc.cluster.local:7474
│   ├── USERNAME               # neo4j
│   └── PASSWORD
├── outline/
│   ├── HOST
│   ├── API_KEY
│   ├── SECRET_KEY
│   ├── UTILS_SECRET
│   ├── GITHUB_CLIENT_ID
│   ├── GITHUB_CLIENT_SECRET
│   ├── GOOGLE_CLIENT_ID
│   ├── GOOGLE_CLIENT_SECRET
│   ├── DISCORD_CLIENT_ID
│   ├── DISCORD_CLIENT_SECRET
│   └── DISCORD_SERVER_ID
├── vikunja/
│   ├── HOST
│   ├── API_TOKEN
│   ├── JWT_SECRET
│   └── POSTGRES_PASSWORD
└── postgresql/
    ├── HOST
    ├── USERNAME
    └── PASSWORD
```

### /home

Smart home, IoT, and local network management.

```
/home/
├── homeassistant/
│   ├── HOST
│   └── API_KEY
├── tasmota/
│   └── (no secrets - HTTP API without auth)
├── unifi/
│   ├── HOST
│   ├── USERNAME
│   └── PASSWORD
├── mqtt/
│   ├── HOST
│   ├── USERNAME
│   └── PASSWORD
└── homepage/
    └── (no secrets - references other service paths)
```

### /media

Media servers and management.

```
/media/
├── plex/
│   ├── HOST
│   ├── TOKEN
│   └── SSH_PRIVATE_KEY        # GPU server access
├── sonarr/
│   ├── HOST
│   └── API_KEY
├── radarr/
│   ├── HOST
│   └── API_KEY
├── prowlarr/
│   ├── HOST
│   └── API_KEY
├── overseerr/
│   ├── HOST
│   └── API_KEY
├── tautulli/
│   ├── HOST
│   └── API_KEY
├── transmission/
│   ├── HOST
│   ├── USERNAME
│   └── PASSWORD
├── sabnzbd/
│   ├── HOST
│   └── API_KEY
└── notifiarr/
    ├── API_KEY
    └── UI_PASSWORD
```

### /external

External APIs and third-party services.

```
/external/
├── github/
│   ├── TOKEN                  # Personal Access Token
│   └── WEBHOOK_SECRET
├── openrouter/
│   └── API_KEY
├── gemini/
│   ├── API_KEY
│   ├── API_KEY_2              # Backup key if needed
│   ├── OAUTH_CREDS_B64
│   └── SETTINGS_B64
└── searxng/
    └── SECRET_KEY
```

### /platform

Cross-cutting platform services.

```
/platform/
├── argocd/
│   └── ADMIN_PASSWORD
├── openwebui/
│   └── SECRET_KEY
├── litellm/
│   └── (references /external/openrouter, /external/gemini)
└── mcp-config-sync/
    ├── GITHUB_WEBHOOK_SECRET
    └── KUBECONFIG_B64
```

### /backups

Backup infrastructure (isolated, quiet, no MCP).

```
/backups/
├── garage/                    # S3-compatible storage
│   ├── ENDPOINT
│   ├── REGION
│   ├── ACCESS_KEY_ID
│   ├── SECRET_ACCESS_KEY
│   ├── ADMIN_TOKEN
│   ├── BUCKET_VELERO_PROD
│   ├── BUCKET_VELERO_AGENTIC
│   ├── BUCKET_VELERO_MONIT
│   └── BUCKET_BACKREST
└── backrest/
    ├── SSH_PRIVATE_KEY
    └── SSH_PUBLIC_KEY
```

---

## Programmatic Path Derivation

Paths are deterministic given domain and service:

```python
def get_infisical_path(domain: str, service: str) -> str:
    """
    Returns the canonical Infisical path for a service.

    Args:
        domain: infrastructure, observability, knowledge, home,
                media, external, platform, backups
        service: lowercase, hyphenated service name

    Returns:
        Canonical path: /{domain}/{service}
    """
    # Validate domain
    valid_domains = [
        "infrastructure", "observability", "knowledge",
        "home", "media", "external", "platform", "backups"
    ]
    if domain not in valid_domains:
        raise ValueError(f"Invalid domain: {domain}")

    # Normalize service name
    service = service.lower().replace("_", "-").replace(" ", "-")

    return f"/{domain}/{service}"


# Examples:
get_infisical_path("infrastructure", "proxmox-ruapehu")  # /infrastructure/proxmox-ruapehu
get_infisical_path("media", "sonarr")                    # /media/sonarr
get_infisical_path("external", "github")                 # /external/github
```

---

## How to Reference Secrets

### In Kubernetes (InfisicalSecret CRD)

```yaml
apiVersion: secrets.infisical.com/v1alpha1
kind: InfisicalSecret
metadata:
  name: myapp-proxmox-credentials
  namespace: my-namespace
spec:
  hostAPI: https://app.infisical.com/api
  resyncInterval: 300
  authentication:
    universalAuth:
      credentialsRef:
        secretName: universal-auth-credentials
        secretNamespace: infisical-operator-system
      secretsScope:
        projectSlug: prod-homelab-y-nij
        envSlug: prod
        secretsPath: /infrastructure/proxmox-ruapehu  # <-- Canonical path
  managedSecretReference:
    secretName: myapp-proxmox-credentials
    secretNamespace: my-namespace
    secretType: Opaque
    creationPolicy: Owner
```

### In CLI Scripts

```bash
# Using the helper script
/root/.config/infisical/secrets.sh get /infrastructure/proxmox-ruapehu TOKEN_SECRET

# List all secrets in a service path
/root/.config/infisical/secrets.sh list /infrastructure/proxmox-ruapehu
```

### Multiple Services in One App

When an app needs secrets from multiple services, create separate InfisicalSecret CRDs:

```yaml
# App needs both Proxmox and Cloudflare
---
apiVersion: secrets.infisical.com/v1alpha1
kind: InfisicalSecret
metadata:
  name: myapp-proxmox
spec:
  secretsScope:
    secretsPath: /infrastructure/proxmox-ruapehu
  managedSecretReference:
    secretName: myapp-proxmox
---
apiVersion: secrets.infisical.com/v1alpha1
kind: InfisicalSecret
metadata:
  name: myapp-cloudflare
spec:
  secretsScope:
    secretsPath: /infrastructure/cloudflare
  managedSecretReference:
    secretName: myapp-cloudflare
```

---

## Adding New Secrets

### Checklist

1. **Identify the domain**: Which of the 8 domains does this service belong to?
2. **Name the service**: Lowercase, hyphenated, descriptive
3. **Use standard key names**: Check the table above before inventing new names
4. **Create the path**: `/{domain}/{service}`
5. **Add secrets**: Using SCREAMING_SNAKE_CASE
6. **Document**: If it's a new service, add it to this document

### Example: Adding a New Service

Adding Jellyfin to the media stack:

```bash
# 1. Create the folder
/root/.config/infisical/secrets.sh mkdir /media jellyfin

# 2. Add secrets with standard names
/root/.config/infisical/secrets.sh set /media/jellyfin HOST "http://jellyfin.media.svc:8096"
/root/.config/infisical/secrets.sh set /media/jellyfin API_KEY "abc123..."

# 3. Update this document to include jellyfin under /media
```

---

## Anti-Patterns (DO NOT DO)

| Anti-Pattern | Why It's Wrong | Correct Approach |
|--------------|----------------|------------------|
| `/mcp/infrastructure` | Consumer-specific path | Use `/infrastructure/*` directly |
| `/agentic-platform/keep` | Cluster-specific path | Use `/observability/keep` |
| `/apps/truenas-hdd` | "apps" is ambiguous | Use `/infrastructure/truenas-hdd` |
| `api_key` | Wrong case | Use `API_KEY` |
| `/infrastructure/Proxmox` | Wrong case | Use `/infrastructure/proxmox-ruapehu` |
| Duplicate secrets in multiple paths | Maintenance nightmare | Single source of truth |

---

## Migration Notes

This structure was adopted on **2025-01-22** to replace the previous ad-hoc structure.

See `infisical-migration-plan.md` for the complete migration from old paths to new.

---

## Maintainer

This structure is maintained as part of the Kernow Homelab infrastructure.
Changes to this document require review to ensure backward compatibility.
