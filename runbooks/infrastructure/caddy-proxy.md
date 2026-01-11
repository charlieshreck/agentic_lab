# Caddy Reverse Proxy Configuration

## Overview
Caddy serves as the reverse proxy for internal-only services on the homelab network. It runs on the Unbound server (10.10.0.1) and handles TLS termination for internal services.

## Location
- Server: 10.10.0.1 (Unbound/DNS server)
- Config: `/etc/caddy/Caddyfile`
- Service: `systemctl status caddy`

## Common Operations

### Add New Reverse Proxy Entry

1. SSH to Caddy server:
```bash
ssh root@10.10.0.1
```

2. Edit Caddyfile:
```bash
nano /etc/caddy/Caddyfile
```

3. Add entry:
```caddyfile
<hostname>.kernow.io {
    reverse_proxy <backend-ip>:<port>
    tls internal
}
```

4. Reload Caddy:
```bash
systemctl reload caddy
```

5. Verify:
```bash
curl -k https://<hostname>.kernow.io
```

### Remove Reverse Proxy Entry

1. Edit Caddyfile and remove the block
2. Reload: `systemctl reload caddy`

### Check Current Configuration

```bash
ssh root@10.10.0.1 "cat /etc/caddy/Caddyfile"
```

### View Caddy Logs

```bash
ssh root@10.10.0.1 "journalctl -u caddy -f"
```

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

Query current Caddy configuration to see all proxied services:
```bash
ssh root@10.10.0.1 "grep -E '^\S+\.kernow\.io' /etc/caddy/Caddyfile"
```

## Automation

Consider using `caddy-mcp` (if available) or shell script for programmatic updates.
