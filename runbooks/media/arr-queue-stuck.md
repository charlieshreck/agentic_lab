# Runbook: arr_queue_stuck

**Check name**: `arr_queue_stuck`
**Domain**: media
**Severity**: warning

## What This Alert Means

A Radarr or Sonarr queue item has a status indicating it may be stuck or failed. The relevant fields are:
- `status` — the download client's reported status
- `trackedDownloadStatus` — Radarr/Sonarr's own assessment of the download health

## Key Distinction: Queued vs Actually Stuck

**False positive pattern (do NOT escalate):**
- `status: "warning"`, `trackedDownloadStatus: "ok"`
- Radarr/Sonarr maps Transmission's "queued" status (waiting its turn) to `status: "warning"` in the API
- `trackedDownloadStatus: "ok"` means the arr app itself sees no real problem
- This is normal Transmission queue management — only N downloads active at a time

**Real issues (investigate):**
- `trackedDownloadStatus: "warning"` — arr app detected a problem (no seeders, hash check fail, etc.)
- `trackedDownloadStatus: "error"` — download client error
- `status: "failed"` — hard failure

## Investigation Steps

1. **Check current queue state:**
   ```
   mcp__media__radarr_get_queue / mcp__media__sonarr_get_queue
   ```
   Look at `trackedDownloadStatus` — if "ok", this is likely queued (false positive).

2. **Check Transmission:**
   ```
   mcp__media__transmission_list_torrents
   ```
   - "queued" = waiting its turn (normal)
   - "stopped" at low % = may need investigation
   - "downloading" with 0 speed = stalled (no peers/seeds)

3. **Check disk space (if torrents actually stalled):**
   ```
   mcp__infrastructure__truenas_get_disk_usage (instance: "media")
   ```
   Previous incident (#1056): Taranaki pool at 100% stopped all downloads.

4. **Check for no-seeder torrents:**
   - `status: "queued"` in Transmission with 0 peers for >24h = dead torrent
   - Use `radarr_remove_queue_item` with `blocklist: true` to re-search

## Resolution

### If `trackedDownloadStatus == "ok"` (false positive)
Auto-resolve: items are legitimately queued behind active downloads.

### If `trackedDownloadStatus == "warning"` or `"error"`
- Check Transmission logs for the specific torrent
- If no seeders: blocklist and re-search via Radarr/Sonarr
- If disk full: free space on Taranaki pool (see media/arr-disk-full.md)

### If storage full
See previous resolution: delete completed downloads that are already imported to Plex library.
Run in Radarr: Activity → Queue → filter "Completed" → delete files already in library.

## Rule Fix (2026-03-04)
The `arr_queue_stuck` checker was updated to only fire when:
- `status == "failed"` (hard failure), OR
- `trackedDownloadStatus in ("warning", "error")` (arr app sees real problem)

Previously it fired on any `status == "warning"`, which included legitimately queued downloads.
Commit: `4112b5a` in agentic_lab.

## Post-Fix: Pod Restart Required

**Important**: error-hunter runs from a ConfigMap-backed volume. When a checker fix is committed, ArgoCD updates the ConfigMap but the **running Python process does NOT reload**. The pod must be restarted to activate the fix:

```bash
# Via MCP
mcp__infrastructure__kubectl_restart_deployment(deployment_name="error-hunter", namespace="ai-platform", cluster="agentic")
```

Finding #1054 was a false positive created at 02:04 on 2026-03-04, before the fix committed at 02:21. The pod (started March 1) was still running old code and produced one more false positive after the fix was committed. Restarting the pod activated the fix.

**Rule**: After any error-hunter checker code change, always restart the deployment.
