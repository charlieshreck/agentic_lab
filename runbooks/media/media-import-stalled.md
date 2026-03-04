# Runbook: MediaImportStalled

**Check name**: `MediaImportStalled`
**Domain**: media
**Severity**: warning

## What This Alert Means

Downloads are stuck in the Radarr/Sonarr queue and cannot complete the import process.
Real causes include: orphaned downloads (movie/series deleted from arr), download client errors, or failed imports.

## Fixed False Positive (2026-03-04)

The original check fired on `status == "warning"` which includes Transmission-queued downloads
(normal waiting-in-line behaviour). Fixed to require `trackedDownloadStatus in ("warning", "error")`
or `status == "failed"`. Commit `bdcdeab` in agentic_lab.

**After this fix**, the check should only fire on genuine issues.

## Diagnosis

### Step 1: Check queue for real problems
```
mcp__media__radarr_get_queue
mcp__media__sonarr_get_queue
```

Look at each item's fields:

| `status` | `trackedDownloadStatus` | Meaning |
|----------|------------------------|---------|
| `warning` | `ok` | Transmission queued — **normal, ignore** |
| `warning` | `warning` | Arr app sees a real problem — investigate |
| `warning` | `error` | Download client error — investigate |
| `failed` | any | Hard failure — remove and re-search |
| `downloading` | `ok` | Actively downloading — normal |
| `paused` | `ok` | SABnzbd queued — normal |

**Note**: The media-mcp strips `movie` and `series` objects from responses — they always show `null`.
Do NOT use `movie: null` or `series: null` to detect orphaned downloads via MCP.

### Step 2: Check for orphaned downloads (movie/series deleted from arr)

Orphaned downloads have `status: "warning"` + `trackedDownloadStatus: "ok"` but the movie/series was
deleted from Radarr/Sonarr. The MCP strips the movie/series object so this can't be detected from
the MCP response alone. Signs:
- Item has been in the queue for days with no progress toward completion
- All other downloads are actively moving
- The movie/series title is not in your Radarr/Sonarr library

If suspected orphaned: remove from arr queue without removing from client:
```
mcp__media__radarr_remove_queue_item(queue_id=<id>, remove_from_client=False, blocklist=False)
mcp__media__sonarr_remove_queue_item(queue_id=<id>, remove_from_client=False, blocklist=False)
```

### Step 3: Check download clients
```
mcp__media__transmission_list_torrents
mcp__media__sabnzbd_get_queue
```

- Transmission "stopped" with 0 seeders = dead torrent → blocklist and re-search
- SABnzbd globally paused = disk full or quota hit

### Step 4: Check disk space (if multiple items affected)
```
mcp__infrastructure__truenas_get_disk_usage (instance: "media")
```
Taranaki pool (230GB) fills quickly with season packs. If > 90%:
- Delete already-imported completed downloads from the NFS share
- See runbook: `media/arr-disk-full.md`

## Contributing Factors

### Huntarr `seasons_packs` Mode (HIGH RISK)
Huntarr configured to grab entire season packs instead of individual episodes. A single season pack
can be 30-90GB, overwhelming the 230GB Taranaki pool.

**Current config check:**
```
mcp__media__huntarr_get_settings(app="sonarr")
```
Look for `hunt_missing_mode: "seasons_packs"` — this should be `"episodes"`.

**Fix** (requires MCP redeploy if using updated media-mcp, endpoint: `POST /api/settings/sonarr`):
```
mcp__media__huntarr_update_settings(app="sonarr", settings={"hunt_missing_mode": "episodes", "upgrade_mode": "episodes"})
```
**Status 2026-03-04**: MCP fix deployed (commit `1f94cbc` in mcp-servers), awaiting pod restart.

### Cleanuparr Stall/Slow Rules Not Configured
Cleanuparr can automatically remove stalled/slow downloads but the rules are separate resources:
- `POST /api/queue-rules/stall` — stall rules (download stuck at same % for N checks)
- `POST /api/queue-rules/slow` — slow rules (download speed below threshold)

**Add stall rule** (once media-mcp redeployed):
```
mcp__media__cleanuparr_create_stall_rule(
    name="Stalled Public",
    max_strikes=3,          # 3 × 5min = 15min before removal
    privacy_type="Public",  # Don't auto-remove private tracker torrents
    min_completion_percentage=0,
    max_completion_percentage=100,
    reset_strikes_on_progress=True
)
```

**Add slow rule**:
```
mcp__media__cleanuparr_create_slow_rule(
    name="Slow Public",
    min_speed="10KB/s",
    max_strikes=3,
    privacy_type="Public",
    reset_strikes_on_progress=True
)
```

### Cleanuparr Failed Import (Requires Download Client Config)
Cleanuparr's `failedImport.maxStrikes >= 3` feature auto-removes failed imports but requires a
download client (Transmission/SABnzbd) to be configured in Cleanuparr first. As of 2026-03-04,
no download client is configured (`downloadClient: {}`). This feature is not yet available.

## Resolution Actions

| Issue | Action |
|-------|--------|
| `trackedDownloadStatus: "warning/error"` | Check statusMessages, blocklist and re-search |
| `status: "failed"` | Remove, optionally blocklist, re-search |
| Orphaned download (no matching movie/series) | Remove from queue (keep in client or delete) |
| SABnzbd globally paused | Check disk space; resume after freeing space |
| Transmission torrents all stopped | Check disk space or download client errors |

## SABnzbd Resume
```
mcp__media__sabnzbd_resume_queue()
```

## Restart alerting-pipeline after code changes
The alerting-pipeline runs from a ConfigMap. After any check code change, restart the pod:
```
mcp__infrastructure__kubectl_restart_deployment(deployment_name="alerting-pipeline", namespace="ai-platform", cluster="agentic")
```
