# Backrest Operations Runbook

## Overview

Backrest provides a web UI for managing restic backups of VMs and LXC containers.

**Access**:
- Internal: http://10.20.0.40:31115
- External: https://backrest.kernow.io (via Caddy reverse proxy)

**Backend**: Garage S3 at http://10.20.0.103:30188

## Initial Setup

### 1. Access Backrest UI
Navigate to http://10.20.0.40:31115

### 2. Add Repository
1. Click "Add Repository"
2. Configure S3 backend:
   - Type: S3
   - Endpoint: http://10.20.0.103:30188
   - Bucket: backrest
   - Region: garage
   - Access Key: (from Infisical `/backups/garage`)
   - Secret Key: (from Infisical `/backups/garage`)
3. Set repository password (store securely!)

### 3. Add Backup Plans

#### IAC LXC (100) - CRITICAL
- **Name**: iac-daily
- **Repository**: (created above)
- **Host**: iac (10.10.0.100)
- **Paths**: /root, /etc, /home
- **Excludes**: /root/.cache, /root/.local/share/containers
- **Schedule**: 0 3 * * * (3AM daily)
- **Retention**: 14 daily, 4 weekly

#### Plex VM (450)
- **Name**: plex-daily
- **Repository**: (created above)
- **Host**: plex (10.10.0.50)
- **Paths**: /var/lib/plex
- **Excludes**: /var/lib/plex/Plex Media Server/Cache
- **Schedule**: 0 4 * * * (4AM daily)
- **Retention**: 7 daily, 4 weekly

#### UniFi VM (451)
- **Name**: unifi-daily
- **Repository**: (created above)
- **Host**: unifi (10.10.0.51)
- **Paths**: /var/lib/unifi
- **Schedule**: 0 5 * * * (5AM daily)
- **Retention**: 7 daily, 4 weekly

#### TrueNAS Configs
- **Name**: truenas-weekly
- **Host**: truenas-hdd (10.20.0.103)
- **Paths**: /root (config exports)
- **Schedule**: 0 6 * * 0 (6AM Sundays)
- **Retention**: 4 weekly, 2 monthly

## SSH Access

Backrest uses SSH to connect to backup targets.

**SSH Config** (mounted at `/root/.ssh/config`):
```
Host iac
  HostName 10.10.0.100
  User root
  IdentityFile /root/.ssh/id_ed25519

Host plex
  HostName 10.10.0.50
  User root
  IdentityFile /root/.ssh/id_ed25519

Host unifi
  HostName 10.10.0.51
  User root
  IdentityFile /root/.ssh/id_ed25519

Host truenas-hdd
  HostName 10.20.0.103
  User root
  IdentityFile /root/.ssh/id_ed25519

Host truenas-media
  HostName 10.20.0.100
  User root
  IdentityFile /root/.ssh/id_ed25519
```

**SSH Keys**: Stored in Infisical `/backups/backrest`

### Adding SSH Key to New Host
```bash
# Get public key from Infisical
PUBLIC_KEY=$(infisical secrets get SSH_PUBLIC_KEY --path=/backups/backrest --plain)

# Add to target host
ssh root@<target> "echo '$PUBLIC_KEY' >> /root/.ssh/authorized_keys"
```

## Common Operations

### Manual Backup
1. Open Backrest UI
2. Select plan → Run Now

### Browse Snapshots
1. Select repository
2. Click "Browse"
3. Navigate snapshot tree

### Restore Files
1. Browse to desired snapshot
2. Select files/folders
3. Click "Restore"
4. Choose destination path

### Check Backup Status
1. View plan → Recent runs
2. Check for errors/warnings

## Troubleshooting

### SSH Connection Failed
1. Verify SSH key is in target's authorized_keys
2. Check network connectivity: `kubectl exec -n backrest deploy/backrest -- ssh -T iac`
3. Verify SSH config is mounted: `kubectl exec -n backrest deploy/backrest -- cat /root/.ssh/config`

### S3 Connection Failed
1. Verify Garage is running: `curl http://10.20.0.103:30188`
2. Check S3 credentials in environment
3. Test with AWS CLI: `aws s3 ls --endpoint-url=http://10.20.0.103:30188`

### Backup Slow
1. Check network bandwidth
2. Consider enabling compression
3. Review exclude patterns

### Repository Locked
1. Check for running backups
2. Force unlock (use with caution): Repository → Unlock

## Kubernetes Resources

**Namespace**: backrest

**Deployment**: backrest
- Image: garethgeorge/backrest:latest
- Port: 9898 (NodePort 31115)

**Secrets**:
- backrest-s3-credentials (Garage access)
- backrest-ssh-keys (SSH private key + config)

**PVCs**:
- backrest-data (1Gi) - Config and database
- backrest-cache (5Gi) - Restic cache

## Monitoring

Backrest health is monitored by Gatus at http://10.30.0.120:31100

## Related Runbooks
- `/home/agentic_lab/runbooks/infrastructure/backup-overview.md`
- `/home/agentic_lab/runbooks/infrastructure/velero-operations.md`
- `/home/agentic_lab/runbooks/infrastructure/pbs-operations.md`
