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
├── Agentic Cluster + Internal Access (PREFERRED)
│   └── Use Agentic Traefik Pattern ★ NEW
│       1. Deployment + Service in agentic
│       2. Traefik Ingress in agentic
│       3. AdGuard DNS rewrite → 10.20.0.90
│
├── Agentic/Monit + External Access Needed
│   └── Use External Service Bridge Pattern
│       1. NodePort in source cluster
│       2. Service + Endpoints in prod (no selector)
│       3. Cloudflare tunnel ingress in prod
│
└── Agentic/Monit + Internal (via Caddy)
    └── Use Caddy + AdGuard Pattern (legacy)
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
- **Internal (LAN)**: Unbound resolves `*.kernow.io` → 10.10.0.90 (Prod Traefik)
- **External (Internet)**: Cloudflare DNS → Cloudflare Tunnel → Service

### Example Files
See runbook: `/home/agentic_lab/runbooks/infrastructure/new-app-prod.md`

---

## Pattern 2: Agentic Traefik (PREFERRED for Agentic Internal)

### When to Use
- App deployed in agentic cluster
- Internal LAN access only
- Standard Kubernetes Ingress sufficient
- **This is the preferred pattern for new agentic services**

### Components
1. **Deployment + Service** in agentic cluster (ClusterIP or NodePort)
2. **Traefik Ingress** in agentic cluster
3. **AdGuard DNS rewrite** to 10.20.0.90

### Traffic Flow
```
LAN Client → AdGuard DNS (app.kernow.io → 10.20.0.90)
          → Agentic Traefik LB (10.20.0.90)
          → Ingress → Service → Pod
```

### Key Configuration
```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app
  namespace: my-namespace
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: websecure
    traefik.ingress.kubernetes.io/router.tls: "true"
spec:
  ingressClassName: traefik
  rules:
    - host: my-app.kernow.io
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: my-app
                port:
                  number: 8080
```

### Services Using This Pattern
| Service | Namespace | DNS | NodePort |
|---------|-----------|-----|----------|
| Backrest | backrest | backrest.kernow.io | 31115 |
| Keep | keep | keep.kernow.io | 31105 |
| Vikunja | vikunja | vikunja.kernow.io | 31095 |
| Matrix | ai-platform | matrix.kernow.io | 30167 |
| Outline | ai-platform | outline.kernow.io | 31113 |
| Fumadocs | ai-platform | fumadocs.kernow.io | 31099 |
| LangGraph | ai-platform | langgraph.kernow.io | 30800 |

### Example Files
See runbook: `/home/agentic_lab/runbooks/infrastructure/new-app-agentic-traefik.md`

---

## Pattern 3: External Service Bridge (Non-Prod + External)

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
- Matrix: NodePort 30167 on agentic → matrix-external service in prod → matrix.kernow.io (external)
- LangGraph: NodePort 30800 on agentic → langgraph-external service in prod → langgraph.kernow.io (external)

### Example Files
See runbook: `/home/agentic_lab/runbooks/infrastructure/new-app-agentic-external.md`

---

## Pattern 4: Caddy + AdGuard (Legacy/Custom)

### When to Use
- App deployed in agentic or monit cluster
- Internal LAN access only
- Need custom Caddy features (headers, rewrites, middleware)
- Legacy compatibility

### Components
1. **NodePort Service** in source cluster
2. **AdGuard DNS Rewrite**: hostname → 10.10.0.1 (Caddy)
3. **Caddy Reverse Proxy**: forwards to source NodePort

### Traffic Flow
```
LAN Client → AdGuard DNS → 10.10.0.1 (Caddy)
          → Caddy → 10.20.0.40:NodePort → App
```

### When to Use Caddy Instead of Agentic Traefik
- Need custom HTTP headers
- Need path rewriting
- Need Caddy-specific middleware
- Legacy service that already uses Caddy

### Example Files
See runbook: `/home/agentic_lab/runbooks/infrastructure/new-app-agentic-internal.md`

---

## Key IPs

| Service | IP | Purpose |
|---------|-----|---------|
| Prod Traefik LB | 10.10.0.90 | Internal ingress for prod cluster |
| **Agentic Traefik LB** | **10.20.0.90** | Internal ingress for agentic cluster |
| Caddy | 10.10.0.1 | Reverse proxy (legacy pattern) |
| Agentic Node | 10.20.0.40 | NodePort target for agentic services |
| Monit Node | 10.30.0.20 | NodePort target for monit services |

## Traefik LoadBalancer Details

### Production Cluster (10.10.0.0/24)
```
Namespace:  traefik (or kube-system)
Service:    traefik
Type:       LoadBalancer
IP:         10.10.0.90
Ports:      80 (web), 443 (websecure)
Assigned:   Via MetalLB or Cilium LB IPAM
```

### Agentic Cluster (10.20.0.0/24)
```
Namespace:  traefik
Service:    traefik
Type:       LoadBalancer
IP:         10.20.0.90
Ports:      80 (web), 443 (websecure), 8080 (admin)
Assigned:   Via Cilium LB IPAM (label: io.cilium/lb-ipam-ips=traefik)
NodePorts:  31734 (web), 30662 (websecure), 30203 (admin)
```

## DNS Rewrite Reference

### Services via Agentic Traefik (10.20.0.90)
```
backrest.kernow.io      → 10.20.0.90
claude-refresh.kernow.io → 10.20.0.90
fumadocs.kernow.io      → 10.20.0.90
keep.kernow.io          → 10.20.0.90
langgraph.kernow.io     → 10.20.0.90  (also: langraph.kernow.io typo)
matrix.kernow.io        → 10.20.0.90
outline.kernow.io       → 10.20.0.90
vikunja.kernow.io       → 10.20.0.90
```

### Services via Caddy (10.10.0.1)
```
adguard.kernow.io       → 10.10.0.1
api-keep.kernow.io      → 10.10.0.1
beszel.kernow.io        → 10.10.0.1
coroot.kernow.io        → 10.10.0.1
garage.kernow.io        → 10.10.0.1
gatus.kernow.io         → 10.10.0.1
grafana.kernow.io       → 10.10.0.1
minio.kernow.io         → 10.10.0.1
netbox.kernow.io        → 10.10.0.1
opnsense.kernow.io      → 10.10.0.1
prometheus.kernow.io    → 10.10.0.1
proxmox.kernow.io       → 10.10.0.1
qdrant.kernow.io        → 10.10.0.1
truenas.kernow.io       → 10.10.0.1
truenas.hdd.kernow.io   → 10.10.0.1
unifi.kernow.io         → 10.10.0.1
```

### Services via Prod Traefik (default via Unbound wildcard)
All `*.kernow.io` not listed above resolve to 10.10.0.90 via Unbound wildcard.

## NodePort Ranges

- Standard range: 30000-32767
- Current allocations tracked in cluster services

## Choosing a Pattern

| Scenario | Pattern | DNS Target |
|----------|---------|------------|
| New prod app | Dual-Ingress | (auto via wildcard) |
| New agentic internal app | **Agentic Traefik** | 10.20.0.90 |
| New agentic app + internet | External Bridge | (via Cloudflare) |
| Custom proxy needs | Caddy + AdGuard | 10.10.0.1 |

## Tags for Indexing

`domain`, `routing`, `ingress`, `cloudflare`, `traefik`, `caddy`, `adguard`, `dns`, `kernow.io`, `cilium`, `loadbalancer`
