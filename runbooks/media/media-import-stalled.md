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

### Step 2b: Check for duplicate downloads (movie/series already exists in library)

If a queue item has `trackedDownloadState: "importBlocked"`, it usually means Radarr/Sonarr **cannot**
import because the movie/series already exists in the library. Verify by searching your Radarr/Sonarr
library for the movie title. If found, this is a duplicate download situation.

Fix: **Remove from arr queue and remove from client** (the file is already imported):
```
mcp__media__radarr_remove_queue_item(queue_id=<id>, remove_from_client=True, blocklist=True)
mcp__media__sonarr_remove_queue_item(queue_id=<id>, remove_from_client=True, blocklist=True)
```

**Recent example (2026-03-21)**: Radarr queue had "Sevimli.Canavarlar.Universitesi.2013..." (Turkish title for Monsters University) with `importBlocked` state. Monsters University (2013) already existed in library at 720p. Removed the duplicate queue item with `remove_from_client=True` + `blocklist=True` to prevent duplicate downloads in future.

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
**Status 2026-03-05**: Huntarr Sonarr switched to `episodes` mode. Prevents season packs
from overwhelming the 230GB Taranaki pool.

### Cleanuparr Stall/Slow Rules

**IMPORTANT**: Stall and slow rules live at **separate API endpoints**, NOT inside the main
`/api/configuration/queue_cleaner` body. The `stallRules: []` in the main GET is a known API quirk.
Rules are managed via: `GET/POST /api/queue-rules/stall` and `GET/POST /api/queue-rules/slow`

**Check current rules** (direct API requires `Accept: application/json` header):
```bash
CLEANUPARR_KEY="17df8de375fce3dde15e8422f431202e1ec74f362856bafc79dd4c17f8ee3815"
curl -s https://cleanuparr.kernow.io/api/queue-rules/stall -H "X-Api-Key: $CLEANUPARR_KEY" -H "Accept: application/json"
curl -s https://cleanuparr.kernow.io/api/queue-rules/slow -H "X-Api-Key: $CLEANUPARR_KEY" -H "Accept: application/json"
```

**Status 2026-03-05**: Rules exist ("Stuck" stall + "Slow coach" slow, both Public, 3 strikes).
These are persistent and survive Cleanuparr restarts.

**Add stall rule** (if missing):
```
mcp__media__cleanuparr_create_stall_rule(name="Stuck", max_strikes=3, privacy_type="Public")
```

**Add slow rule** (if missing):
```
mcp__media__cleanuparr_create_slow_rule(name="Slow coach", min_speed="10KB", max_strikes=3, privacy_type="Public")
```

### Cleanuparr MCP API Notes (Fixed 2026-03-05, commit `8d13e3f`)
- `Accept: application/json` is **required** — without it, Caddy returns Angular SPA HTML
- `PUT /api/configuration/queue_cleaner` returns 400 if `id` is in the body (even though GET returns it)
- Both bugs fixed in media-mcp — `cleanuparr_update_queue_cleaner_config` now strips `id`

### Cleanuparr Failed Import (Download Client Config)
Only Transmission is configured in Cleanuparr. SABnzbd Usenet downloads are not directly connected.
Stall/slow rules still work for Usenet because Cleanuparr detects stalls via arr queue state.

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
