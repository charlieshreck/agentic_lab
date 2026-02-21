# KubeJobFailed: mount-canary-writer

## Alert Description

Alert: **KubeJobFailed** with severity **warning**
- Namespace: `media`
- Job: `mount-canary-writer-*`
- Cluster: `production`

## Root Cause

The `mount-canary-writer` CronJob tests NFS mount health by writing sentinel files to mounted Plex media directories. It failed when configured to mount non-existent TrueNAS datasets:

- `/mnt/Taranaki/Tarriance/hopuhopu_katoa` (downloads)
- `/mnt/Tongariro/Plexopathy/Film` (movies)
- `/mnt/Tongariro/Plexopathy/Television` (tv)

These datasets do not exist on TrueNAS-HDD. The actual media dataset is:
- `/mnt/Taupo/Pleximetry` (857.7GB, contains Plex media)

## Fix

Update the CronJob manifest to mount the correct existing path:

**File**: `kubernetes/applications/media/mount-canary/cronjob.yaml`

Change all volume mounts from:
```yaml
volumes:
  - name: downloads
    nfs:
      server: 10.40.0.10
      path: /mnt/Taranaki/Tarriance/hopuhopu_katoa
  - name: movies
    nfs:
      server: 10.40.0.10
      path: /mnt/Tongariro/Plexopathy/Film
  - name: tv
    nfs:
      server: 10.40.0.10
      path: /mnt/Tongariro/Plexopathy/Television
```

To:
```yaml
volumes:
  - name: downloads
    nfs:
      server: 10.40.0.10
      path: /mnt/Taupo/Pleximetry
  - name: movies
    nfs:
      server: 10.40.0.10
      path: /mnt/Taupo/Pleximetry
  - name: tv
    nfs:
      server: 10.40.0.10
      path: /mnt/Taupo/Pleximetry
```

Apply via GitOps:
```bash
git -C /home/prod_homelab add kubernetes/applications/media/mount-canary/cronjob.yaml
git -C /home/prod_homelab commit -m "fix: mount-canary-writer - use correct TrueNAS paths"
git -C /home/prod_homelab push origin main
# ArgoCD auto-syncs within minutes
```

## Verification

After ArgoCD syncs (watch `/home/prod_homelab/kubernetes/applications/media/mount-canary/`):

```bash
# Check the latest job pod
kubectl get pods -n media | grep mount-canary

# Verify it Succeeded
kubectl logs -n media job/mount-canary-writer-* | tail -5
# Should output: "Canary files written successfully"
```

## Long-Term Solution

The current fix mounts all three mount points (downloads, movies, tv) to the same Pleximetry dataset. This is a temporary workaround.

**Proper solution** (requires TrueNAS infrastructure updates):

1. Create Tongariro/Tongariro dataset with subdirectories:
   - `/mnt/Tongariro/Plexopathy/Film` → for Radarr movies
   - `/mnt/Tongariro/Plexopathy/Television` → for Sonarr TV shows

2. Create Taranaki dataset with subdirectory:
   - `/mnt/Taranaki/Tarriance/hopuhopu_katoa` → for Transmission/SABnzbd downloads

3. Export all three as NFS shares to 10.40.0.0/24 network

4. Update mount-canary-writer to mount each to its proper path

5. Update any Kubernetes *arr deployments to mount these paths instead of Pleximetry

## Alert Configuration

This alert fires whenever the `mount-canary-writer` CronJob fails. The canary runs every 5 minutes (`schedule: "*/5 * * * *"`).

**Alert should trigger** when NFS mounts are truly unavailable (e.g., TrueNAS offline, network down). **False positives** occur when paths don't exist or permissions are misconfigured.

To adjust sensitivity:
- `backoffLimit: 1` - job fails after 1 retry (currently strict, no tolerance)
- `activeDeadlineSeconds: 60` - 60-second timeout per attempt

## Related Resources

- CronJob manifest: `prod_homelab/kubernetes/applications/media/mount-canary/cronjob.yaml`
- TrueNAS NFS config: OPNsense → Infisical secret `/infrastructure/truenas-hdd/`
- NFS network: vmbr3 (10.40.0.0/24) on prod cluster workers

## References

- **TrueNAS Datasets**: Available at `/mnt/Taupo/*` and `/mnt/Tekapo/*`
- **NFS Server**: 10.40.0.10 (TrueNAS-HDD management IP: 10.10.0.103)
- **Prod Network**: 10.10.0.0/24 (management), 10.40.0.0/24 (NFS storage)
