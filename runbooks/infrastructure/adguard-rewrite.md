# AdGuard DNS Rewrite Configuration

## Overview
AdGuard Home provides DNS filtering and rewriting for the homelab network. DNS rewrites redirect specific hostnames to internal IP addresses, enabling access to internal services via friendly domain names.

## Location
- Server: AdGuard Home instance
- Access: Via `adguard-mcp` or web UI
- Integration: Works with Caddy reverse proxy for internal services

## MCP Tools

### Using adguard-mcp

#### List DNS Rewrites
```
Tool: list_dns_rewrites
```

#### Add DNS Rewrite
```
Tool: add_dns_rewrite
Parameters:
  domain: <hostname>.kernow.io
  answer: <target-ip>
```

#### Remove DNS Rewrite
```
Tool: remove_dns_rewrite
Parameters:
  domain: <hostname>.kernow.io
```

## Common Operations

### Add Rewrite for Internal Service

For services behind Caddy (most internal services):
```
domain: app.kernow.io
answer: 10.10.0.1  # Caddy server
```

For direct access to specific IPs:
```
domain: truenas.kernow.io
answer: 10.10.0.100
```

### Wildcard Rewrites

Wildcard already configured in Unbound for `*.kernow.io → 10.10.0.90` (Traefik).

For internal services, add specific rewrites that take precedence:
```
domain: internal-app.kernow.io
answer: 10.10.0.1  # Overrides wildcard
```

## Workflow: New Internal Service

1. Deploy app with NodePort in agentic cluster
2. Add AdGuard rewrite pointing to Caddy (10.10.0.1)
3. Add Caddy reverse proxy entry
4. Test access

Example:
```
1. kubectl get svc myapp -n ai-platform
   → NodePort: 30123

2. adguard-mcp: add_dns_rewrite("myapp.kernow.io", "10.10.0.1")

3. Caddy entry:
   myapp.kernow.io {
       reverse_proxy 10.20.0.40:30123
       tls internal
   }

4. curl -k https://myapp.kernow.io
```

## Verification

### Check DNS Resolution
```bash
# Should return the rewrite target
dig myapp.kernow.io

# Test from client using AdGuard DNS
nslookup myapp.kernow.io <adguard-ip>
```

### Check Rewrite Exists
Use `list_dns_rewrites` via adguard-mcp or check AdGuard UI.

## Troubleshooting

### DNS Not Resolving to Expected IP
1. Check rewrite exists in AdGuard
2. Check client DNS settings point to AdGuard
3. Clear DNS cache: `sudo dscacheutil -flushcache` (macOS) or `ipconfig /flushdns` (Windows)

### Rewrite Conflict
- More specific rewrites take precedence
- Check for duplicate entries

### Caching Issues
- AdGuard caches DNS responses
- Clear cache in AdGuard UI or restart service

## Current Rewrites

Query via adguard-mcp:
```
Tool: list_dns_rewrites
```

## Common Patterns

| Pattern | Domain | Target | Purpose |
|---------|--------|--------|---------|
| Caddy proxy | `app.kernow.io` | `10.10.0.1` | Internal service via Caddy |
| Direct access | `truenas.kernow.io` | `10.10.0.100` | Direct to service IP |
| Cluster internal | `*.cluster.local` | Varies | K8s internal DNS |

## Integration

### With Caddy
1. Rewrite points to Caddy (10.10.0.1)
2. Caddy proxies to actual backend
3. See: `runbooks/infrastructure/caddy-proxy.md`

### With Traefik (Prod)
- Wildcard `*.kernow.io → 10.10.0.90` handled by Unbound
- No AdGuard rewrite needed for prod apps
- AdGuard rewrites override for specific internal services

## Direct API Access

When adguard-mcp is unavailable or for automation scripts, use the AdGuard API directly.

### Credentials
```bash
# Get from Infisical
ADGUARD_USER=$(/root/.config/infisical/secrets.sh get /infrastructure/adguard username)
ADGUARD_PASS=$(/root/.config/infisical/secrets.sh get /infrastructure/adguard password)
```

### List Rewrites
```bash
curl -s -u "${ADGUARD_USER}:${ADGUARD_PASS}" \
  "http://10.10.0.1:3000/control/rewrite/list" | jq '.'
```

### Add Rewrite
```bash
curl -s -X POST "http://10.10.0.1:3000/control/rewrite/add" \
  -u "${ADGUARD_USER}:${ADGUARD_PASS}" \
  -H "Content-Type: application/json" \
  -d '{"domain":"app.kernow.io","answer":"10.10.0.1"}'
```

### Delete Rewrite
```bash
curl -s -X POST "http://10.10.0.1:3000/control/rewrite/delete" \
  -u "${ADGUARD_USER}:${ADGUARD_PASS}" \
  -H "Content-Type: application/json" \
  -d '{"domain":"app.kernow.io","answer":"10.10.0.1"}'
```

### Via adguard-mcp REST API
```bash
# List rewrites (no auth needed - MCP handles it)
curl -s http://10.20.0.40:31086/api/rewrites | jq '.'
```

## Automation Considerations

When deploying new internal services:
1. Add rewrite via adguard-mcp (preferred)
2. Or use AdGuard API directly (see above)
3. Document the rewrite in service deployment notes

## Security Notes

- DNS rewrites only work for clients using AdGuard DNS
- External clients bypass AdGuard (use Cloudflare DNS)
- This provides basic access control for internal-only services
