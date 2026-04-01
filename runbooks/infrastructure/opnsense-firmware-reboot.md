# OPNsense Routine Firmware Reboot

## Trigger
- Estate Patrol detects `needs_reboot: 1` in firmware status
- Pending package updates requiring reboot
- Crash log entries accumulating

## Impact
- OPNsense (10.10.0.1) is the network gateway for ALL traffic
- Reboot causes **full network outage** (~2-5 minutes):
  - All 3 K8s clusters lose external connectivity
  - DNS resolution (AdGuard) temporarily unavailable
  - Caddy reverse proxy offline
  - Cloudflare tunnels disconnect (auto-reconnect after reboot)
  - Tasmota devices may lose MQTT briefly
- Internal cluster-to-cluster traffic on same subnet unaffected during reboot

## Prerequisites
1. Schedule during low-traffic window (recommended: 02:00-04:00 UTC)
2. Verify no active Plex transcoding sessions: `plex_get_active_sessions`
3. Verify no active downloads: `transmission_list_torrents`, `sabnzbd_get_queue`
4. Ensure Velero daily backups have completed

## Procedure

### Via Web GUI (Recommended)
1. Navigate to `https://10.10.0.1` → System → Firmware → Status
2. Review pending updates
3. Click **Update** to apply updates
4. Confirm reboot when prompted
5. Wait 2-5 minutes for system to return

### Via SSH
```bash
sshpass -p 'H4ckwh1z' ssh -o StrictHostKeyChecking=no -o PubkeyAuthentication=no root@10.10.0.1
# From menu: option 5 (Reboot)
# Or: /usr/local/opnsense/scripts/firmware/update.sh
```

### Via API
```bash
API_KEY=$(/root/.config/infisical/secrets.sh get /infrastructure/opnsense API_KEY 2>/dev/null)
API_SECRET=$(/root/.config/infisical/secrets.sh get /infrastructure/opnsense API_SECRET 2>/dev/null)

# Apply pending updates + reboot
curl -sk -u "$API_KEY:$API_SECRET" \
  -X POST "https://10.10.0.1:8443/api/core/firmware/update"
```

## Post-Reboot Verification (wait 5 min, then check)
```bash
# 1. Ping gateway
ping -c 3 10.10.0.1

# 2. DNS resolution
nslookup tamar.kernow.io 10.10.0.1

# 3. Firmware status (needs_reboot should be 0)
# Check via estate patrol OPNsense script or MCP

# 4. Gatus endpoints recovering
# mcp__observability__gatus_get_failing_endpoints

# 5. Cluster DNS forwarding
KUBECONFIG=/root/.kube/config kubectl --context admin@homelab-prod run -it --rm dns-test --image=alpine --restart=Never -- nslookup google.com

# 6. Cloudflare tunnels reconnected
# Check Cloudflare dashboard or gatus external endpoints
```

## Crash Log Entries
- `crash_log_entries` is a cumulative counter that resets on reboot
- High counts (>1000) alone are not critical — they accumulate over uptime
- Only concerning if crashes are recent/frequent (check `/var/crash/` on OPNsense)

## Automation Notes
- Estate Patrol detects `needs_reboot=1` and escalates to human
- Reboot is NEVER automated — always requires human approval due to network-wide impact
- After reboot, next patrol sweep should show `needs_reboot=0`

## Related
- [opnsense-major-upgrade.md](opnsense-major-upgrade.md) — Major version upgrades (e.g., 25.7 → 26.1)
- CLAUDE.md DNS Architecture section — Split-DNS design

---
**Last verified**: 2026-04-01
**Owner**: Infrastructure team
