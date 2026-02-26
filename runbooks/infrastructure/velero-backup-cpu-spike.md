# Velero Backup CPU Spike (Transient)

**Alert**: CPU spike on worker nodes (threshold: 80%) during 02:00-03:30 UTC window

**Root Cause**: Daily Velero backup jobs (`velero/daily-backup-*`) run PodVolumeBackup operations which are CPU-intensive. Spikes are expected during this window.

**Verification**:
1. Check timestamp: Is it between 02:00-03:30 UTC?
2. Verify Velero jobs: `kubectl get pods -n velero | grep daily-backup`
3. Check job status: Should show "Running" (actively backing up) or "Succeeded" (just completed)
4. Check CPU now: Should be normalizing (< 60%) after backup finishes

**Resolution**: AUTO-RESOLVE
- This is expected transient behavior
- No action required
- CPU will normalize within 30 minutes after backup completion
- If CPU is still elevated 60+ minutes after backup window ends, investigate storage performance

**Why It's Safe**:
- All nodes remain Ready during backup
- Pod scheduling not affected
- No service degradation observed
- Normal backup activity

**To Reduce Future Alerts**:
- Consider running backup at low-traffic window (currently 02:00 UTC)
- Monitor if Velero needs resource limit increases
- Check if backup window needs expansion (if backups exceed 60 minutes)
