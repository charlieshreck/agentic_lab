# OPNsense Major Version Upgrade Runbook

## Overview
OPNsense major version upgrades (e.g., 25.7 → 26.1) require careful planning and coordination due to potential breaking changes and the mandatory reboot required.

**Current State (Feb 28, 2026):**
- Running: 25.7.11_9 (Visionary Viper) — **End of Life**
- Available: 26.1 (major upgrade, 1.2GB download)
- Impact: Full firewall reboot required

## When to Upgrade

Upgrade to a new major version when:
1. **Current version is EOL** and no longer receiving security patches
2. **Planned maintenance window exists** (30-60 min downtime acceptable for prod network)
3. **Configuration backup is current** (via OPNsense web GUI)
4. **Team is coordinated** (notify on-call, pause critical operations if needed)

**Current Status:** 25.7 is EOL but still functional. Upgrade is recommended but not urgent. Schedule for planned maintenance window.

## Prerequisites

1. **Backup current configuration**
   ```bash
   # Via SSH to 10.10.0.1
   sshpass -p 'H4ckwh1z' ssh -o StrictHostKeyChecking=no root@10.10.0.1

   # From web GUI: System → Configuration → Backups
   # Or via API: POST /api/core/system/config/backup
   ```

2. **Document current state**
   - Firewall rules (count, patterns)
   - DNS rewrites (AdGuard entries)
   - NAT rules
   - DHCP leases
   - Active Tailscale state
   - Caddy reverse proxy configuration

3. **Notify stakeholders**
   - Cluster operators (will lose external connectivity)
   - Media team (Plex may be unreachable)
   - Internal users (15-30 min downtime)

## Upgrade Procedure

### Option 1: Web GUI (Recommended)
1. Log in to OPNsense web GUI (https://10.10.0.1)
2. Navigate to **System → Firmware → Status**
3. Click **Upgrade to 26.1** button
4. Confirm: "Upgrade major version"
5. Wait for download + installation (~5 min)
6. Firewall will reboot automatically
7. Wait for network to stabilize (~2 min after reboot)

### Option 2: SSH Console
1. SSH to 10.10.0.1: `sshpass -p 'H4ckwh1z' ssh root@10.10.0.1`
2. Type option **12** from main menu
3. Enter **26.1** when prompted
4. Confirm upgrade
5. Wait for completion and reboot

### Option 3: CLI API
```bash
# Get upgrade status
curl -s -X GET https://10.10.0.1:8443/api/core/firmware/upgrade_status \
  -H 'Authorization: ApiKey <API_KEY>' | jq

# Trigger upgrade
curl -s -X POST https://10.10.0.1:8443/api/core/firmware/upgrade \
  -H 'Authorization: ApiKey <API_KEY>' \
  -H 'Content-Type: application/json' \
  -d '{"version":"26.1"}'
```

## Post-Upgrade Verification

After reboot completes (~5 min), verify:

```bash
# 1. Check firmware version
curl -s -X GET https://10.10.0.1:8443/api/core/firmware/status \
  -H 'Authorization: ApiKey <API_KEY>' | jq '.product.product_version'
# Expected: 26.1.x

# 2. Test DNS resolution (AdGuard)
nslookup tamar.kernow.io 10.10.0.1

# 3. Test external connectivity (Cloudflare tunnel)
curl -s -I https://tamar.kernow.io/api/health

# 4. Check cluster coredns → OPNsense forwarding
kubectl run -it --rm debug --image=alpine --restart=Never -- \
  sh -c 'apk add curl && curl -I https://tamar.kernow.io/api/health'

# 5. Verify all services are healthy
# - Check Caddy reverse proxy is listening on 80/443
# - Check Tailscale is connected (if enabled)
# - Spot-check 2-3 key DNS rewrites in AdGuard

# 6. Monitor for alerts
# - Check AlertManager for any firing alerts
# - Tail error-hunter logs for anomalies
```

## Breaking Changes (25.7 → 26.1)

Before upgrading, review:
- [OPNsense 26.1 Migration Notes](https://docs.opnsense.org/releases/26.1.html)
- Possible changes to firewall rule syntax
- Changes to plugin compatibility
- DNS/DHCP configuration differences

**Known Issues:**
- (Add any org-specific issues discovered during upgrade)

## Rollback Plan

If upgrade fails or causes issues:

1. **Boot into single-user mode** (Proxmox console)
2. **Restore backup configuration**
   - Access via SSH in single-user
   - Copy backup config to `/conf/`
   - Reboot normally

**Note:** Full rollback to 25.7 is not supported after 26.1 install. Backup BEFORE upgrade.

## Runbook Maintenance

- **Last verified**: Feb 28, 2026
- **Next review**: Quarterly or after OPNsense 27.x becomes available
- **Owner**: Infrastructure team

---

## Related

- [OPNsense Official Docs](https://docs.opnsense.org/)
- `/home/agentic_lab/runbooks/infrastructure/` — other infrastructure runbooks
- [CLAUDE.md DNS Architecture](../../CLAUDE.md) — DNS split-stack design
