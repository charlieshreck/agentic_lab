# Caddy Reverse Proxy Configuration

## Overview
Caddy serves as the reverse proxy for internal-only services on the homelab network. It runs on OPNsense (10.10.0.1) as a plugin and handles TLS termination for internal services.

## Location
- Server: 10.10.0.1 (OPNsense firewall)
- Management: OPNsense Web UI or API
- Plugin: os-caddy

## OPNsense API Access

Caddy on OPNsense is managed via the REST API.

### Credentials
```bash
# Get from Infisical
OPNSENSE_KEY=$(/root/.config/infisical/secrets.sh get /infrastructure/opnsense key)
OPNSENSE_SECRET=$(/root/.config/infisical/secrets.sh get /infrastructure/opnsense secret)
```

### List Current Reverse Proxies
```bash
curl -sk --user "${OPNSENSE_KEY}:${OPNSENSE_SECRET}" \
  'https://10.10.0.1:8443/api/caddy/ReverseProxy/searchReverseProxy' \
  -X POST | jq '.rows[] | {domain: .FromDomain, description: .description}'
```

### Add New Reverse Proxy (Two Steps)

**Step 1: Create the domain entry**
```bash
# Returns UUID of created entry
curl -sk --user "${OPNSENSE_KEY}:${OPNSENSE_SECRET}" \
  'https://10.10.0.1:8443/api/caddy/ReverseProxy/addReverseProxy' \
  -X POST -H 'Content-Type: application/json' \
  -d '{"reverse":{"enabled":"1","FromDomain":"app.kernow.io","description":"My App","DnsChallenge":"1"}}'
```

**Step 2: Add backend handle (using UUID from step 1)**
```bash
curl -sk --user "${OPNSENSE_KEY}:${OPNSENSE_SECRET}" \
  'https://10.10.0.1:8443/api/caddy/ReverseProxy/addHandle' \
  -X POST -H 'Content-Type: application/json' \
  -d '{"handle":{"enabled":"1","reverse":"<UUID>","HandleType":"handle","HandleDirective":"reverse_proxy","ToDomain":"10.20.0.40","ToPort":"31095","description":"Backend"}}'
```

**Step 3: Apply configuration**
```bash
curl -sk --user "${OPNSENSE_KEY}:${OPNSENSE_SECRET}" \
  'https://10.10.0.1:8443/api/caddy/service/reconfigure' -X POST
```

### List Backend Handles
```bash
curl -sk --user "${OPNSENSE_KEY}:${OPNSENSE_SECRET}" \
  'https://10.10.0.1:8443/api/caddy/ReverseProxy/searchHandle' \
  -X POST | jq '.rows[] | {domain: ."%reverse", backend: "\(.ToDomain):\(.ToPort)"}'
```

### Delete Reverse Proxy
```bash
# Get UUID first from searchReverseProxy
curl -sk --user "${OPNSENSE_KEY}:${OPNSENSE_SECRET}" \
  'https://10.10.0.1:8443/api/caddy/ReverseProxy/delReverseProxy/<UUID>' \
  -X POST
```

## Common Operations (Web UI)

### Add New Reverse Proxy Entry

1. Navigate to Services → Caddy Web Server → Reverse Proxy → Domains
2. Click "+" to add new domain
3. Fill in:
   - Domain: `app.kernow.io`
   - Description: Your description
   - DNS Challenge: Enabled
4. Save, then go to Handlers tab
5. Add handler pointing to backend: `10.20.0.40:31095`
6. Apply configuration

### View Logs
Navigate to Services → Caddy Web Server → Log File

## Configuration Examples

### Basic HTTP Backend
```caddyfile
app.kernow.io {
    reverse_proxy 10.20.0.40:30080
    tls internal
}
```

### With Headers
```caddyfile
app.kernow.io {
    reverse_proxy 10.20.0.40:30080 {
        header_up Host {upstream_hostport}
        header_up X-Real-IP {remote_host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto {scheme}
    }
    tls internal
}
```

### WebSocket Support
```caddyfile
app.kernow.io {
    reverse_proxy 10.20.0.40:30080 {
        transport http {
            keepalive 30s
        }
    }
    tls internal
}
```

### Load Balancing (Multiple Backends)
```caddyfile
app.kernow.io {
    reverse_proxy 10.20.0.40:30080 10.20.0.41:30080 {
        lb_policy round_robin
    }
    tls internal
}
```

## TLS Options

### Internal (Self-Signed)
```caddyfile
tls internal
```
- Generates self-signed certificate
- Browser will show warning (acceptable for internal use)

### Let's Encrypt (Requires DNS Challenge)
```caddyfile
tls {
    dns cloudflare {env.CF_API_TOKEN}
}
```
- Requires Cloudflare API token
- Certificate is publicly trusted

## Integration with AdGuard

For Caddy proxy to work, DNS must resolve to Caddy server:

1. Add AdGuard DNS rewrite: `<hostname>.kernow.io → 10.10.0.1`
2. Add Caddy reverse proxy entry
3. Test access

See: `runbooks/infrastructure/adguard-rewrite.md`

## Troubleshooting

### 502 Bad Gateway
- Backend not reachable
- Check: `curl http://<backend-ip>:<port>`

### SSL Certificate Error
- Using `tls internal` shows browser warning
- Add browser exception or use Let's Encrypt

### DNS Not Resolving
- AdGuard rewrite not configured
- Check: `dig <hostname>.kernow.io`

### Configuration Syntax Error
```bash
ssh root@10.10.0.1 "caddy validate --config /etc/caddy/Caddyfile"
```

## Current Entries

Query current Caddy configuration via API:
```bash
curl -sk --user "${OPNSENSE_KEY}:${OPNSENSE_SECRET}" \
  'https://10.10.0.1:8443/api/caddy/ReverseProxy/searchReverseProxy' \
  -X POST | jq '.rows[] | .FromDomain'
```

## Automation

For automated deployments, use the OPNsense API directly (see API Access section above).

The API workflow is:
1. Get credentials from Infisical
2. Add reverse proxy entry (get UUID)
3. Add handle with backend details
4. Reconfigure Caddy service

This can be scripted or integrated into deployment pipelines.
