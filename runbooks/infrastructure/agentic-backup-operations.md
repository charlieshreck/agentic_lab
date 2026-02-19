# Agentic Cluster Backup Operations

## Overview

Application-level backups for the agentic cluster (10.20.0.0/24). These backups exist because:
- Velero cannot back up `local-path` storage class volumes (hostPath type)
- Each service requires application-specific backup procedures
- Data is stored in Garage S3 (`backrest` bucket, `agentic/` prefix)

## Architecture

```
┌────────────────────────────────────────────────────────────────────────────┐
│                    AGENTIC CLUSTER BACKUP ARCHITECTURE                      │
├────────────────────────────────────────────────────────────────────────────┤
│                                                                            │
│   BACKUP CRONJOBS (ai-platform namespace)                                  │
│   ───────────────────────────────────────                                  │
│                                                                            │
│   ┌──────────────┐ ┌──────────────┐ ┌────────────┐ ┌──────────────┐       │
│   │ postgresql-  │ │ qdrant-      │ │ redis-     │ │ neo4j-       │       │
│   │ backup       │ │ backup       │ │ backup     │ │ backup       │       │
│   │ 2:00 AM      │ │ 2:30 AM      │ │ 3:00 AM    │ │ 3:30 AM      │       │
│   └──────┬───────┘ └──────┬───────┘ └─────┬──────┘ └──────┬───────┘       │
│          │                │               │               │               │
│          ▼                ▼               ▼               ▼               │
│   ┌────────────────────────────────────────────────────────────────────┐  │
│   │                      GARAGE S3 (10.10.0.103:30188)                  │  │
│   │                      Bucket: backrest                               │  │
│   │                                                                     │  │
│   │   agentic/postgresql/YYYYMMDD-HHMMSS/*.dump                        │  │
│   │   agentic/qdrant/YYYYMMDD-HHMMSS/*.snapshot                        │  │
│   │   agentic/redis/YYYYMMDD-HHMMSS/*.rdb.gz                           │  │
│   │   agentic/neo4j/YYYYMMDD-HHMMSS/*.tar.gz                           │  │
│   └────────────────────────────────────────────────────────────────────┘  │
│                                                                            │
└────────────────────────────────────────────────────────────────────────────┘
```

## Backup Schedule

| Service | Schedule | Retention | Data Type |
|---------|----------|-----------|-----------|
| PostgreSQL | 2:00 AM UTC | 14 days | pg_dump (custom format) |
| Qdrant | 2:30 AM UTC | 14 days | Qdrant snapshots |
| Redis | 3:00 AM UTC | 7 days | RDB dump or key export |
| Neo4j | 3:30 AM UTC | 14 days | Cypher JSON export |

## What's Backed Up

### PostgreSQL
- **Databases**: All non-template databases (outline, langgraph, etc.)
- **Format**: pg_dump custom format with compression
- **Recovery**: Full database restore possible

### Qdrant
- **Collections**: All collections (runbooks, entities, decisions, documentation, etc.)
- **Format**: Native Qdrant snapshots
- **Recovery**: Collection-level restore via Qdrant API

### Redis
- **Data**: All keys (primarily session/cache data)
- **Format**: RDB dump or JSON key export
- **Recovery**: Less critical (session data can be regenerated)

### Neo4j
- **Data**: All nodes and relationships
- **Format**: JSON export of nodes and relationships
- **Recovery**: Cypher-based import (requires custom script)

## S3 Storage Structure

```
s3://backrest/
├── agentic/
│   ├── postgresql/
│   │   └── 20260121-020000/
│   │       ├── outline.dump
│   │       └── langgraph.dump
│   ├── qdrant/
│   │   └── 20260121-023000/
│   │       ├── runbooks-<snapshot-id>
│   │       ├── entities-<snapshot-id>
│   │       └── ...
│   ├── redis/
│   │   └── 20260121-030000/
│   │       └── redis-keys-20260121-030000.json.gz
│   └── neo4j/
│       └── 20260121-033000/
│           └── neo4j-20260121-033000.tar.gz
```

## Common Operations

### Check Backup Status

```bash
# Set kubeconfig
export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig

# List recent backup jobs
kubectl get jobs -n ai-platform -l app.kubernetes.io/component=backup

# View most recent backup logs
kubectl logs -n ai-platform job/postgresql-backup-<timestamp> --tail=50
kubectl logs -n ai-platform job/qdrant-backup-<timestamp> --tail=50
```

### Trigger Manual Backup

```bash
# PostgreSQL
kubectl create job --from=cronjob/postgresql-backup postgresql-backup-manual -n ai-platform

# Qdrant
kubectl create job --from=cronjob/qdrant-backup qdrant-backup-manual -n ai-platform

# Watch progress
kubectl logs -n ai-platform job/postgresql-backup-manual -f
```

### List Backups in S3

```bash
# From any machine with S3 credentials
export AWS_ACCESS_KEY_ID=<from infisical>
export AWS_SECRET_ACCESS_KEY=<from infisical>

# List PostgreSQL backups
aws s3 ls s3://backrest/agentic/postgresql/ --endpoint-url http://10.10.0.103:30188

# List Qdrant backups
aws s3 ls s3://backrest/agentic/qdrant/ --endpoint-url http://10.10.0.103:30188
```

## Recovery Procedures

### PostgreSQL Recovery

```bash
# 1. Download backup
aws s3 cp s3://backrest/agentic/postgresql/20260121-020000/outline.dump /tmp/ \
  --endpoint-url http://10.10.0.103:30188

# 2. Restore to PostgreSQL
kubectl exec -it postgresql-0 -n ai-platform -- \
  pg_restore -U postgres -d outline --clean /tmp/outline.dump

# Alternative: Restore via port-forward
kubectl port-forward svc/postgresql 5432:5432 -n ai-platform &
pg_restore -h localhost -U postgres -d outline --clean /tmp/outline.dump
```

### Qdrant Recovery

```bash
# 1. Download snapshot
aws s3 cp s3://backrest/agentic/qdrant/20260121-023000/runbooks-<snapshot-id> /tmp/ \
  --endpoint-url http://10.10.0.103:30188

# 2. Upload to Qdrant
curl -X POST "http://10.20.0.40:6333/collections/runbooks/snapshots/upload" \
  -H "Content-Type: multipart/form-data" \
  -F "snapshot=@/tmp/runbooks-<snapshot-id>"

# 3. Or recover from snapshot
curl -X PUT "http://10.20.0.40:6333/collections/runbooks/snapshots/recover" \
  -H "Content-Type: application/json" \
  -d '{"location": "file:///tmp/runbooks-<snapshot-id>"}'
```

### Neo4j Recovery

```bash
# 1. Download and extract backup
aws s3 cp s3://backrest/agentic/neo4j/20260121-033000/neo4j-20260121-033000.tar.gz /tmp/ \
  --endpoint-url http://10.10.0.103:30188
tar -xzf /tmp/neo4j-20260121-033000.tar.gz -C /tmp/

# 2. Import via Cypher (custom script needed)
# The backup contains nodes.json and relationships.json
# Requires Python script to convert JSON to Cypher CREATE statements
```

## Troubleshooting

### Backup Job Failed

1. Check job logs:
   ```bash
   kubectl logs -n ai-platform job/<job-name>
   ```

2. Common issues:
   - **S3 connection failed**: Check Garage is running (`curl http://10.10.0.103:30188`)
   - **Auth failed**: Verify `backup-s3-credentials` secret exists
   - **Service unavailable**: Check target service is running (postgresql, qdrant, etc.)

### Missing Backups

1. Check CronJob schedule:
   ```bash
   kubectl get cronjob -n ai-platform
   ```

2. Check for suspended CronJobs:
   ```bash
   kubectl get cronjob -n ai-platform -o jsonpath='{range .items[*]}{.metadata.name}: {.spec.suspend}{"\n"}{end}'
   ```

### S3 Credentials Issues

1. Check InfisicalSecret sync:
   ```bash
   kubectl describe infisicalsecret backup-s3-infisical -n ai-platform
   ```

2. Verify secret exists:
   ```bash
   kubectl get secret backup-s3-credentials -n ai-platform
   ```

## Monitoring

### Gatus Checks

Add backup health checks to Gatus:
- Check CronJob last successful run time
- Alert if backup older than 48 hours

### Prometheus Metrics

Kubernetes exposes CronJob metrics:
- `kube_cronjob_status_last_schedule_time`
- `kube_cronjob_status_last_successful_time`
- `kube_job_status_succeeded`
- `kube_job_status_failed`

## Secrets

| Location | Contents |
|----------|----------|
| Infisical `/backups/garage` | AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY |
| K8s `backup-s3-credentials` | Synced from Infisical |
| K8s `postgresql-credentials` | PostgreSQL username/password |
| K8s `neo4j-credentials` | Neo4j auth (optional) |

## Related Runbooks

- `/home/agentic_lab/runbooks/infrastructure/backup-overview.md` - Overall backup strategy
- `/home/agentic_lab/runbooks/infrastructure/garage-operations.md` - S3 storage operations
- `/home/agentic_lab/runbooks/infrastructure/velero-operations.md` - K8s PVC backups (prod cluster)

## Why Not Velero?

Velero uses file-system backup for PVCs, which requires CSI volumes with snapshot support. The agentic cluster uses `local-path` storage class which creates `hostPath` volumes. These are NOT supported by Velero's file-system backup because:

1. hostPath volumes don't have snapshot capability
2. No CSI driver to interface with
3. Data lives directly on the node filesystem

**Solution**: Application-level backups (this system) that use each application's native backup/export capabilities.
