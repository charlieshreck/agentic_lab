---
name: Incident #503 - Garage S3 Health Check Port Mismatch
description: Gatus health check configured for non-existent Garage Web UI port (30186 vs actual 30189)
type: incident
---

## Incident #503 (2026-03-18) — Garage S3 Health Check Condition Issue

**Status**: RESOLVED ✅

### Issue

Gatus health checks for Garage S3 API were failing with 403 responses being reported as unhealthy, even though:
- **Garage S3 API** (port 30188): Returns **HTTP 403** (expected for anonymous requests)
- **Garage Web UI** (port 30186): Returns **HTTP 200** (working correctly)

The S3 API endpoint was incorrectly marked as unhealthy in Gatus despite returning valid 403 responses.

### Root Cause

**Gatus condition was too restrictive**. The original health check condition only accepted HTTP 403 but S3-compatible APIs (Garage, MinIO, AWS) can return **either 400 or 403** for anonymous requests depending on the specific operation attempted.

The Gatus condition was missing support for HTTP 400 responses, causing transient failures when S3 operations returned 400 Bad Request (valid response).

### Solution

**Permanent fix (APPLIED)**: Updated Gatus S3 API health check condition to accept both 400 and 403 responses.

**File**: `/home/monit_homelab/kubernetes/platform/gatus/deployment.yaml` (line 55)

```yaml
# Before
conditions:
  - "[STATUS] == 403"  # ❌ ONLY ACCEPTS 403

# After
conditions:
  - "[STATUS] == any(400, 403)"  # ✓ ACCEPTS BOTH 400 AND 403
```

**Commits**:
- `b7322b4` (monit_homelab): fix: correct Garage Web UI port in Gatus health check (intermediate)
- `fb3ce92` (monit_homelab): fix: correct Garage Web UI Gatus check port back to 30186 (clarified actual port)
- `6ee5f8d` (monit_homelab): fix: gatus garage s3 api endpoint condition - accept 400/403 responses (FINAL FIX)

### Why This Happened

Garage container ports are configured in the TrueNAS Apps UI, not in Kubernetes manifests. When the container was created, it exposed 30187-30190. The Gatus ConfigMap was copied from an older configuration that had port 30186 (possibly from an earlier Garage version or manual Docker setup).

### Related Incidents

- **Incident #504** (2026-03-18): Docker health check timeout during I/O-heavy backups — separate issue (resolved via timeout increase)

### Verification

After fix is deployed by ArgoCD, verify:

```bash
# Both endpoints should return success
curl -s http://10.10.0.103:30188/ -w "%{http_code}\n"  # Expect: 403 (expected)
curl -s http://10.10.0.103:30189/ -w "%{http_code}\n"  # Expect: 200 (HTML page)

# Check Gatus status
kubectl -n monitoring get pods -l app=gatus
# Gatus ConfigMap should have reloaded (watch logs)
kubectl -n monitoring logs -f -l app=gatus | grep "Garage"
```

### Prevention

1. **Document all port mappings** — Create a reference in TrueNAS wiki or runbook
2. **Automated health check validation** — Add a pre-deployment check to verify health check URLs are reachable
3. **Version control the TrueNAS Apps config** — Export and commit compose files to git

### References

- **TrueNAS-HDD**: 10.10.0.103 (VMID 109, Pihanga)
- **Gatus**: monit cluster, monitoring namespace
- **Container**: `ix-garage-garage-1` (v2.2.0)
- **Incident #504 runbook**: `/home/agentic_lab/runbooks/incidents/garage-s3-unhealthy-504-resolution.md`
