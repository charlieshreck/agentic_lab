# Runbook: TrueNAS-Media Taranaki Pool Saturation (Orphaned Downloads)

**Status**: Incident #385 (2026-02-28)
**Severity**: Warning
**Auto-trigger**: At 88% pool usage
**Root Cause**: Orphaned Transmission downloads in `/mnt/Taranaki/Tarriance/hopuhopu_katoa`

## Problem

The Taranaki ZFS pool on **TrueNAS-Media** (VM 109, IP 10.10.0.100) fills to 88-96% because:

1. **Transmission downloads to** `/mnt/Taranaki/Tarriance/hopuhopu_katoa` (93.8GB)
2. **Sonarr uses SABnzbd**, not Transmission (no import connection)
3. **Cleanuparr's DownloadCleaner** cannot delete because no imports trigger
4. **Old downloads accumulate** and never clean up

## Root Cause Analysis

| Component | What It Does | Issue |
|-----------|--------------|-------|
| Transmission | Downloads torrents to `/downloads` → `/mnt/Taranaki/Tarriance/hopuhopu_katoa` | No connection to Sonarr |
| Sonarr | Imports from SABnzbd only | Ignores Transmission downloads entirely |
| Cleanuparr DownloadCleaner | Deletes files **after import** | No import events = no cleanup |
| Tarriance (NFS) | Holds download folder | Becomes a black hole for orphaned files |

**Result**: Pool usage: 0.09TB used / 0.22TB total = 41% baseline → 88-96% when new downloads arrive.

## Diagnosis

```bash
# SSH to TrueNAS-Media (if accessible)
ssh root@10.10.0.100

# Check Tarriance dataset usage
zfs list -o name,used,avail Taranaki Taranaki/Tarriance

# List old files in download folder
ls -lht /mnt/Taranaki/Tarriance/hopuhopu_katoa | head -30

# Find files older than 7 days
find /mnt/Taranaki/Tarriance/hopuhopu_katoa -mtime +7 -type f
```

## Solutions

### Option 1: Manual Cleanup (Immediate)

Delete old orphaned downloads:

```bash
# SSH to TrueNAS-Media
ssh root@10.10.0.100

# List files by age
ls -lht /mnt/Taranaki/Tarriance/hopuhopu_katoa | tail -20

# Remove old files (older than 7 days)
find /mnt/Taranaki/Tarriance/hopuhopu_katoa -mtime +7 -type f -delete

# Verify space freed
zfs list Taranaki/Tarriance
```

**Caution**: Ensure Sonarr/Radarr are not actively importing these files. Check logs first.

### Option 2: Create Cleanup CronJob (Permanent)

Deploy a Kubernetes CronJob to periodically delete old downloads:

**File**: `/home/prod_homelab/kubernetes/applications/media/cleanup-tarriance-cronjob.yaml`

```yaml
---
apiVersion: batch/v1
kind: CronJob
metadata:
  name: cleanup-tarriance-old-downloads
  namespace: media
spec:
  # Run daily at 02:00 UTC (off-peak)
  schedule: "0 2 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: cleanup
            image: busybox:1.36
            command:
            - /bin/sh
            - -c
            - |
              echo "Removing Tarriance downloads older than 7 days..."
              find /downloads -mtime +7 -type f -exec rm -v {} \;
              echo "Cleanup completed. Current usage:"
              du -sh /downloads
            volumeMounts:
            - name: downloads
              mountPath: /downloads
          volumes:
          - name: downloads
            nfs:
              server: 10.40.0.10
              path: /mnt/Taranaki/Tarriance/hopuhopu_katoa
```

Deploy:
```bash
kubectl -C /home/prod_homelab apply -f kubernetes/applications/media/cleanup-tarriance-cronjob.yaml
```

### Option 3: Connect Transmission to Sonarr/Radarr (Architectural Fix)

Configure Sonarr/Radarr to use Transmission for torrent downloads:

1. Open Sonarr UI → Settings → Download Clients
2. Add "Transmission" client pointing to `transmission.media.svc.cluster.local:9091`
3. Configure import path: `/downloads` (Transmission mount)
4. Set as primary download client (higher priority than SABnzbd)
5. Repeat for Radarr

This allows Cleanuparr to track and delete imports normally.

## Prevention

1. **Monitor pool usage**: Alert fires at 85% threshold
2. **Regular cleanup**: Run manual cleanup monthly OR deploy CronJob
3. **Verify imports**: Ensure Sonarr/Radarr are importing correctly
4. **Check logs**: Look for import failures that might block cleanup

## Related Issues

- **Incident #160**: Ruapeuh memory pressure (similar resource saturation pattern)
- **Known issue (2026-02-23)**: TrueNAS-Media NFS permissions broken for some UIDs (may prevent imports)

## References

- TrueNAS-Media: VMID 109, IP 10.10.0.100
- Tarriance NFS: `10.40.0.10:/mnt/Taranaki/Tarriance/hopuhopu_katoa`
- Cleanuparr: `cleanuparr-dd9bf5875-4r8w4` (media namespace, enabled)
- Sonarr: Uses SABnzbd (Usenet), NOT Transmission
- Radarr: Unknown (check if also uses SABnzbd)
