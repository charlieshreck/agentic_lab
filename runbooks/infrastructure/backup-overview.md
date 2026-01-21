# Backup Infrastructure Overview

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        UNIFIED BACKUP INFRASTRUCTURE                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   KUBERNETES BACKUPS (Velero)           VM/LXC/BAREMETAL (Backrest)        │
│   ─────────────────────────             ───────────────────────────        │
│                                                                             │
│   ┌─────────┐ ┌─────────┐ ┌─────────┐   ┌──────────────────────────┐      │
│   │  PROD   │ │ AGENTIC │ │  MONIT  │   │       BACKREST           │      │
│   │ Velero  │ │ Velero  │ │ Velero  │   │   (Web UI + Scheduler)   │      │
│   └────┬────┘ └────┬────┘ └────┬────┘   │   Port: 31115            │      │
│        │           │           │         └───────────┬──────────────┘      │
│        └───────────┴───────────┘                     │                     │
│                    │                                 │                     │
│                    ▼                                 ▼                     │
│   ┌────────────────────────────────────────────────────────────────────┐  │
│   │                     GARAGE (S3-Compatible)                          │  │
│   │                     TrueNAS HDD - 10.20.0.103                       │  │
│   │                     Buckets: velero-*, backrest                     │  │
│   │                     Capacity: 13TB available                        │  │
│   └────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│   DISASTER RECOVERY LAYER (PBS)                                            │
│   ─────────────────────────────                                            │
│   PBS Server: 10.10.0.150                                                  │
│   Weekly VM snapshots for critical systems                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Backup Matrix

| Platform | Backup Tool | Frequency | Retention | Storage |
|----------|-------------|-----------|-----------|---------||
| Prod K8s PVCs | Velero | Daily 2AM + Weekly Sunday 3AM | 7d + 30d | Garage |
| Agentic K8s PVCs | Velero | Daily 2AM + Weekly Sunday 3AM | 7d + 30d | Garage |
| Monit K8s PVCs | Velero | Daily 2:30AM + Weekly Sunday 3:30AM | 7d + 30d | Garage |
| IAC LXC (100) | Backrest | Daily 3AM | 14d + 4w | Garage |
| Plex VM (450) | Backrest | Daily 4AM | 7d + 4w | Garage |
| UniFi VM (451) | ❌ Disabled | - | - | - |
| TrueNAS configs | Backrest | Weekly Sunday 6AM | 4w + 2m | Garage |
| Critical VMs | PBS | Weekly Sunday 2AM | 4 weekly | TrueNAS PBS |

## Component Details

### Velero (Kubernetes PVC Backups)

Velero handles Kubernetes-native backups including PVCs, ConfigMaps, Secrets, and custom resources.

| Cluster | Schedule | Retention | Bucket |
|---------|----------|-----------|--------|
| **Prod** | Daily 2AM (7d) + Weekly 3AM Sunday (30d) | As scheduled | velero-prod |
| **Agentic** | Daily 2AM (7d) + Weekly 3AM Sunday (30d) | As scheduled | velero-agentic |
| **Monit** | Daily 2:30AM (7d) + Weekly 3:30AM Sunday (30d) | As scheduled | velero-monit |

- **Backend**: Garage S3 at http://10.20.0.103:30188
- **Credentials**: Infisical `/backups/garage`
- **Runbook**: `/home/agentic_lab/runbooks/infrastructure/velero-operations.md`

### Backrest (VM/LXC File-Level Backups)

Backrest provides a web UI for managing restic-based backups of VMs and LXC containers.
Backups run via SSH commandPrefix - restic executes on the remote host and streams data to Garage.

| Plan | Host | Schedule | Paths | Retention |
|------|------|----------|-------|-----------|
| **iac-daily** | 10.10.0.175 | Daily 3AM | /home, /root, /etc | 14d, 4w |
| **plex-daily** | 10.10.0.50 | Daily 4AM | /opt/plex/config/..., /opt/plex/compose | 7d, 4w |
| **truenas-weekly** | 10.20.0.103 | Sunday 6AM | /root | 4w, 2m |

**Note**: UniFi VM (10.10.0.51) backup is currently **disabled** - SSH access requires password authentication. Needs manual SSH key setup.

- **UI**: https://backrest.kernow.io or http://10.20.0.40:31115
- **Backend**: Garage S3 (backrest bucket)
- **SSH Key**: `ssh-ed25519 ...IJ...AAZ backrest-backup@kernow.io` (K8s secret `backrest-ssh-keys`)
- **Runbook**: `/home/agentic_lab/runbooks/infrastructure/backrest-operations.md`

### PBS (Proxmox Backup Server - Disaster Recovery)

PBS provides full VM snapshots for rapid bare-metal recovery scenarios.

| VM | Schedule | Purpose |
|----|----------|---------|
| IAC LXC (100) | Weekly Sunday 2AM | **CRITICAL** - Claude Code environment |
| Plex VM (450) | Weekly Sunday 2AM | Config/DB (media on TrueNAS) |
| UniFi VM (451) | Weekly Sunday 2AM | Network controller |

- **Server**: https://10.10.0.150:8007
- **Datastore**: pbs-ruapehu on TrueNAS HDD
- **Storage**: 13.3 TB available
- **Runbook**: `/home/agentic_lab/runbooks/infrastructure/pbs-operations.md`

### Garage (S3-Compatible Object Storage)

Garage is a lightweight S3-compatible storage system running on TrueNAS-HDD.

| Port | Service | Purpose |
|------|---------|---------|
| 30188 | S3 API | Client operations |
| 30186 | Web UI | Management interface |
| 30190 | Admin API | Cluster configuration |

- **Admin**: https://garage.kernow.io (admin token in Infisical)
- **S3 API**: http://10.20.0.103:30188
- **Credentials**: Infisical `/backups/garage`
- **Runbook**: `/home/agentic_lab/runbooks/infrastructure/garage-operations.md`

## Access Quick Reference

| Service | Internal URL | External URL |
|---------|-------------|--------------||
| Backrest | http://10.20.0.40:31115 | https://backrest.kernow.io |
| Garage Web | http://10.20.0.103:30186 | https://garage.kernow.io |
| PBS | https://10.10.0.150:8007 | N/A |
| Gatus (monitoring) | http://10.30.0.120:31100 | https://gatus.kernow.io |

## Monitoring

### Gatus Endpoints

| Endpoint | Check | Expected |
|----------|-------|----------|
| Garage S3 API | http://10.20.0.103:30188 | 403 Forbidden |
| Garage Web UI | http://10.20.0.103:30186 | 200 OK |
| Backrest | http://10.20.0.40:31115 | 200 OK |

### Alerts

Backup failures are sent to Keep alert aggregation platform via:
- Gatus webhooks (health check failures)
- Velero metrics (backup job failures)
- AlertManager rules (backup-related alerts)

## Secrets

| Location | Contains |
|----------|----------|
| Infisical `/backups/garage` | ACCESS_KEY_ID, SECRET_ACCESS_KEY, ENDPOINT, ADMIN_TOKEN |
| K8s secret `backrest-ssh-keys` | id_ed25519, id_ed25519.pub, config |

**Note**: Backrest SSH keys are stored directly in Kubernetes secret `backrest-ssh-keys` (backrest namespace) rather than synced from Infisical due to API sync issues.

## Recovery Procedures

### Kubernetes PVC Recovery (Velero)

```bash
# List backups
velero backup get

# Describe a backup
velero backup describe <backup-name> --details

# Restore specific resources
velero restore create --from-backup <backup-name> \
  --include-namespaces <namespace> \
  --include-resources persistentvolumeclaims,persistentvolumes

# Check restore status
velero restore describe <restore-name>
```

### VM File Recovery (Backrest)

1. Access Backrest UI at https://backrest.kernow.io
2. Select repository → Browse snapshots
3. Navigate to desired date/time
4. Select files → Restore
5. Choose destination (original or custom path)

### Full VM Recovery (PBS)

1. Access PBS UI at https://10.10.0.150:8007
2. Navigate to Datastore → pbs-ruapehu
3. Select VM snapshot
4. Right-click → Restore
5. Choose target node and storage
6. Start restored VM

### Disaster Recovery Scenarios

| Scenario | Recovery Method | RTO |
|----------|----------------|-----|
| PVC data loss | Velero restore | ~30 min |
| VM config corruption | Backrest file restore | ~15 min |
| VM total loss | PBS full restore | ~1 hour |
| Garage storage failure | Rebuild from PBS snapshots | ~4 hours |
| Complete site failure | PBS + off-site (TODO) | TBD |

## What's NOT Backed Up

- **Talos K8s VMs (400-403)**: Immutable, rebuilt from IaC
- **Media files**: On TrueNAS with ZFS redundancy
- **Container images**: Pulled from registries
- **Temporary data**: Caches, logs older than retention

## Design Decisions

### Why Garage Instead of MinIO?
- Lighter weight (single binary)
- No licensing concerns
- S3-compatible for Velero/restic
- Runs well on TrueNAS SCALE

### Why Backrest Instead of Direct Restic?
- Web UI for management
- Built-in scheduler
- Easy restore browsing
- Multiple repository support

### Why Both Backrest and PBS?
- **Backrest**: File-level, frequent, granular recovery
- **PBS**: Full VM snapshots, disaster recovery

## Related Runbooks

- `/home/agentic_lab/runbooks/infrastructure/velero-operations.md` - K8s backup procedures
- `/home/agentic_lab/runbooks/infrastructure/backrest-operations.md` - VM/LXC backup procedures
- `/home/agentic_lab/runbooks/infrastructure/garage-operations.md` - S3 storage operations
- `/home/agentic_lab/runbooks/infrastructure/pbs-operations.md` - PBS disaster recovery
