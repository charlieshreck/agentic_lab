# Velero Backup CPU Spike (Transient)

**Alert**: CPU spike on worker nodes (threshold: 80%) during 02:00-03:30 UTC window

**Root Cause**: Daily Velero backup jobs (`velero/daily-backup-*`) run two phases:
1. **PodVolumeBackup** (02:00-03:00 UTC): Backs up persistent volume data
2. **Kopia Maintenance** (~02:00-02:30 UTC): Deduplication & compression of backup snapshots

The Kopia maintenance phase is the primary CPU consumer. Kopia jobs (labeled `*-kopia-maintain-job-*`) cause CPU spikes to 80%+.

**Verification**:
1. Check timestamp: Is it between 02:00-03:30 UTC?
2. Verify backup phase:
   - `kubectl get jobs -n velero | grep kopia-maintain` — Find recent Kopia jobs (should show "Complete" within last 30m)
   - `kubectl get pods -n velero | grep daily-backup` — Check status of daily-backup pods
3. CPU status: `kubectl top node <node>` — Should show CPU normalizing (< 60%) after Kopia jobs complete
4. Verify recent completion: `kubectl get jobs -A --sort-by='.status.completionTime' | grep -i kopia | tail -10`

**Resolution**: AUTO-RESOLVE
- This is expected transient behavior (Kopia deduplication is CPU-intensive)
- No action required
- **Expected timeline**:
  - 02:00-02:30 UTC: Kopia jobs run (CPU at 80%+)
  - After 02:30: CPU drops rapidly to normal (39-50%)
  - If alert fires between 02:00-03:00 UTC, this is normal
- If CPU is still elevated 60+ minutes after backup window ends (03:30 UTC), investigate:
  - Storage performance degradation (NFS, Garage S3)
  - Kopia jobs hung/deadlocked
  - Insufficient node resources

**Why It's Safe**:
- All nodes remain Ready during backup (CPU is not exhausted, just contended)
- Pod scheduling continues normally (pods evicted/rescheduled rarely)
- No service degradation observed (app pods still run at normal load)
- Kopia deduplication is essential for backup efficiency (reduces storage by 70-80%)
- **Incident #247 (2026-02-26 02:00 UTC)**: Verified safe — CPU returned to 39% after Kopia jobs completed

**To Reduce Future Alerts**:
- Backup already runs at low-traffic window (02:00 UTC)
- Kopia CPU spike is unavoidable (it's the deduplication algorithm)
- Options to reduce alert frequency:
  1. Adjust alert threshold: Raise from 80% to 85% during 02:00-03:00 UTC
  2. Add alert rule exemption for backup window
  3. Run Kopia maintenance less frequently (currently daily)
- Monitor if Velero needs resource limit increases or Kopia optimization
- Current: 2-4 cores at 80% for ~30 minutes during backup window is normal
