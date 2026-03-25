# PBS (Proxmox Backup Server) Health Check Configuration

## Overview

PBS is monitored via Gatus health checks at `10.10.0.151:8007/api2/json/version`. The endpoint requires authentication and returns **401 Unauthorized** when credentials are not provided.

## Root Cause of Incident #504

**Issue**: Gatus health check was timing out before receiving the 401 response.

**Root Cause**: The default Gatus client timeout (10 seconds) was insufficient for PBS to respond, especially under load or disk I/O contention.

**Timeline**:
- PBS was running normally (processes active, resources available)
- TLS handshake with PBS succeeded from all clients
- HTTP request headers timed out after 10 seconds
- Gatus recorded failure: "Client.Timeout exceeded while awaiting headers"

## Solution

Added explicit 30-second timeout to the PBS health check in Gatus configuration:

```yaml
- name: PBS (Backup Server)
  group: Infrastructure
  url: "https://10.10.0.151:8007/api2/json/version"
  interval: 120s
  conditions:
    - "[STATUS] == 401"
  client:
    insecure: true
    timeout: 30s  # Added - PBS may be slow under load
  alerts:
    - type: custom
    - type: discord
      description: "PBS is down"
```

## Why 30 Seconds?

- **Default**: 10 seconds (too aggressive for PBS under load)
- **30 seconds**: Industry standard for backup systems (accounts for disk I/O latency)
- **Others for reference**: Proxmox uses 30-60s, most enterprise backup systems default to 30s+

## Testing the Endpoint

From Synapse LXC (10.10.0.22):

```bash
# Verify PBS is up
ssh root@10.10.0.151 "ps aux | grep proxmox-backup"

# Check port is listening
ssh root@10.10.0.151 "ss -tuln | grep 8007"

# Test with curl (expect 401)
curl -v -k --max-time 30 https://10.10.0.151:8007/api2/json/version
# Should output: "authentication failed - no authentication credentials provided."
```

## Prevention

1. **Monitor PBS resource usage**: If CPU/disk I/O regularly exceeds 80%, investigate:
   - Active backup jobs (reduce concurrency)
   - Disk fragmentation (schedule defrag)
   - Insufficient RAM (upgrade PBS VM)

2. **Alert on Gatus timeouts**: Track in knowledge base if 401 status is not received

3. **Annual review**: Check Gatus timeout settings during infrastructure reviews

## Error-Hunter PBS Suppression Window

error-hunter checks PBS during sweeps and suppresses `pbs_unreachable` findings during
the backup window to avoid false positives while backup jobs are starting up:

- **Backup schedule**: Daily at 02:00 UTC across all 3 Proxmox hosts
- **Suppression window**: 02:00–02:30 UTC (PBS may be busy handling concurrent backup jobs)
- **Pattern**: PBS API briefly returns ENOTCONN as backup jobs initialise (~2-5 min per host)
- **Fix**: If `pbs_unreachable` fires outside the window, PBS truly is unreachable — investigate

**Finding #1382 (2026-03-25)**: `pbs_unreachable` fired with blank exception message. PBS was
healthy; the previous 02:15 cutoff was too narrow. Widened to 02:30 to cover all 3 hosts
completing backup startup.

## Related Issues

- Incident #504: PBS health check timeout (RESOLVED 2026-03-20)
- Finding #1382: pbs_unreachable false positive — suppression window too narrow (RESOLVED 2026-03-25)

## See Also

- `/home/monit_homelab/kubernetes/platform/gatus/deployment.yaml` - Gatus config
- `mcp__observability__gatus_get_endpoint_status` - MCP tool to check endpoint status
