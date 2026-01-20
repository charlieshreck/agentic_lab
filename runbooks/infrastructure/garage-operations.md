# Garage S3 Operations Runbook

## Overview

Garage is a lightweight, self-hosted S3-compatible object storage system deployed on TrueNAS-HDD. It serves as the unified storage backend for:
- **Velero** backups (Kubernetes PVC snapshots)
- **Backrest** repositories (VM/LXC file-level backups via restic)

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         GARAGE ON TRUENAS-HDD                            │
│                           10.20.0.103                                    │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                     TrueNAS SCALE Apps                           │   │
│   │   App: garage                                                    │   │
│   │   Dataset: /mnt/Taupo/ix-applications/releases/garage/...       │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                              │                                           │
│                              ▼                                           │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │                      Exposed Ports                                │  │
│   │                                                                   │  │
│   │   S3 API:    http://10.20.0.103:30188  (client operations)       │  │
│   │   Web UI:    http://10.20.0.103:30186  (management)              │  │
│   │   Admin API: http://10.20.0.103:30190  (cluster management)      │  │
│   │   RPC:       10.20.0.103:30187         (internal cluster)        │  │
│   │   K2V API:   10.20.0.103:30189         (key-value, unused)       │  │
│   └──────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│   Storage Pool: Taupo (13.3 TB available)                               │
│   Replication: 1 (single node)                                          │
│   Region: garage                                                         │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## Access

| Service | URL | Purpose |
|---------|-----|---------|
| S3 API | http://10.20.0.103:30188 | Bucket operations, uploads, downloads |
| Web UI | http://10.20.0.103:30186 or https://garage.kernow.io | Management interface |
| Admin API | http://10.20.0.103:30190 | Cluster configuration, layout |

## Credentials

All credentials stored in Infisical at `/backups/garage`:

| Key | Description |
|-----|-------------|
| `ACCESS_KEY_ID` | S3 access key (e.g., `GKf2aa99d99a269da7f9f8e5e4`) |
| `SECRET_ACCESS_KEY` | S3 secret key |
| `ADMIN_TOKEN` | Admin API token (for garage CLI/API) |
| `ENDPOINT` | S3 endpoint URL |

### Retrieve Credentials

```bash
# Via Infisical CLI
/root/.config/infisical/secrets.sh get /backups/garage ACCESS_KEY_ID
/root/.config/infisical/secrets.sh get /backups/garage SECRET_ACCESS_KEY
/root/.config/infisical/secrets.sh get /backups/garage ADMIN_TOKEN

# Via MCP
infisical-mcp: get_secret(path="/backups/garage", key="ACCESS_KEY_ID")
```

## Buckets

| Bucket | Purpose | Consumers |
|--------|---------|-----------|
| `velero-prod` | Production cluster Velero backups | Velero (prod) |
| `velero-agentic` | Agentic cluster Velero backups | Velero (agentic) |
| `velero-monit` | Monitoring cluster Velero backups | Velero (monit) |
| `backrest` | Backrest restic repositories | Backrest |

## Common Operations

### Check Garage Health

```bash
# Via S3 API (anonymous request returns 403)
curl -I http://10.20.0.103:30188
# Expected: HTTP/1.1 403 Forbidden

# Via Admin API
curl -H "Authorization: Bearer $(infisical secrets get ADMIN_TOKEN --path=/backups/garage --plain)" \
  http://10.20.0.103:30190/v1/status
```

### List Buckets (via AWS CLI)

```bash
export AWS_ACCESS_KEY_ID=$(infisical secrets get ACCESS_KEY_ID --path=/backups/garage --plain)
export AWS_SECRET_ACCESS_KEY=$(infisical secrets get SECRET_ACCESS_KEY --path=/backups/garage --plain)

aws s3 ls --endpoint-url=http://10.20.0.103:30188
```

### Create Bucket

```bash
aws s3 mb s3://new-bucket --endpoint-url=http://10.20.0.103:30188
```

### List Objects in Bucket

```bash
aws s3 ls s3://backrest/ --endpoint-url=http://10.20.0.103:30188
```

### Check Bucket Size

```bash
aws s3 ls s3://backrest/ --recursive --summarize --endpoint-url=http://10.20.0.103:30188 | tail -2
```

## Admin Operations

### Check Cluster Status

```bash
ADMIN_TOKEN=$(infisical secrets get ADMIN_TOKEN --path=/backups/garage --plain)

curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://10.20.0.103:30190/v1/status | jq
```

### Check Layout

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://10.20.0.103:30190/v1/layout | jq
```

### Create API Key

```bash
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  http://10.20.0.103:30190/v1/key \
  -d '{"name": "new-key-name"}' | jq
```

### List API Keys

```bash
curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://10.20.0.103:30190/v1/key | jq
```

## TrueNAS SCALE App Management

### Access TrueNAS UI
- URL: https://10.20.0.103 (TrueNAS-HDD)
- Navigate to: Apps → Installed Applications → garage

### Restart Garage App
1. In TrueNAS UI: Apps → garage → Stop → Start
2. Or via shell: `k3s kubectl rollout restart -n ix-garage deployment/garage`

### View Logs
1. In TrueNAS UI: Apps → garage → Logs
2. Or via shell: `k3s kubectl logs -n ix-garage -l app.kubernetes.io/name=garage`

### Update Garage
1. In TrueNAS UI: Apps → garage → Update
2. Review release notes before updating
3. Test after update: `curl http://10.20.0.103:30188`

## Storage Considerations

### Current Capacity
- Pool: Taupo (ZFS RAIDZ2)
- Available: ~13 TB
- Used by PBS: ~240 GB
- Used by Garage: Growing (check periodically)

### Monitoring Storage
```bash
# Check TrueNAS pool status
truenas-mcp: truenas_list_pools(instance="hdd")

# Check specific usage
truenas-mcp: truenas_get_disk_usage(instance="hdd")
```

### Data Retention
Retention is handled by consumers:
- **Velero**: Configured in backup schedules (7 daily, 30 weekly)
- **Backrest**: Configured per backup plan (varies)

Garage itself does not implement retention policies - it stores whatever is uploaded.

## Integration with Consumers

### Velero Configuration

Velero BackupStorageLocation pointing to Garage:
```yaml
apiVersion: velero.io/v1
kind: BackupStorageLocation
metadata:
  name: default
  namespace: velero
spec:
  provider: aws
  bucket: velero-prod  # or velero-agentic, velero-monit
  config:
    region: garage
    s3ForcePathStyle: "true"
    s3Url: http://10.20.0.103:30188
  credential:
    name: garage-credentials
    key: cloud
```

### Backrest Configuration

In Backrest UI, repository configuration:
- **Type**: S3
- **Endpoint**: http://10.20.0.103:30188
- **Bucket**: backrest
- **Region**: garage
- **Access Key**: From Infisical
- **Secret Key**: From Infisical

Repository URI format: `s3:http://10.20.0.103:30188/backrest`

## Troubleshooting

### Connection Refused
1. Check Garage app is running in TrueNAS
2. Check port mapping: `k3s kubectl get svc -n ix-garage`
3. Check firewall allows traffic from source

### 403 Forbidden on Authenticated Request
1. Verify credentials are correct
2. Check bucket policy allows access
3. Verify key has permissions for operation

### Slow Uploads/Downloads
1. Check TrueNAS disk I/O: `truenas-mcp: truenas_get_disk_usage()`
2. Check network bandwidth between source and TrueNAS
3. Consider Garage is single-node (no parallelism)

### "Layout Not Ready" Error
Garage requires layout configuration after fresh install:
```bash
# Get node ID
NODE_ID=$(curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://10.20.0.103:30190/v1/status | jq -r '.node')

# Assign capacity (10TB = 10000000000000 bytes)
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  http://10.20.0.103:30190/v1/layout \
  -d "{\"node_id\": \"$NODE_ID\", \"zone\": \"dc1\", \"capacity\": 10000000000000}"

# Apply layout
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://10.20.0.103:30190/v1/layout/apply \
  -d '{"version": 1}'
```

### Bucket Already Exists Error
Bucket names are global across the Garage cluster. Choose unique names.

## Monitoring

### Gatus Health Check
Garage is monitored by Gatus at http://10.30.0.120:31100:
- **Garage S3 API**: Expects 403 (anonymous request blocked)
- **Garage Web UI**: Expects 200

### Metrics (Future)
Garage exposes Prometheus metrics at `/metrics` on the admin port.
TODO: Add to VictoriaMetrics scrape config.

## Disaster Recovery

### Data Location
All Garage data is stored in the TrueNAS dataset associated with the app.
This is included in TrueNAS ZFS snapshots.

### Restore from TrueNAS Snapshot
1. Identify snapshot with Garage data
2. Restore dataset from snapshot
3. Restart Garage app

### Rebuild from Scratch
1. Install Garage app in TrueNAS SCALE
2. Configure ports (30186-30190)
3. Set admin token
4. Apply layout configuration
5. Create buckets
6. Create API keys
7. Update Infisical secrets if keys changed
8. Resync Velero/Backrest (will re-upload data)

## Security Notes

- Garage runs on internal network only (10.20.0.0/24)
- S3 API requires authentication (no anonymous access)
- Admin API requires bearer token
- All credentials in Infisical, not in git

## Related Runbooks

- `/home/agentic_lab/runbooks/infrastructure/backup-overview.md` - Overall backup strategy
- `/home/agentic_lab/runbooks/infrastructure/backrest-operations.md` - Backrest procedures
- `/home/agentic_lab/runbooks/infrastructure/velero-operations.md` - Velero procedures

## Infisical Paths

| Path | Keys |
|------|------|
| `/backups/garage` | ACCESS_KEY_ID, SECRET_ACCESS_KEY, ADMIN_TOKEN, ENDPOINT |
| `/backups/backrest` | SSH_PRIVATE_KEY, SSH_PUBLIC_KEY |
