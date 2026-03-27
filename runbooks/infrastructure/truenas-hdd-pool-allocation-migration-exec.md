# TrueNAS HDD Pleximetry Migration - Execution Log

**Investigation**: Incident #618, #1401 (Taupo pool 90.4% full)
**Date Started**: 2026-03-27T15:45Z
**Status**: In Progress (Phase 2 - Data Migration)

## Completed Actions (Phase 1 & Phase 1.5)

✅ **Phase 1: Analysis & Documentation**
- Identified root cause: Pleximetry (858GB) misallocated to overcrowded Taupo pool
- Created pool allocation strategy runbook: `truenas-hdd-pool-allocation.md`

✅ **Phase 1.5: GitOps Updates**
- Updated K8s manifests (prod_homelab):
  - `kubernetes/applications/apps/filebrowser/deployment.yaml` (commit: f8609a4)
  - `kubernetes/applications/apps/homepage/deployment.yaml` (commit: f8609a4)
  - Changed NFS path: `/mnt/Taupo/Pleximetry` → `/mnt/Tekapo/Pleximetry`
- Created runbook documenting allocation strategy (agentic_lab commit: 61384f8)
- **Status**: Both commits pushed to main branches. ArgoCD will auto-sync in 3-5 minutes.

✅ **Phase 1.75: TrueNAS Preparation**
- Created destination dataset: `Tekapo/Pleximetry`
- Mount point ready at: `/mnt/Tekapo/Pleximetry`
- Inherited compression (LZ4) and settings from parent pool

## Next Steps (Phase 2 - DATA MIGRATION)

### Execution Checklist

The following steps must be completed **before pods restart** (which happens on ArgoCD sync):

1. **SSH to TrueNAS-HDD** (10.10.0.103):
   ```bash
   ssh root@10.10.0.103
   ```

2. **Verify both paths exist**:
   ```bash
   ls -lh /mnt/Taupo/Pleximetry | head -10
   ls -lh /mnt/Tekapo/Pleximetry
   ```

3. **Execute rsync migration**:
   ```bash
   # Full copy with verbose progress
   rsync -avz --progress /mnt/Taupo/Pleximetry/ /mnt/Tekapo/Pleximetry/

   # Expected output: 858GB transfer
   # Estimated time: 30-60 minutes depending on disk I/O
   ```

4. **Verify integrity** (CRITICAL before cleanup):
   ```bash
   # Compare file counts
   SOURCE_COUNT=$(find /mnt/Taupo/Pleximetry -type f | wc -l)
   DEST_COUNT=$(find /mnt/Tekapo/Pleximetry -type f | wc -l)
   echo "Source files: $SOURCE_COUNT"
   echo "Dest files: $DEST_COUNT"
   [ "$SOURCE_COUNT" = "$DEST_COUNT" ] && echo "✅ File counts match" || echo "❌ MISMATCH!"

   # Compare directory sizes
   du -sh /mnt/Taupo/Pleximetry
   du -sh /mnt/Tekapo/Pleximetry
   ```

5. **Create safety snapshot** (rollback protection):
   ```bash
   zfs snapshot Taupo/Pleximetry@migration-2026-03-27
   ```

6. **Clean old path** (ONLY after verification):
   ```bash
   # ⚠️ DO NOT execute until new path is verified in prod for 24+ hours
   rm -rf /mnt/Taupo/Pleximetry/*
   ```

7. **Wait for ArgoCD sync**:
   - ArgoCD will auto-sync in 3-5 minutes (if not already synced)
   - Verify: `kubectl get applications -n argocd | grep app-of-apps`

8. **Verify pods restart**:
   ```bash
   kubectl rollout status deployment/filebrowser -n apps --timeout=5m
   kubectl rollout status deployment/homepage -n apps --timeout=5m
   ```

9. **Final verification**:
   ```bash
   # Check pod logs for mount success
   kubectl logs -f deployment/filebrowser -n apps | grep -i pleximetry

   # Verify NFS mount is working
   kubectl exec -it -n apps deployment/filebrowser -- df -h /folder/hdd/Pleximetry
   kubectl exec -it -n apps deployment/filebrowser -- ls -la /folder/hdd/Pleximetry | head -20
   ```

### Timeline
- **Start migration**: 2026-03-27 after business hours (recommend 22:00-02:00 UTC)
- **Estimated duration**: 1-2 hours (858GB transfer + verification)
- **Cutover window**: 5-10 minutes (ArgoCD sync + pod restart)
- **Monitoring period**: 24 hours (before deleting old data)

### Rollback Plan (if anything goes wrong)

1. **Stop pods**:
   ```bash
   kubectl scale deployment filebrowser -n apps --replicas=0
   kubectl scale deployment homepage -n apps --replicas=0
   ```

2. **Revert manifests**:
   ```bash
   git -C prod_homelab revert f8609a4
   git -C prod_homelab push origin main
   # Wait for ArgoCD sync
   ```

3. **Restore TrueNAS snapshot**:
   ```bash
   zfs rollback Taupo/Pleximetry@migration-2026-03-27
   ```

4. **Verify old path**:
   ```bash
   ls -lh /mnt/Taupo/Pleximetry | head -10
   ```

5. **Restart pods**:
   ```bash
   kubectl scale deployment filebrowser -n apps --replicas=1
   kubectl scale deployment homepage -n apps --replicas=1
   ```

## Success Criteria

✅ Migration complete when:
- [x] Tekapo/Pleximetry dataset created
- [ ] Pleximetry data rsync'd to Tekapo (858GB)
- [ ] File counts and sizes match between source and destination
- [ ] ArgoCD synced K8s manifests to prod cluster
- [ ] Filebrowser and Homepage pods running and accessing new path
- [ ] No data loss, no permission errors in pod logs
- [ ] TrueNAS pool utilization: Taupo ~24%, Tekapo ~36%

## Monitoring

Post-migration, monitor:
- **Taupo utilization**: Should drop from 90.4% → 24%
- **Tekapo utilization**: Should rise from 1.3% → 36%
- **Pod access**: Both filebrowser and homepage should show data via `/folder/hdd/Pleximetry`
- **NFS mounts**: Verify no stale mount issues
- **Storage alerts**: Taupo alert should clear (below 80% threshold)

---

**Owner**: Infrastructure Team / On-call Engineer
**Created**: 2026-03-27 Claude AI Investigation
**Execution Approval Required**: Yes (manual TrueNAS SSH work)
