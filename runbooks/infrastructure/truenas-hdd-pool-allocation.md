# TrueNAS HDD Pool Allocation Strategy

**Incident**: #618, #1401
**Date Created**: 2026-03-27
**Status**: Active

## Problem Statement

TrueNAS-HDD has two pools with inconsistent data allocation:
- **Taupo pool** (13.5TB used, 90.4% full): PBS backups (1.03TB) + Pleximetry (858GB) + unused datasets
- **Tekapo pool** (24GB used, 1.3% full): Only observability metrics (victoria-metrics, victoria-logs)

This leads to **critical capacity strain** on Taupo while Tekapo remains underutilized.

## Root Cause

No documented allocation policy was established when pools were created. Pleximetry (media library metadata, ephemeral-like timeseries) should have been on Tekapo with other observability data, not on Taupo with permanent backups.

## Intended Design

### Taupo Pool (Persistent, Long-Term)
**Purpose**: Permanent archival and backup data
- **pbs** (1.03TB): Proxmox Backup Server repositories — expected to grow with infrastructure backups
- **Deprecated**: Truro, MinIO (unused, can be purged)

**Target Utilization**: 60-70% (allows growth headroom)

### Tekapo Pool (Ephemeral/Monitoring)
**Purpose**: Observability and temporary data
- **victoria-metrics** (20.6GB): Timeseries metrics (retention-based growth)
- **victoria-logs** (3.2GB): Observability logs (retention-based growth)
- **pleximetry** (858GB): Media library indexing metadata (should migrate here)

**Target Utilization**: 30-40% (ephemeral data, frequent pruning)

## Migration Plan

### Phase 1: Update K8s Manifests (GitOps)
Update NFS mount paths to point from Taupo to Tekapo:

**Files to update:**
- `prod_homelab/kubernetes/applications/apps/filebrowser/deployment.yaml` (line 114)
- `prod_homelab/kubernetes/applications/apps/homepage/deployment.yaml` (line 299)

Change:
```yaml
# OLD
path: /mnt/Taupo/Pleximetry

# NEW
path: /mnt/Tekapo/Pleximetry
```

### Phase 2: Data Migration (Maintenance Window)
Execute during low-traffic period (e.g., 02:00-03:00 UTC):

**On TrueNAS-HDD (SSH: 10.10.0.103):**

1. **Pre-flight checks**:
   ```bash
   # Verify source and destination
   zfs list | grep -E 'Taupo|Tekapo'
   df -h /mnt/Taupo/Pleximetry /mnt/Tekapo
   ```

2. **Create destination dataset** (if not exists):
   ```bash
   zfs create Tekapo/Pleximetry
   chmod 755 /mnt/Tekapo/Pleximetry
   ```

3. **Perform rsync**:
   ```bash
   rsync -avz --progress /mnt/Taupo/Pleximetry/ /mnt/Tekapo/Pleximetry/
   ```

4. **Verify data integrity**:
   ```bash
   # Check file counts match
   find /mnt/Taupo/Pleximetry -type f | wc -l
   find /mnt/Tekapo/Pleximetry -type f | wc -l

   # Compare sizes
   du -sh /mnt/Taupo/Pleximetry
   du -sh /mnt/Tekapo/Pleximetry
   ```

5. **Old path cleanup** (after verification):
   ```bash
   # Backup old data for 1 week in case rollback needed
   zfs snapshot Taupo/Pleximetry@archive-2026-03-27

   # Then remove (DO NOT DELETE until new path stable for 1+ week)
   rm -rf /mnt/Taupo/Pleximetry/*
   ```

### Phase 3: K8s Restart
After manifests are synced and data migration complete:

```bash
# Force pod restart to pick up new NFS path
kubectl rollout restart deployment/filebrowser -n apps
kubectl rollout restart deployment/homepage -n apps

# Verify pods are running and accessing new path
kubectl logs -f deployment/filebrowser -n apps
kubectl exec -it -n apps deployment/filebrowser -- df -h /folder/hdd/Pleximetry
```

## Monitoring & Alerts

### Current Thresholds (2026-03-27)
- Taupo alert: 85% (TRIGGERED at 90.4%)
- Tekapo: No alerts configured

### Recommended Changes
1. **Lower Taupo threshold to 80%** — earlier warning for growth
2. **Add Tekapo monitoring** — if grows above 60%, investigate retention policies
3. **Document retention policies** for both pools:
   - Taupo: PBS backups retention (how many versions?)
   - Tekapo: Metrics retention (how many days of data?)

## Verification Checklist

After migration, verify:
- [ ] K8s manifests updated and applied (ArgoCD sync)
- [ ] Pleximetry data copied to Tekapo
- [ ] Old Taupo/Pleximetry directory cleaned
- [ ] Pods restarted and accessing new NFS path
- [ ] Filebrowser shows `/folder/hdd/Pleximetry` contents
- [ ] Homepage shows disk metrics from Pleximetry
- [ ] TrueNAS pool utilization: Taupo ~24%, Tekapo ~36%
- [ ] No data loss, no permission issues

## Lessons Learned

1. **Document pool allocation upfront** — design decisions must be in code/runbooks, not implicit
2. **Implement capacity monitoring** — set alerts at 60-70% to catch growth early
3. **Review pool usage quarterly** — prevent data creep and capacity surprises
4. **Tekapo should have compression enabled** — ZFS can save 10-15% on timeseries data

## Related Issues

- **Recurring Pattern**: TrueNAS-Media (Taranaki pool) also suffered similar saturation (93.2% at incident #162)
- **Future Prevention**: Create automated rebalancing logic or documented SOP for when pools approach 80%

## Rollback Plan

If migration fails:
1. Stop K8s pods: `kubectl scale deployment filebrowser -n apps --replicas=0`
2. Revert K8s manifests to point back to Taupo
3. Restart pods
4. Clean Tekapo/Pleximetry if partial data exists
5. Restore from snapshot: `zfs rollback Taupo/Pleximetry@archive-2026-03-27`

---

**Owner**: Infrastructure Team
**Last Updated**: 2026-03-27
**Next Review**: 2026-06-27 (quarterly capacity review)
