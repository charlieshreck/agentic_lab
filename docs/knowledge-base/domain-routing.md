# Domain Routing (kernow.io)

## Overview
All services are accessible via `*.kernow.io` domain. Routing depends on cluster location and access requirements.

## Decision Tree

```
New App → Which Cluster?
│
├── Prod Cluster (10.10.0.0/24)
│   └── Use Dual-Ingress Pattern
│       ├── Internal: Traefik ingress → 10.10.0.90
│       └── External: Cloudflare tunnel ingress
│
├── Agentic/Monit + External Access Needed
│   └── Use External Service Bridge Pattern
│       1. NodePort in source cluster
│       2. Service + Endpoints in prod (no selector)
│       3. Cloudflare tunnel ingress in prod
│
└── Agentic/Monit + Internal Only
    └── Use Caddy + AdGuard Pattern
        1. NodePort in source cluster
        2. AdGuard DNS rewrite → 10.10.0.1
        3. Caddy reverse proxy entry
```

## Pattern 1: Dual-Ingress (Prod Cluster)

### When to Use
- App deployed in production cluster
- Needs both internal LAN and external internet access

### Components
1. **Traefik Ingress** (`ingress.yaml`)
   - IngressClass: `traefik`
   - Handles internal LAN traffic
   - cert-manager for TLS certificates

2. **Cloudflare Tunnel Ingress** (`cloudflare-tunnel-ingress.yaml`)
   - IngressClass: `cloudflare-tunnel`
   - Handles external internet traffic
   - No TLS config needed (Cloudflare handles SSL)

### DNS Resolution
- **Internal (LAN)**: Unbound resolves `*.kernow.io` → 10.10.0.90 (Traefik)
- **External (Internet)**: Cloudflare DNS → Cloudflare Tunnel → Service

### Example Files
See runbook: `/home/agentic_lab/runbooks/infrastructure/new-app-prod.md`

## Pattern 2: External Service Bridge (Non-Prod + External)

### When to Use
- App deployed in agentic or monit cluster
- Needs external internet access
- Cloudflare Tunnel only runs in prod cluster

### Components
1. **NodePort Service** in source cluster (agentic/monit)
2. **Bridge Service** in prod cluster (ClusterIP, no selector)
3. **Bridge Endpoints** in prod cluster (points to source NodePort)
4. **Cloudflare Tunnel Ingress** in prod cluster

### Traffic Flow
```
Internet → Cloudflare → Prod Cluster
         → Service/Endpoints → 10.20.0.40:NodePort
         → Agentic Cluster → App
```

### Example
- Matrix: NodePort 30167 on agentic → matrix-external service in prod → matrix.kernow.io
- LangGraph: NodePort 30800 on agentic → langgraph-external service in prod → langgraph.kernow.io

### Example Files
See runbook: `/home/agentic_lab/runbooks/infrastructure/new-app-agentic-external.md`

## Pattern 3: Caddy + AdGuard (Non-Prod + Internal Only)

### When to Use
- App deployed in agentic or monit cluster
- Internal LAN access only (no internet)
- Development, testing, or sensitive services

### Components
1. **NodePort Service** in source cluster
2. **AdGuard DNS Rewrite**: hostname → 10.10.0.1 (Caddy)
3. **Caddy Reverse Proxy**: forwards to source NodePort

### Traffic Flow
```
LAN Client → AdGuard DNS → 10.10.0.1 (Caddy)
          → Caddy → 10.20.0.40:NodePort → App
```

### Example Files
See runbook: `/home/agentic_lab/runbooks/infrastructure/new-app-agentic-internal.md`

## Key IPs

| Service | IP | Purpose |
|---------|-----|---------|
| Traefik LoadBalancer | 10.10.0.90 | Internal ingress for prod |
| Caddy | 10.10.0.1 | Reverse proxy for internal services |
| Agentic Node | 10.20.0.40 | NodePort target for agentic services |
| Monit Node | 10.30.0.20 | NodePort target for monit services |

## NodePort Ranges

- Standard range: 30000-32767
- Current allocations tracked in cluster

## Tags for Indexing
`domain`, `routing`, `ingress`, `cloudflare`, `traefik`, `caddy`, `adguard`, `dns`, `kernow.io`
