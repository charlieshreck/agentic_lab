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

## Additional Patterns (2026-03-04, finding #1002)

### Season Pack = Multiple Queue Entries (Normal)
When Sonarr tracks a season pack download, it creates **one queue entry per episode** in the season.
A season with 12 episodes = 12 queue entries all with the same title and sizeleft. This is NOT duplication or a bug.
- Mr.Robot S02 (12 eps) → 12 queue entries ✓
- Do not alert on "N duplicate queue entries" for season packs.

### `series: null` in media-mcp Response
The media-mcp `sonarr_get_queue` tool returns `"series": null` for ALL queue items — it strips the series
object from the response. This field is **not usable** for orphan detection via patrol. The `arr_queue_orphaned`
check in error-hunter queries the real Sonarr API directly and is not affected, but patrol scripts should not
rely on `series: null` to identify orphaned items.

### Torrent Stopped at 0% for Completed Series
If `transmission_list_torrents` shows a torrent `stopped` at 0% and the series is already 100% complete
in Sonarr, this is benign — likely a re-grab that Sonarr queued but then stopped when it detected the
series was already complete. No action needed; Sonarr will clean it up.

## Content-Based Issues (2026-03-21, incident #431)

### Radarr: `importBlocked` — Movie Matching Ambiguity
**Pattern**: `trackedDownloadStatus: "warning"`, `trackedDownloadState: "importBlocked"`
Error message: `"Found matching movie via grab history, but release was matched to movie by ID. Manual Import required."`

**Root cause**: Radarr safety feature triggered when a release is initially matched to a movie via grab history,
but then re-matched by a different method (e.g., movie ID). This creates an ambiguity that requires manual intervention
to confirm the import is correct.

**Resolution** (in priority order):

1. **Blocklist + Re-Search (RECOMMENDED)** - Avoids the matching ambiguity entirely:
   ```
   mcp__media__radarr_remove_queue_item(queue_id=<id>, blocklist=true)
   mcp__media__radarr_trigger_search(movie_id=<id>)
   ```
   This forces Radarr to find an alternative release without the matching ambiguity.

2. **Manual Import (if you trust the file)** - For releases where the file is verified correct:
   - Radarr UI: Activity → Queue → click item → Manual Import → confirm
   - OR via API: Send PUT to `/api/v3/history/failed` to mark as complete, then trigger re-import

**Example**: "The Silence of the Lambs (1991)" matched initially by grab history, later re-confirmed by TMDB ID match.
Blocklisting the release and re-searching is preferred over manual import for production reliability.

### Sonarr: `importPending` — Executable File Detected
**Pattern**: `trackedDownloadStatus: "warning"`, `trackedDownloadState: "importPending"`
Error message: `"Caution: Found executable file"`

**Root cause**: NZB release contains an executable file (.exe) which Sonarr blocks as a security measure.
The .exe file often masquerades as the video file or comes packaged in the release.

**Resolution**:
1. Verify file in /downloads: `ls -lah /downloads/tv-sonarr/<release>/`
2. Remove the .exe: `rm /downloads/tv-sonarr/<release>/*.exe`
3. Trigger re-import: Sonarr Activity → Queue → click item → Force Import OR wait for auto-import after cleanup
4. OR: Request re-download from different NZB source/indexer that doesn't include executable

**Prevention**:
- Check release comments on indexer before grabbing
- Configure Sonarr "Settings → Import → Skip free space check" to catch malformed releases earlier
- Add problematic indexers to ignore list if releases consistently contain malware/executables
