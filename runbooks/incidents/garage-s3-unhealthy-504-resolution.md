# Incident #504 Resolution: Garage S3 Docker Health Check Unhealthy

**Date**: 2026-03-18
**Incident**: Gatus health check failed for Garage S3 API (context deadline exceeded)
**Root Cause**: Docker health check timeout (5s) exceeded during Garage gossip protocol handshake
**Status**: RESOLVED

## Issue Summary

Garage container (ix-garage-garage-1) on TrueNAS-HDD (10.10.0.103) becomes marked as **UNHEALTHY** during high I/O operations (backups, gossip sync).

- Container Status: UP but UNHEALTHY (marked by Docker health check)
- Health Check Timeout: 5s (immutable, cannot be updated without recreating)
- API Ports: 30186 (web UI), 30187 (admin), 30188 (S3), 30189 (s3-api), 30190 (metric)
- No actual data loss or data unavailability — API hangs at TCP accept

## Root Cause

1. Garage performs gossip protocol handshakes with other nodes
2. During high I/O operations (backups, snapshots), gossip handshakes exceed 5s
3. Docker health check times out while waiting for HTTP response
4. Container marked UNHEALTHY by Docker even though it's functional
5. This is NOT a container crash — the container continues running

## Diagnosis

```bash
# SSH to TrueNAS-HDD
sshpass -p 'H4ckwh1z' ssh root@10.10.0.103

# Check container status
docker ps | grep garage
# Output: ix-garage-garage-1 ... (unhealthy)

# View logs
docker logs ix-garage-garage-1 --tail 20

# Test connectivity (will hang without timeout)
timeout 3 curl http://localhost:30188/ 2>&1
# Result: Connection hangs, then timeout after 3s
```

## Permanent Fix

**Option 1: Increase Docker Health Check Timeout (RECOMMENDED)**

1. Open TrueNAS Web UI: https://10.10.0.103/
2. Navigate to **Apps** → **Installed** → **garage**
3. Click **Edit** on the Garage app
4. Expand **Container Configuration**
5. Find **Health Check Timeout** setting
6. Change from **5s** to **30s** (or higher)
7. Save and apply

This requires removing and re-adding the app container (no data loss, only config change).

**Option 2: Disable Health Check (TEMPORARY)**

Same steps as Option 1, but disable the health check entirely.
**Not recommended** — health checks catch real failures.

**Option 3: Restart Container (TEMPORARY)**

```bash
docker restart ix-garage-garage-1
```

This clears the UNHEALTHY status temporarily, but will recur during next high-I/O operation.

## Monitoring

Gatus endpoint **Garage S3 API** at `http://10.10.0.103:30188` expects:
- Status: **403** (anonymous request rejection)
- Timeout: **60s** (from Gatus config)

After fix, this should respond within 1-2s.

## Prevention

1. **Schedule backups during low-activity periods** (e.g., 02:00 UTC)
2. **Monitor I/O wait** on TrueNAS-HDD (use ntopng or Beszel agent)
3. **Set up alerts** if I/O wait exceeds 30% for >5 minutes
4. **Upgrade Garage** if newer version fixes gossip timeout issue

## References

- Incident: #504 (2026-03-18)
- Garage Version: v2.2.0 (as of this incident)
- Related Gatus Config: `/home/monit_homelab/kubernetes/platform/gatus/deployment.yaml:54-66`
- TrueNAS-HDD: 10.10.0.103 (VMID 109 on Pihanga)

## Related Knowledge

- **Memory Entry**: Incident #504 in `/root/.claude/projects/-home/memory/MEMORY.md`
- **Architecture**: TrueNAS-HDD stores Garage S3 as Docker app (managed via Apps UI)
- **Monitoring**: Gatus checks endpoint every 60s, custom alert via LangGraph at 10.20.0.40:30800
