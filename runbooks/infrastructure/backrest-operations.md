# Backrest Operations Runbook

## Overview

Backrest provides a web UI for managing restic backups of VMs and LXC containers. It runs in the agentic cluster and stores backups in Garage S3.

## Access

| Method | URL | Notes |
|--------|-----|-------|
| Traefik Ingress | https://backrest.kernow.io | Via Agentic Traefik LB (10.20.0.90) |
| NodePort | http://10.20.0.40:31115 | Direct access / fallback |

**Authentication**: Username/password configured in Backrest UI on first login.

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                              BACKREST BACKUP FLOW                                 │
├──────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   BACKREST (Agentic Cluster)                                                     │
│   Namespace: backrest                                                            │
│   Pod: backrest-xxx                                                              │
│   ┌────────────────────────────────────────────────────────────────────────┐    │
│   │                                                                        │    │
│   │   ┌──────────┐    ┌───────────────┐    ┌──────────────────────────┐  │    │
│   │   │ Web UI   │───▶│ Backup Plans  │───▶│ Restic (embedded)        │  │    │
│   │   │ :9898    │    │ Scheduler     │    │ - Snapshots              │  │    │
│   │   └──────────┘    └───────────────┘    │ - Deduplication          │  │    │
│   │                                         │ - Encryption             │  │    │
│   │                                         └────────────┬─────────────┘  │    │
│   │                                                      │                │    │
│   └──────────────────────────────────────────────────────┼────────────────┘    │
│                                                          │                      │
│                           ┌──────────────────────────────┴──────────────────┐  │
│                           │                                                  │  │
│                           ▼                                                  ▼  │
│   ┌─────────────────────────────────────┐    ┌────────────────────────────────┐│
│   │         SSH to Backup Targets       │    │      S3 to Garage Storage      ││
│   │                                     │    │                                ││
│   │   IAC LXC (10.10.0.100)            │    │   s3:http://10.20.0.103:30188  ││
│   │   Plex VM (10.10.0.50)             │    │   Bucket: backrest             ││
│   │   UniFi VM (10.10.0.51)            │    │                                ││
│   │   TrueNAS-HDD (10.20.0.103)        │    │   Encrypted, deduplicated      ││
│   │                                     │    │   restic repository            ││
│   └─────────────────────────────────────┘    └────────────────────────────────┘│
│                                                                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

## Backend: Garage S3

| Setting | Value |
|---------|-------|
| Repository URI | `s3:http://10.20.0.103:30188/backrest` |
| Region | `garage` |
| Endpoint | `http://10.20.0.103:30188` |
| Bucket | `backrest` |
| Credentials | Infisical `/backups/garage` |

## Configured Backup Plans

Backrest uses **SSH commandPrefix** to run restic on remote hosts. This means restic runs on the target machine (not in the Backrest pod) and streams backup data to Garage S3.

| Plan | Host | Paths | Excludes | Schedule | Retention |
|------|------|-------|----------|----------|-----------|
| **iac-daily** | 10.10.0.175 | /home, /root, /etc | /root/.cache, /home/*/.cache, /root/.local/share/nvim | 3AM daily | 14 daily, 4 weekly |
| **plex-daily** | 10.10.0.50 | /opt/plex/config/Library/Application Support/Plex Media Server, /opt/plex/compose | Cache, Logs directories | 4AM daily | 7 daily, 4 weekly |
| **unifi-daily** | 10.10.0.51 | Container volumes (uosserver_data, uosserver_var_lib_unifi) | Logs | 5AM daily | 7 daily, 4 weekly |
| **truenas-hdd-weekly** | 10.20.0.103 | /root | - | 6AM Sundays | 4 weekly, 2 monthly |
| **truenas-media-weekly** | 10.20.0.100 | /root | - | 7AM Sundays | 4 weekly, 2 monthly |

### Cron Expressions

| Plan | Cron | Meaning |
|------|------|---------|
| iac-daily | `0 3 * * *` | Every day at 3:00 AM |
| plex-daily | `0 4 * * *` | Every day at 4:00 AM |
| unifi-daily | `0 5 * * *` | Every day at 5:00 AM |
| truenas-hdd-weekly | `0 6 * * 0` | Every Sunday at 6:00 AM |
| truenas-media-weekly | `0 7 * * 0` | Every Sunday at 7:00 AM |

### How SSH CommandPrefix Works

Each plan has a `commandPrefix.backup` array that wraps the restic command with SSH:
```json
"commandPrefix": {
  "backup": ["ssh", "-o", "StrictHostKeyChecking=no", "root@10.10.0.50"]
}
```

This causes Backrest to execute: `ssh root@10.10.0.50 restic backup /path/to/backup ...`

**Requirements on target hosts**:
- `restic` binary installed (installed via package manager)
- SSH public key in `/root/.ssh/authorized_keys`
- Network access to Garage S3 (10.20.0.103:30188)

### Path Validation Workaround

Backrest validates that backup paths exist **locally** before running SSH commands. For remote backups (Plex, UniFi), we use an init container to create empty directory structures in the pod that match the remote paths. This satisfies path validation while the actual backup runs on the remote host via SSH.

The init container creates:
- `/opt/plex/config/Library/Application Support/Plex Media Server`
- `/opt/plex/compose`
- `/home/uosserver/.local/share/containers/storage/volumes/uosserver_data/_data`
- `/home/uosserver/.local/share/containers/storage/volumes/uosserver_var_lib_unifi/_data`

## SSH Configuration

Backrest connects to backup targets via SSH using keys mounted from Kubernetes secrets.

### SSH Key Details

| Property | Value |
|----------|-------|
| **Type** | ed25519 |
| **Comment** | backrest-backup@kernow.io |
| **Public Key** | `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJiIOVl9I2skpBkJM+N+VVTTW06LNGKV+46o+P0f3AAZ backrest-backup@kernow.io` |

### SSH Keys Location

- **Kubernetes Secret**: `backrest-ssh-keys` in `backrest` namespace (primary source)
- **Mounted Path**: `/root/.ssh/` in Backrest pod
- **Note**: Keys stored directly in K8s secret (Infisical sync had API issues)

### SSH Config (mounted at `/root/.ssh/config`)

```
Host *
  StrictHostKeyChecking no
  UserKnownHostsFile /dev/null
  IdentityFile /root/.ssh/id_ed25519
```

### Target Host SSH Setup

The public key must be in `/root/.ssh/authorized_keys` on each target:

| Host | IP | Status |
|------|-----|--------|
| IAC LXC | 10.10.0.175 | ✅ Configured |
| Plex VM | 10.10.0.50 | ✅ Configured |
| UniFi VM | 10.10.0.51 | ✅ Configured |
| TrueNAS-HDD | 10.20.0.103 | ✅ Local (no SSH needed) |

### Adding SSH Key to New Host

```bash
# The public key to install on targets
PUBLIC_KEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJiIOVl9I2skpBkJM+N+VVTTW06LNGKV+46o+P0f3AAZ backrest-backup@kernow.io"

# Add to target host
ssh root@<target> "mkdir -p /root/.ssh && echo '$PUBLIC_KEY' >> /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys"

# Install restic on target (required for SSH commandPrefix)
ssh root@<target> "apt update && apt install -y restic"  # Debian/Ubuntu
# or
ssh root@<target> "dnf install -y restic"  # RHEL/Fedora
```

## Common Operations

### Access Backrest UI

1. Navigate to https://backrest.kernow.io
2. Login with configured credentials
3. Dashboard shows all backup plans and recent activity

### Run Manual Backup

1. Open Backrest UI
2. Select backup plan from sidebar
3. Click "Run Now" button
4. Monitor progress in activity log

### Browse Snapshots

1. Select repository from sidebar
2. Click "Browse" tab
3. Navigate snapshot tree by date
4. Select files/folders to view

### Restore Files

1. Browse to desired snapshot
2. Select files/folders to restore
3. Click "Restore" button
4. Choose destination:
   - **Original location**: Overwrites existing files
   - **Custom path**: Restores to specified location
5. Confirm and monitor progress

### Check Backup Status

1. Select backup plan
2. View "Recent Runs" section
3. Check for:
   - ✅ Success (green)
   - ⚠️ Warning (yellow) - partial issues
   - ❌ Failed (red) - needs investigation

### View Logs

```bash
# Via kubectl
kubectl logs -n backrest deployment/backrest --tail=100

# Via MCP
infrastructure-mcp: kubectl_logs(namespace="backrest", pod_name="backrest")
```

## Troubleshooting

### SSH Connection Failed

1. **Verify SSH key is installed on target**:
   ```bash
   ssh root@<target> "cat /root/.ssh/authorized_keys | grep backrest"
   ```

2. **Test SSH from Backrest pod**:
   ```bash
   kubectl exec -n backrest deployment/backrest -- ssh -o StrictHostKeyChecking=no -T iac
   ```

3. **Verify SSH config is mounted**:
   ```bash
   kubectl exec -n backrest deployment/backrest -- cat /root/.ssh/config
   ```

4. **Check key permissions**:
   ```bash
   kubectl exec -n backrest deployment/backrest -- ls -la /root/.ssh/
   # id_ed25519 should be 0600
   ```

### S3 Connection Failed

1. **Verify Garage is running**:
   ```bash
   curl http://10.20.0.103:30188
   # Expected: 403 Forbidden (anonymous access denied)
   ```

2. **Check S3 credentials in pod environment**:
   ```bash
   kubectl exec -n backrest deployment/backrest -- env | grep AWS
   ```

3. **Test with AWS CLI from pod**:
   ```bash
   kubectl exec -n backrest deployment/backrest -- aws s3 ls --endpoint-url=http://10.20.0.103:30188
   ```

### Backup Slow

1. Check network bandwidth between Backrest and target
2. Review exclude patterns - add large cache/temp directories
3. Enable restic compression if not enabled
4. Check target disk I/O

### Repository Locked

This happens if a backup was interrupted.

1. Check for running backups first
2. If no backups running, unlock via UI:
   - Select Repository → Actions → Unlock
3. Or via restic CLI:
   ```bash
   kubectl exec -n backrest deployment/backrest -- restic unlock -r s3:http://10.20.0.103:30188/backrest
   ```

### "Permission Denied" During Backup

1. Check target paths are readable by root
2. Check SELinux/AppArmor on target
3. Verify SSH user has required permissions

## Kubernetes Resources

### Namespace
```
backrest
```

### Deployment
```yaml
Name: backrest
Image: garethgeorge/backrest:latest
Port: 9898
```

### Service
```yaml
Name: backrest
Type: NodePort
Port: 9898
NodePort: 31115
```

### Ingress
```yaml
Name: backrest
Host: backrest.kernow.io
IngressClass: traefik
```

### Secrets

| Secret | Contents | Source |
|--------|----------|--------|
| `backrest-s3-credentials` | AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY | Infisical `/backups/garage` |
| `backrest-ssh-keys` | id_ed25519, id_ed25519.pub, config | Infisical `/backups/backrest` |

### PVCs

| PVC | Size | Purpose |
|-----|------|---------|
| `backrest-data` | 1Gi | Config, database |
| `backrest-cache` | 5Gi | Restic cache |

## Monitoring

### Gatus Health Check

Backrest is monitored by Gatus at https://gatus.kernow.io:
- Endpoint: http://10.20.0.40:31115
- Expected: HTTP 200
- Interval: 60s

### Alerts

Backup failures trigger alerts via Gatus → Keep → alerting pipeline.

## Adding a New Backup Target

### 1. Install SSH Key on Target

```bash
PUBLIC_KEY=$(infisical secrets get SSH_PUBLIC_KEY --path=/backups/backrest --plain)
ssh root@<new-host> "mkdir -p /root/.ssh && echo '$PUBLIC_KEY' >> /root/.ssh/authorized_keys"
```

### 2. Update SSH Config Secret

Edit `/home/agentic_lab/kubernetes/applications/backrest/ssh-secret.yaml`:
```yaml
# Add new host entry to config
Host <new-host>
  HostName <ip-address>
  User root
  IdentityFile /root/.ssh/id_ed25519
```

### 3. Commit and Sync

```bash
/home/scripts/git-commit-submodule.sh agentic_lab "feat(backrest): add <new-host> SSH config"

# Sync ArgoCD
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig \
  kubectl patch application backrest -n argocd --type merge \
  -p '{"operation": {"initiatedBy": {"username": "claude"}, "sync": {"prune": true}}}'
```

### 4. Create Backup Plan in UI

1. Open Backrest UI
2. Click "Add Plan"
3. Configure:
   - Name: `<host>-daily` or `<host>-weekly`
   - Repository: garage-s3
   - Host: `<new-host>` (from SSH config)
   - Paths: List of paths to backup
   - Excludes: Cache, temp, log directories
   - Schedule: Cron expression
   - Retention: Daily/weekly/monthly counts

## Repository Password

The restic repository password is stored in Backrest's encrypted config. If you need to access the repository directly:

1. Export config from Backrest UI (Settings → Export)
2. The exported JSON contains the encrypted repository password
3. Or check Backrest's internal database in the `backrest-data` PVC

**Important**: The repository password is critical. If lost, backups cannot be restored. Ensure it's documented securely.

## Disaster Recovery

### If Backrest Pod is Lost

1. ArgoCD will recreate the deployment
2. PVCs preserve config and cache
3. Repository data is safe in Garage S3
4. SSH keys are in Kubernetes secrets (from Infisical)

### If Config PVC is Lost

1. Recreate backup plans manually in UI
2. Repository (in Garage) is intact
3. Historical backups still accessible

### If Garage Storage is Lost

1. Backups are gone (rebuild from PBS if available)
2. Reconfigure Backrest with new repository
3. Start fresh backup cycle

## Related Runbooks

- `/home/agentic_lab/runbooks/infrastructure/backup-overview.md` - Overall strategy
- `/home/agentic_lab/runbooks/infrastructure/garage-operations.md` - S3 storage
- `/home/agentic_lab/runbooks/infrastructure/pbs-operations.md` - PBS disaster recovery
- `/home/agentic_lab/runbooks/infrastructure/velero-operations.md` - K8s backups

## Secrets

| Location | Keys |
|----------|------|
| Infisical `/backups/garage` | ACCESS_KEY_ID, SECRET_ACCESS_KEY, ENDPOINT |
| K8s Secret `backrest-ssh-keys` | id_ed25519, id_ed25519.pub, config |

**Note**: SSH keys are stored directly in Kubernetes secret rather than Infisical due to API sync issues during initial setup.
