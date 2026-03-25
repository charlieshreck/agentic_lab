# Sonarr Transmission Download Path Mapping

## Problem
Sonarr health check fails with error: "Remote download client Transmission places downloads in `/downloads/tv-sonarr` but this directory does not appear to exist."

## Root Cause
Sonarr is configured with a remote path mapping that expects Transmission to place downloads in `/downloads/tv-sonarr` (a subdirectory of the NFS mount at `/downloads`). However, Transmission was not explicitly configured to use this subdirectory and was defaulting to just `/downloads`, causing the directory that Sonarr expected to not exist.

## Solution
Add the `TRANSMISSION_DOWNLOAD_DIR` environment variable to the Transmission Kubernetes deployment to explicitly configure the download directory.

### Configuration
In `kubernetes/applications/media/transmission/deployment.yaml`, add the following environment variable to the Transmission container:

```yaml
- name: TRANSMISSION_DOWNLOAD_DIR
  value: "/downloads/tv-sonarr"
```

This ensures that:
1. Transmission creates and uses the `/downloads/tv-sonarr` subdirectory
2. The directory path matches Sonarr's remote path mapping expectation
3. Both containers share the same NFS mount point (TrueNAS at 10.40.0.10:/mnt/Taranaki/Tarriance/hopuhopu_katoa)

### GitOps Implementation
1. Commit the change: `git add kubernetes/applications/media/transmission/deployment.yaml && git commit -m "fix: configure Transmission download directory for Sonarr remote path mapping"`
2. Push to GitHub: `git push origin main`
3. ArgoCD automatically syncs the updated deployment
4. Transmission pod is redeployed with the new environment variable
5. Sonarr health check passes as the expected directory now exists

## Verification
After deployment:
- Transmission logs show successful initialization of the download directory
- Sonarr health check: "Remote download client Transmission ✓"
- Files downloaded by Sonarr through Transmission appear in `/downloads/tv-sonarr`

## Related Issues
- Incident #469: Sonarr health check failure

## Notes
- Both Sonarr and Transmission mount the same NFS path at `/downloads`
- The subdirectory `/downloads/tv-sonarr` is created dynamically by Transmission on startup
- Sonarr's remote path mapping (configured in app settings) expects this exact directory structure
