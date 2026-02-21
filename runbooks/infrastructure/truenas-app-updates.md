# TrueNAS App Updates

## Overview

TrueNAS SCALE periodically notifies when application updates are available through the Apps dashboard. This runbook covers how to safely assess, plan, and execute app updates on TrueNAS instances.

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | TrueNAS app updates available |
| **Severity** | INFO (informational, not urgent) |
| **Source** | TrueNAS SCALE monitoring |
| **Frequency** | Periodic (weekly/monthly depending on update schedule) |
| **Action** | Review, plan, and update at convenient maintenance window |

## Current App Inventory

TrueNAS instances in the homelab:

| Instance | Network | Purpose | Apps |
|----------|---------|---------|------|
| **truenas-hdd** | 10.10.0.103 (prod) + 10.40.0.10 (NFS) | Backup storage | Garage, PBS, others |
| **truenas-media** | 10.20.0.100 (agentic) | Media SSD storage | Media apps |

## Garage Update Policy

**Garage** is the highest-priority app to maintain because:
- Used as backend for **Velero** backups (all 3 clusters)
- Used as backend for **Backrest** restic repositories
- Critical to disaster recovery

### Update Strategy for Garage

1. **Non-blocking**: Garage updates are NOT immediately critical if functioning properly
2. **Planned maintenance**: Schedule updates during:
   - Low backup activity window (off-peak hours)
   - NO active cluster backups in progress
   - NO active Backrest jobs running
3. **Notify stakeholders**: Alert users if external systems depend on Garage
4. **Test after update**: Verify S3 API responds and existing buckets remain accessible

## Pre-Update Checklist

Before updating ANY app on TrueNAS:

### 1. Check Current Status

```bash
# Via TrueNAS UI
# Navigate to: Apps → Installed Applications → [app-name]
# Note: Current version and available version

# Via MCP (if available)
truenas-mcp: truenas_list_instances()
```

### 2. Review Release Notes

- Visit the app's project repository (usually linked in TrueNAS)
- Check for breaking changes, new configuration requirements
- Note any data migration steps
- Example for Garage: https://garagehq.deuxfleurs.fr/

### 3. Verify Dependencies

**For Garage specifically:**
```bash
# Check if Velero backups are running
kubectl get pods -n velero | grep backup

# Check if Backrest jobs are active
# (access Backrest UI or check logs)

# Verify no recent backup failures
mcp__observability__query_metrics_instant(query='velero_backup_failure_total')
```

### 4. Have a Rollback Plan

- Note the current app version
- Understand how to revert if update fails
- For Garage: Data is persisted in ZFS dataset and survives app restart

## Update Procedures

### Via TrueNAS Web UI (Recommended)

1. Navigate to **Apps** → **Installed Applications**
2. Click the app (e.g., **garage**)
3. Click **Update** button
4. Review new version and confirm changes
5. Click **Update Application**
6. Monitor logs during update:
   - App will stop, upgrade, and restart
   - Watch for errors in the output

### Via Kubernetes CLI (Advanced)

```bash
# If you have access to the k3s instance on TrueNAS
# (not recommended for most users)

k3s kubectl rollout restart -n ix-garage deployment/garage

# For custom chart updates, use Helm:
# (check TrueNAS Helm repository)
```

## Post-Update Verification

### For Garage Specifically

**Step 1: Check if app is running**
```bash
# Via TrueNAS UI
# Apps → garage → Status should show "Running"

# Or check health endpoint
curl -I http://10.10.0.103:30188
# Expected: HTTP/1.1 403 Forbidden (anonymous request blocked)
```

**Step 2: Verify S3 API**
```bash
# Test with AWS CLI
export AWS_ACCESS_KEY_ID=$(infisical secrets get ACCESS_KEY_ID --path=/backups/garage --plain)
export AWS_SECRET_ACCESS_KEY=$(infisical secrets get SECRET_ACCESS_KEY --path=/backups/garage --plain)

aws s3 ls --endpoint-url=http://10.10.0.103:30188
# Should list buckets: velero-prod, velero-agentic, velero-monit, backrest
```

**Step 3: Check buckets are still accessible**
```bash
aws s3 ls s3://velero-prod --endpoint-url=http://10.10.0.103:30188 --max-items 5
# Should list recent backups
```

**Step 4: Check Admin API**
```bash
ADMIN_TOKEN=$(infisical secrets get ADMIN_TOKEN --path=/backups/garage --plain)

curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://10.10.0.103:30190/v1/status | jq .
# Should show node status and health
```

## Common Update Issues

### 1. App Stops Responding After Update

**Symptom**: S3 API returns 503 or connection refused

**Diagnosis**:
- Check app logs in TrueNAS UI
- Verify storage pool (Taupo) is healthy
- Check free disk space

**Recovery**:
1. Wait 60 seconds for app to fully start
2. If still failing, click **Stop** then **Start** in TrueNAS UI
3. Check logs for specific errors
4. If necessary, revert to previous version (TrueNAS rollback feature)

### 2. Data Inaccessible After Update

**Symptom**: Buckets exist but give 500 errors on access

**Diagnosis**:
```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://10.10.0.103:30190/v1/key | jq
# Check if API keys still exist and are valid
```

**Recovery**:
1. Check if Garage underwent a major version bump (rare)
2. Review release notes for migration steps
3. Contact Garage maintainers if data loss suspected
4. Restore from TrueNAS snapshot if necessary

### 3. Velero Backups Fail After Update

**Symptom**: Velero reports connection errors to Garage

**Diagnosis**:
```bash
kubectl logs -n velero -l app.kubernetes.io/name=velero | tail -50
# Look for S3 connection errors
```

**Recovery**:
1. Verify Garage is responding (see Post-Update Verification)
2. Check Velero credentials are correct (no API key rotation)
3. Verify firewall allows traffic from clusters to 10.10.0.103:30188
4. Re-test Velero backup manually: `kubectl apply -f velero-manual-backup.yaml`

## Scheduling Updates

### Recommended Update Cadence

| App | Frequency | Risk | Policy |
|-----|-----------|------|--------|
| **Garage** | Monthly | Low (data persisted) | Update during maintenance window, verify after |
| **PBS** | As-needed | Low | Updates rarely cause issues |
| **Other apps** | Ad-hoc | Varies | Review release notes before updating |

### Maintenance Window Template

**Monthly TrueNAS App Update Window**
- **When**: 2nd Sunday of month, 02:00 UTC (midnight EST)
- **Duration**: 30-60 minutes
- **Affected**: Garage (backup system), PBS (snapshots)
- **Impact**: Backups may fail if running during update; queued backups resume after restart
- **Communication**: Notify ops team 24 hours in advance

## Automation & Monitoring

### Alert Suppression (Optional)

If the "app updates available" alert is too noisy:
1. Document suppression reason in Runbook
2. Set AlertManager silence for 4 weeks
3. Re-enable before silence expires

### Future Enhancements

- [ ] Automated update testing in non-prod environment
- [ ] Velero backup pre-update snapshot
- [ ] Post-update health check automation

## Related Runbooks

- `/home/agentic_lab/runbooks/infrastructure/garage-operations.md` — Garage administration
- `/home/agentic_lab/runbooks/infrastructure/velero-operations.md` — Velero backup procedures
- `/home/agentic_lab/runbooks/infrastructure/backup-overview.md` — Backup strategy overview
- `/home/agentic_lab/runbooks/infrastructure/pbs-operations.md` — PBS backup server

## Infisical References

| Path | Keys | Purpose |
|------|------|---------|
| `/infrastructure/truenas-hdd` | API_KEY | TrueNAS API access |
| `/backups/garage` | ACCESS_KEY_ID, SECRET_ACCESS_KEY, ADMIN_TOKEN | Garage credentials |

## Troubleshooting Commands

### Get TrueNAS app status via SSH (admin user only)

```bash
# SSH to TrueNAS (FreeBSD)
ssh -l admin 10.10.0.103

# List k3s namespaces
/usr/local/bin/k3s kubectl get namespaces

# Check ix-garage namespace
/usr/local/bin/k3s kubectl get all -n ix-garage

# View app deployment logs
/usr/local/bin/k3s kubectl logs -n ix-garage -l app=garage --tail=50
```

### Manual rollback (if available)

TrueNAS may offer a "Rollback" button in the app details page. If not:
1. Uninstall the app
2. Reinstall previous version from TrueNAS catalog
3. Restore data from snapshot if needed
