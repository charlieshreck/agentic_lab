# Tailscale on OPNsense

## Overview

Tailscale provides secure remote access to all homelab networks via WireGuard-based mesh VPN. OPNsense acts as a subnet router, advertising internal networks to the Tailscale network.

## Architecture

```
Remote Device (Tailscale client)
        │
        ▼ (Tailscale mesh)
    Tailscale.com coordination
        │
        ▼
OPNsense (10.10.0.1) - Subnet Router
        │
        ├── 10.10.0.0/24 (Prod network)
        ├── 10.20.0.0/24 (Agentic network)
        └── 10.30.0.0/24 (Monitoring network)
```

## Components

| Component | Location | Purpose |
|-----------|----------|---------|
| os-tailscale plugin | OPNsense | Tailscale daemon + WireGuard |
| Tailscale Admin | login.tailscale.com | Device management, ACLs, DNS |
| Auth Key | Infisical | `/infrastructure/tailscale/AUTH_KEY` |

## Installation

### 1. Install Plugin

**Via GUI:**
- System → Firmware → Plugins → Search "tailscale" → Install

**Via MCP:**
```python
mcp__infrastructure__install_plugin(package_name="os-tailscale")
```

### 2. Generate Auth Key

1. Go to https://login.tailscale.com/admin/settings/keys
2. Click **"Generate auth key..."**
3. Configure:
   - Description: `opnsense-router`
   - Reusable: Enabled
   - Expiration: 90 days (or longer)
   - Tags: `tag:router` (optional)
4. Save key to Infisical:

```bash
/root/.config/infisical/secrets.sh set /infrastructure/tailscale AUTH_KEY "tskey-auth-..."
```

Or via MCP:
```python
mcp__infrastructure__set_secret(
    path="/infrastructure/tailscale",
    key="AUTH_KEY",
    value="tskey-auth-..."
)
```

### 3. Configure Tailscale

**Via GUI:**

1. **VPN → Tailscale → Settings:**
   - Enabled: Yes
   - Accept Routes: Yes (to receive routes from other nodes)
   - Exit Node: No (unless you want all traffic routed)

2. **VPN → Tailscale → Authentication:**
   - Login Server: `https://controlplane.tailscale.com` (for Tailscale.com)
   - Auth Key: Paste the key from step 2

3. **VPN → Tailscale → Subnets:**
   - Add: `10.10.0.0/24` (prod)
   - Add: `10.20.0.0/24` (agentic)
   - Add: `10.30.0.0/24` (monitoring)

4. Click **Apply**

**Via MCP:**
```python
# Configure settings and auth
mcp__infrastructure__set_tailscale_config(
    enabled=True,
    authkey="tskey-auth-...",
    login_server="https://controlplane.tailscale.com",
    accept_routes=True,
    advertise_exit_node=False,
    advertise_routes="10.10.0.0/24,10.20.0.0/24,10.30.0.0/24"
)

# Apply and start
mcp__infrastructure__reconfigure_tailscale()
mcp__infrastructure__start_tailscale()
```

### 4. Approve Routes in Tailscale Admin

1. Go to https://login.tailscale.com/admin/machines
2. Find OPNsense device
3. Click on it → Subnets section
4. Approve all three subnets

## DNS Configuration

By default, Tailscale clients use their local DNS. To use your homelab DNS (AdGuard) for split-DNS resolution:

1. Go to https://login.tailscale.com/admin/dns
2. Add nameserver: `10.10.0.1` (AdGuard)
3. Enable **"Override local DNS"**

### DNS Behavior

| Location | DNS Server | `outline.kernow.io` resolves to |
|----------|------------|--------------------------------|
| Home network | AdGuard (auto) | 10.10.0.90 (internal Traefik) |
| Remote + Tailscale DNS | AdGuard via Tailscale | 10.10.0.90 (internal) |
| Remote without Tailscale DNS | Local/Cloudflare | Cloudflare tunnel (external) |

**Recommendation:** Enable Tailscale DNS override for consistent internal resolution and ad-blocking on mobile.

## Verification

### Check Status

**Via MCP:**
```python
mcp__infrastructure__get_tailscale_status()
# Returns: {"status": "running", ...}

mcp__infrastructure__get_tailscale_config()
# Returns current settings, auth config, subnets
```

### Test Connectivity

From a Tailscale-connected device:
```bash
# Ping OPNsense
ping 10.10.0.1

# Ping a prod server
ping 10.10.0.6

# Ping agentic cluster
ping 10.20.0.40

# Test DNS (if Tailscale DNS enabled)
nslookup outline.kernow.io
```

### Tailscale Admin Console

- Devices: https://login.tailscale.com/admin/machines
- DNS: https://login.tailscale.com/admin/dns
- ACLs: https://login.tailscale.com/admin/acls
- Auth Keys: https://login.tailscale.com/admin/settings/keys

## Headscale (Self-Hosted Alternative)

Headscale is a self-hosted Tailscale coordination server. If you want to use Headscale instead of Tailscale.com:

1. Deploy Headscale server
2. Set Login Server to your Headscale URL:
   ```python
   mcp__infrastructure__set_tailscale_config(
       login_server="http://headscale.example.com:8080"
   )
   ```
3. Generate pre-auth key from Headscale

**Note:** Previously configured Headscale at `10.10.0.31:8080` was decommissioned.

## Troubleshooting

### Service Not Starting

```python
# Check status
mcp__infrastructure__get_tailscale_status()

# Restart service
mcp__infrastructure__restart_tailscale()

# Check logs (via SSH or console)
# /var/log/tailscale/tailscaled.log
```

### Device Not Appearing in Admin

- Verify auth key is valid (not expired)
- Check login server URL is correct
- Ensure plugin is enabled in settings

### Routes Not Working

1. Verify subnets are added in OPNsense
2. Verify subnets are approved in Tailscale admin
3. Check firewall rules allow Tailscale interface traffic

### DNS Not Resolving Internal Names

1. Verify Tailscale DNS is configured (admin → DNS)
2. Verify "Override local DNS" is enabled
3. Test: `nslookup kernow.io` should return 10.10.0.x

### API Returns 404

The MCP uses these API endpoints:
- `/tailscale/service/status` - Service status
- `/tailscale/settings/get|set` - General settings
- `/tailscale/authentication/get|set` - Auth key, login server
- `/tailscale/settings/add_subnet` - Add subnets

If 404, the plugin may need:
1. Reinstall: `mcp__infrastructure__reinstall_plugin("os-tailscale")`
2. GUI visit to initialize config files

## MCP Tool Reference

| Tool | Purpose |
|------|---------|
| `get_tailscale_status()` | Service running/stopped status |
| `get_tailscale_config()` | Current settings and auth config |
| `set_tailscale_config(...)` | Configure all settings |
| `start_tailscale()` | Start the service |
| `stop_tailscale()` | Stop the service |
| `restart_tailscale()` | Restart the service |
| `reconfigure_tailscale()` | Apply pending changes |

### set_tailscale_config Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `enabled` | bool | Enable/disable Tailscale |
| `authkey` | str | Tailscale auth key |
| `login_server` | str | Coordination server URL (empty for Tailscale.com) |
| `accept_routes` | bool | Accept routes from other nodes |
| `advertise_exit_node` | bool | Advertise as exit node |
| `advertise_routes` | str | Comma-separated CIDRs to advertise |

## Security Considerations

1. **Auth Key Expiration**: Keys expire - set calendar reminder to rotate
2. **ACLs**: Consider restricting which devices can access which subnets
3. **Exit Node**: Only enable if you want ALL traffic routed through home
4. **MagicDNS**: Tailscale assigns 100.x.x.x addresses - these bypass your ACLs

## Related Documentation

- [DNS Architecture](./dns-architecture.md) - Split-DNS setup
- [AdGuard Rewrite](./adguard-rewrite.md) - DNS rewrites
- [OPNsense Caddy Proxy](./caddy-proxy.md) - Internal reverse proxy
