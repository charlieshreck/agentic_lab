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
|----------|-------------|-----------|-----------|---------|
| Prod K8s PVCs | Velero | Daily 2AM + Weekly Sunday 3AM | 7d + 30d | Garage |
| Agentic K8s PVCs | Velero | Daily 2AM + Weekly Sunday 3AM | 7d + 30d | Garage |
| Monit K8s PVCs | Velero | Daily 2:30AM + Weekly Sunday 3:30AM | 7d + 30d | Garage |
| IAC LXC (100) | Backrest | Daily | 14d | Garage |
| Plex VM (450) | Backrest | Daily | 7d | Garage |
| UniFi VM (451) | Backrest | Daily | 7d | Garage |
| TrueNAS configs | Backrest | Weekly | 30d | Garage |
| Critical VMs | PBS | Weekly Sunday 2AM | 4 weekly | TrueNAS PBS |

## Component Details

### Velero (Kubernetes)
- **Prod**: Daily 2AM (7d) + Weekly 3AM Sunday (30d)
- **Agentic**: Daily 2AM (7d) + Weekly 3AM Sunday (30d)
- **Monit**: Daily 2:30AM (7d) + Weekly 3:30AM Sunday (30d)
- **Backend**: Garage S3 at http://10.20.0.103:30188
- **Buckets**: velero-prod, velero-agentic, velero-monit

### Backrest (VM/LXC File-Level)
- **UI**: http://10.20.0.40:31115 or https://backrest.kernow.io
- **Backend**: Garage S3 (backrest bucket)
- **SSH Access**: Via dedicated keypair stored in Infisical `/backups/backrest`

### PBS (Disaster Recovery)
- **Server**: https://10.10.0.150:8007
- **Datastore**: pbs-ruapehu on TrueNAS HDD
- **Purpose**: Full VM snapshots for rapid recovery

### Garage (S3 Storage)
- **Admin**: http://garage.kernow.io (admin token in Infisical)
- **S3 API**: http://10.20.0.103:30188
- **Web UI**: http://10.20.0.103:30186
- **Credentials**: Infisical `/backups/garage`

## Access Quick Reference

| Service | Internal URL | External URL |
|---------|-------------|--------------|
| Backrest | http://10.20.0.40:31115 | https://backrest.kernow.io |
| Garage Web | http://10.20.0.103:30186 | https://garage.kernow.io |
| PBS | https://10.10.0.150:8007 | N/A |
| Gatus (monitoring) | http://10.30.0.120:31100 | https://gatus.kernow.io |

## Monitoring

### Gatus Endpoints
- Garage S3 API - checks anonymous 403 response
- Garage Web UI - checks HTTP 200
- Backrest - checks HTTP 200

### Alerts
Backup failures are sent to Keep alert aggregation platform via Gatus webhooks.

## Infisical Secrets

| Path | Contains |
|------|----------|
| `/backups/garage` | ACCESS_KEY_ID, SECRET_ACCESS_KEY, ENDPOINT |
| `/backups/backrest` | SSH_PRIVATE_KEY, SSH_PUBLIC_KEY |

## Recovery Procedures

### Kubernetes PVC Recovery (Velero)
```bash
# List backups
velero backup get

# Restore specific resources
velero restore create --from-backup <backup-name> \
  --include-namespaces <namespace> \
  --include-resources persistentvolumeclaims,persistentvolumes
```

### VM File Recovery (Backrest)
1. Access Backrest UI at http://10.20.0.40:31115
2. Select repository → Browse snapshots
3. Restore files to target location

### Full VM Recovery (PBS)
1. Access PBS UI at https://10.10.0.150:8007
2. Select snapshot → Restore
3. Choose target node and storage

## Related Runbooks
- `/home/agentic_lab/runbooks/infrastructure/velero-operations.md`
- `/home/agentic_lab/runbooks/infrastructure/backrest-operations.md`
- `/home/agentic_lab/runbooks/infrastructure/pbs-operations.md`
