# Add Storage to FileBrowser

## Overview
FileBrowser (https://files.kernow.io) provides web access to all TrueNAS storage. This runbook covers adding new storage mounts.

## Prerequisites
- TrueNAS dataset must exist
- NFS share must be configured on TrueNAS (or create one below)

## TrueNAS Instances

| Instance | NFS IP | Management IP | Purpose |
|----------|--------|---------------|---------|
| Media | 10.40.0.10 | 10.20.0.100 | Plex media, downloads |
| HDD | 10.20.0.103 | 10.20.0.103 | Backups, archives |

## Step 1: Create NFS Share (if needed)

### Via TrueNAS API
```bash
# Get API key from Infisical
# For HDD NAS:
/root/.config/infisical/secrets.sh get /apps/truenas/truenas-hdd API_KEY

# Create NFS share
curl -s -k -X POST "https://10.20.0.103/api/v2.0/sharing/nfs" \
  -H "Authorization: Bearer <API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/mnt/Pool/Dataset",
    "comment": "Description",
    "networks": ["10.20.0.0/24", "10.10.0.0/24", "10.30.0.0/24", "10.40.0.0/24"],
    "ro": false,
    "enabled": true
  }'
```

### Verify Share Created
```bash
# Via MCP
truenas-mcp: list_shares(instance="hdd")
```

## Step 2: Update FileBrowser Deployment

Edit `prod_homelab/kubernetes/applications/apps/filebrowser/deployment.yaml`:

### 2a. Add to Velero Exclusion
```yaml
annotations:
  backup.velero.io/backup-volumes-excludes: ...,newvolume
```

### 2b. Add VolumeMount
```yaml
volumeMounts:
  - name: newvolume
    mountPath: /folder/hdd/NewVolume  # or /folder/media/
```

### 2c. Add Volume Definition
```yaml
volumes:
  - name: newvolume
    nfs:
      server: 10.20.0.103  # or 10.40.0.10 for media
      path: /mnt/Pool/Dataset
```

### 2d. Add to ConfigMap Sources
```yaml
sources:
  - path: "/folder/hdd/NewVolume"
    config:
      defaultEnabled: true
```

## Step 3: Commit and Deploy

```bash
/home/scripts/git-commit-submodule.sh prod_homelab "feat(filebrowser): add <dataset> mount"
```

## Step 4: Trigger ArgoCD Sync

```bash
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig \
kubectl patch application filebrowser -n argocd --type merge \
  -p '{"operation": {"initiatedBy": {"username": "claude"}, "sync": {"prune": true}}}'
```

## Step 5: Verify

```bash
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig \
kubectl exec -n apps deploy/filebrowser -- ls -la /folder/hdd/
```

## Current Mounts

| FileBrowser Path | NFS Source | TrueNAS Instance |
|------------------|------------|------------------|
| /folder/media/Plexopathy | 10.40.0.10:/mnt/Tongariro/Plexopathy | Media |
| /folder/media/Tarriance | 10.40.0.10:/mnt/Taranaki/Tarriance | Media |
| /folder/hdd/Pleximetry | 10.20.0.103:/mnt/Taupo/Pleximetry | HDD |
| /folder/hdd/PBS-Backups | 10.20.0.103:/mnt/Taupo/pbs | HDD |
| /folder/hdd/MinIO | 10.20.0.103:/mnt/Taupo/MinIO | HDD |
| /folder/hdd/Truro | 10.20.0.103:/mnt/Truro | HDD |

## Related
- FileBrowser deployment: `prod_homelab/kubernetes/applications/apps/filebrowser/`
- TrueNAS MCP: `agentic_lab/mcp-servers/truenas/`
- Infisical secrets: `/apps/truenas/truenas-hdd`, `/apps/truenas/truenas-media`
