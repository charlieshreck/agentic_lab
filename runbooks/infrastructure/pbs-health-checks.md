# PBS Health Check Monitoring

**Created**: 2026-03-20
**Updated**: 2026-03-20
**Status**: Active

## Overview

Proxmox Backup Server (PBS) at 10.10.0.151:8007 requires special handling for health monitoring because it runs scheduled backup operations that cause slow API responses.

## Scheduled Backup Window

**Time**: Daily 02:00 UTC
**Duration**: ~50 minutes (02:00-02:50 UTC)
**Nodes**: Ruapehu (10.10.0.10) and Pihanga (10.10.0.20)
**Operation**: `vzdump` backup operations
**Impact**: PBS API response time increases to 10-30 seconds under backup load

## Health Check Configuration

**Endpoint**: `https://10.10.0.151:8007/api2/json/version`
**Expected Status**: 401 (Unauthorized - correct for unauthenticated API access)
**Check Interval**: 120 seconds
**Timeout**: 60 seconds (tuned to accommodate backup window latency)

### Gatus Configuration

```yaml
- name: PBS (Backup Server)
  group: Infrastructure
  url: "https://10.10.0.151:8007/api2/json/version"
  interval: 120s
  conditions:
    - "[STATUS] == 401"
  client:
    insecure: true
    timeout: 60s  # Critical: must be >30s to handle backup-window latency
  alerts:
    - type: custom
    - type: discord
      description: "PBS is down"
```

**Location**: `/home/monit_homelab/kubernetes/platform/gatus/deployment.yaml` (lines 215-227)

## Expected Behavior During Backups (02:00-02:50 UTC)

- **API Response Time**: 10-30 seconds
- **Gatus Health Check**: Still succeeds (timeout: 60s accommodates this)
- **Alerts**: None triggered (transient slowness is expected)
- **False Positives**: Prevented by 60s timeout

## Timeout History

| Date | Timeout | Issue | Resolution |
|------|---------|-------|-------------|
| Pre-2026-03-20 | 30s | False positives during backup window | Increased to 60s |
| 2026-03-20+ | 60s | Accommodates backup-time latency | Active |

## Troubleshooting

**If PBS health checks are failing outside the 02:00-02:50 window:**

1. Check PBS service status directly:
   ```bash
   curl -k https://10.10.0.151:8007/api2/json/version
   ```
   Should return 401.

2. Check PBS VM status:
   ```bash
   # From Synapse (10.10.0.22)
   ssh root@10.10.0.151 "proxmox-backup-proxy --version"
   ```

3. Check Proxmox Pihanga (10.10.0.20) for backup failures:
   - Access Proxmox web UI: https://10.10.0.20:8006
   - Check "Tasks" tab for failed backups

4. Check network connectivity:
   ```bash
   timeout 5 curl -k -v https://10.10.0.151:8007/api2/json/version
   ```

## Alert Routing

- **Gatus Alert**: Custom webhook to LangGraph incident broker (10.20.0.40:30800)
- **Discord**: Configured in Gatus alerting (requires webhook URL in Infisical)
- **Failure Threshold**: 3 consecutive failures
- **Success Threshold**: 2 consecutive successes to resolve

## References

- **PBS Documentation**: https://pbs.proxmox.com
- **Gatus Configuration**: `/home/monit_homelab/kubernetes/platform/gatus/deployment.yaml`
- **Incident #504**: Transient timeout during backup window (resolved 2026-03-20, commit c5567b0)
- **Backup Schedule**: Both Ruapehu and Pihanga nodes run vzdump at 02:00 UTC daily
