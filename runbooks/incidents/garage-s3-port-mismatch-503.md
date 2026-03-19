---
name: Incident #503 - Garage S3 Health Check Port Mismatch
description: Gatus health check configured for non-existent Garage Web UI port (30186 vs actual 30189)
type: incident
---

## Incident #503 (2026-03-18) — Garage S3 Health Check Port Mismatch

**Status**: RESOLVED

### Issue

Gatus health checks for Garage S3 were failing:
- **Garage S3 API** (port 30188): **HTTP 403** — Expected, working correctly
- **Garage Web UI** (port 30186): **Connection refused** — Port doesn't exist

Both endpoints marked unhealthy in Gatus monitoring dashboard.

### Root Cause

**Port mismatch in Gatus configuration**. The Garage Docker container exposes ports via TrueNAS Apps:
- 30187: Cluster communications (netapp)
- 30188: S3 API ✓
- **30189**: Web UI (nginx)
- 30190: Admin API

But Gatus was configured to check port **30186** for the Web UI, which doesn't exist on the container.

### Solution

**Permanent fix (APPLIED)**: Corrected Gatus ConfigMap port mapping.

**File**: `/home/monit_homelab/kubernetes/platform/gatus/deployment.yaml` (line 71)

```yaml
# Before
- name: Garage Web UI
  url: "http://10.10.0.103:30186"  # ❌ WRONG PORT

# After
- name: Garage Web UI
  url: "http://10.10.0.103:30189"  # ✓ CORRECT PORT
```

**Commits**:
- `b7322b4` (monit_homelab): fix: correct Garage Web UI port in Gatus health check (30186 -> 30189)
- `6a2c58c` (parent): chore: update monit_homelab submodule (Gatus Garage S3 port fix)

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
