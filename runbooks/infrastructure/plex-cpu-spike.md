# Plex VM CPU Spike (83.6% / 80% Threshold)

## Expected Pattern
Plex VM CPU frequently spikes above 80% due to background operations. These spikes are **transient and benign** when caused by:
- Active transcoding jobs
- Library scans or metadata updates
- Version/update checks
- Backup operations

## How to Verify It's Transient

1. **Check active sessions** (Tautulli):
   ```
   mcp__media__tautulli_get_activity
   ```
   - If `stream_count: 0`, no active playback
   - Spike was from a background job that completed

2. **Check current CPU** (Proxmox):
   ```
   mcp__infrastructure__proxmox_get_vm_status
   params: {"host": "ruapehu", "node": "Ruapehu", "vmid": 450}
   ```
   - If CPU is low (< 10%), the spike has cleared
   - Memory should be stable (6GB allocated)

3. **Check AlertManager**:
   ```
   mcp__observability__list_alerts
   active: true
   ```
   - If no active alerts, the spike is gone

## Auto-Resolve Criteria
- ✅ Zero active sessions in Tautulli
- ✅ Current CPU < 10%
- ✅ CPU alert has cleared from AlertManager
- ✅ VM is running and responsive

## When to Investigate Further
- CPU remains high (> 50%) with no active sessions → check for hung transcode process
- CPU frequently spikes > 80% multiple times per day → may indicate library too large, consider periodic maintenance window
- CPU spike coincides with errors in Plex logs → check `/var/log/plexmediaserver/Plex\ Media\ Server.log`

## Incident: #307 (2026-02-26)
- **Alert**: CPU 83.6% (threshold: 80%)
- **Status**: Transient, self-healed
- **Resolution**: Verified zero active sessions, current CPU 0.48%, alert cleared
- **Action taken**: Auto-resolved, no intervention needed

## References
- Plex VM: 10.10.0.50 (VMID 450 on Ruapehu)
- Tautulli: Plex statistics and session tracking
- AlertManager: Active alert status
