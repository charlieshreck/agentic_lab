# Sonarr Remote Path Mapping Missing Directory

**Alert**: `SonarrHealthCheck` - "Remote download client Transmission places downloads in /downloads/tv-sonarr but this directory does not appear to exist"

**Severity**: Warning
**Root Cause**: Download subdirectories don't exist on shared NFS storage
**Resolution**: Create missing directories on the downloads NFS mount

## Root Cause Analysis

Sonarr monitors health and checks if configured remote download paths exist. The remote path mapping in Sonarr is configured as:
- **Local path**: `/downloads/tv-sonarr/`
- **Remote path**: `/downloads/tv-sonarr/` (in Transmission pod)

The NFS mount at `/mnt/Taranaki/Tarriance/hopuhopu_katoa` only had `incomplete/` directory, causing Sonarr's health check to fail.

## Fix

Create the missing subdirectories on the shared downloads mount:

```bash
export KUBECONFIG=/root/.kube/config

# Create missing directories
kubectl exec -n media transmission-86474b9965-227hk -- \
  mkdir -p /downloads/tv-sonarr /downloads/movies-radarr

# Verify
kubectl exec -n media transmission-86474b9965-227hk -- ls -la /downloads/
```

**Why this works**: All *arr services share the same NFS mount at `/downloads/`. Creating the subdirectories there makes them visible to all pods and resolves the health check.

## Patterns & Prevention

### Download Directory Structure
The shared downloads NFS mount should maintain this structure:
```
/downloads/
├── incomplete/          # Active downloads
├── tv-sonarr/          # Sonarr completed downloads
└── movies-radarr/      # Radarr completed downloads
```

### Permanent Fix — Init Container (2026-03-25)
Transmission deployment now has an init container that ensures required directories exist on every pod start:

```yaml
initContainers:
- name: init-download-dirs
  image: busybox:1.37
  command: ['sh', '-c', 'mkdir -p /downloads/tv-sonarr /downloads/movies-radarr /downloads/incomplete && chown -R 3000:3000 /downloads/tv-sonarr /downloads/movies-radarr']
  volumeMounts:
  - name: downloads
    mountPath: /downloads
```

This prevents recurrence after pod restarts or NFS remounts.

### Why Separate Directories?
- **Isolation**: Each service has its own completed downloads directory
- **Monitoring**: Easier to track which service added what files
- **Cleanup**: Enables per-service retention policies

### Related Configuration
- Sonarr remote path mapping: UI → Settings → Download Clients → Transmission
- Radarr remote path mapping: UI → Settings → Download Clients → Transmission
- Both configured in their respective pod configs (no changes needed)

## Verification

Health check passes when:
1. Directory exists and is accessible from Transmission pod
2. Sonarr can write to the directory (ownership/permissions allow)
3. Both Sonarr and Transmission see the same NFS mount

```bash
# Verify from both pods
kubectl exec -n media sonarr-f87459474-w8b9b -- test -d /downloads/tv-sonarr && echo "✓ Sonarr can see it"
kubectl exec -n media transmission-86474b9965-227hk -- test -d /downloads/tv-sonarr && echo "✓ Transmission can see it"
```

## References
- Sonarr health check: https://wiki.servarr.com/servarr/health-checks
- Remote path mapping: https://wiki.servarr.com/sonarr/settings#remote-path-mappings
