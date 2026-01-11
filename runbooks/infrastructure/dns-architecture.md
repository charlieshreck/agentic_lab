# DNS Architecture - Kernow Homelab

## Overview

The homelab uses a **split-DNS architecture** with AdGuard Home and Unbound working together. This is intentional and by design.

## Architecture Diagram

```
                                    INTERNAL CLIENTS
                                          │
                                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      AdGuard Home (10.10.0.1:53)                        │
│                                                                          │
│  1. Blocklist filtering (ads, trackers, malware)                        │
│  2. Specific rewrites for external-access services → 10.10.0.1 (Caddy)  │
│  3. Everything else → forwards to Unbound                               │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Unbound (localhost:53535)                           │
│                                                                          │
│  1. Host overrides for internal domains:                                │
│     - *.kernow.io → 10.10.0.90 (Prod Cluster Load Balancer)            │
│     - *.shreck.io → 10.30.0.120                                         │
│     - *.shreck.co.uk → 10.10.0.80                                       │
│  2. DNSSEC validation                                                   │
│  3. Recursive resolution for external domains                           │
└─────────────────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### Why Two Layers?

| Layer | Purpose |
|-------|---------|
| **AdGuard Home** | Ad blocking, query logging, specific external-access rewrites |
| **Unbound** | Internal DNS resolution, DNSSEC, recursive resolution |

### Split-DNS for kernow.io

The `*.kernow.io` domain uses split-DNS:

| Scenario | DNS Path | Target IP | Purpose |
|----------|----------|-----------|---------|
| **Internal traffic** | Unbound wildcard | 10.10.0.90 | Prod cluster Traefik LB |
| **External access** | AdGuard rewrite | 10.10.0.1 | Caddy on OPNsense (reverse proxy) |

### IP Addresses

| IP | Role |
|----|------|
| **10.10.0.1** | OPNsense firewall, Caddy reverse proxy, AdGuard Home |
| **10.10.0.90** | Prod cluster load balancer (Traefik) |
| **10.30.0.120** | Monit cluster services |

## How Rewrites Work

### AdGuard Rewrites (Specific Overrides)

These are for services that need external access via Caddy:
- `grafana.kernow.io → 10.10.0.1`
- `matrix.kernow.io → 10.10.0.1`
- `prometheus.kernow.io → 10.10.0.1`
- etc.

When a client queries one of these specific domains, AdGuard returns 10.10.0.1 immediately (Caddy handles the routing).

### Unbound Wildcard (Default Internal)

For any `*.kernow.io` domain NOT in AdGuard's rewrite list:
- Query passes through AdGuard (no match)
- Forwards to Unbound
- Unbound matches `*.kernow.io → 10.10.0.90`
- Traffic goes directly to prod cluster Traefik

## Adding New Services

### Internal-Only Service (No External Access)

No action needed - Unbound wildcard catches it automatically.

```
new-service.kernow.io → Unbound → 10.10.0.90 → Traefik → Service
```

### Service Needing External Access

1. Add AdGuard rewrite: `service.kernow.io → 10.10.0.1`
2. Configure Caddy on OPNsense to proxy to the service
3. (Optional) Add Cloudflare tunnel for true external access

## Troubleshooting

### Service Resolving to Wrong IP

1. Check if AdGuard has a specific rewrite: `adguard-mcp: get_adguard_rewrites()`
2. If no rewrite, it will use Unbound wildcard (10.10.0.90)
3. Add/remove AdGuard rewrite as needed

### DNS Not Resolving

1. Check AdGuard status: `adguard-mcp: get_adguard_status()`
2. Check Unbound status: `opnsense-mcp: get_unbound_stats()`
3. Verify upstream connectivity

### Common Mistakes to Avoid

1. **DO NOT** add `10.10.0.1:53` as an upstream in AdGuard (creates loop)
2. **DO NOT** add domain overrides in Unbound pointing to AdGuard
3. **DO NOT** remove the Unbound `*.kernow.io` wildcard

## Related Documentation

- Caddy configuration: OPNsense web UI
- Traefik configuration: `/home/prod_homelab/kubernetes/platform/traefik/`
- AdGuard MCP: `adguard-mcp` tools
- OPNsense MCP: `opnsense-mcp` tools (includes Unbound)

Tags for indexing: `dns, adguard, unbound, split-dns, kernow.io, routing, architecture`
