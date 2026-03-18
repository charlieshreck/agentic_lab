# PostgreSQL Major Version Upgrade

## Overview

PostgreSQL major version upgrades (e.g., 16 → 17 → 18) **cannot** be performed by simply
updating the container image tag. The on-disk data directory format changes between major
versions and PostgreSQL will refuse to start if the PGDATA was initialized by a different
major version.

**Current version**: PostgreSQL 16-alpine
**Cluster**: agentic (ai-platform namespace)
**Data**: NFS-backed PVC (`postgresql-data`)
**Dependent services**: langgraph, outline, error-hunter, incident-db

---

## Why This Requires a Runbook

Renovate PR #3 (2026-03-18) grouped `postgres:16-alpine → 18-alpine` with safe application
updates. This would have caused a total failure of all AI platform services using PostgreSQL.
The `renovate.json` now has a `database-major-upgrades` rule with `do-not-merge` label to
prevent this pattern from recurring.

---

## Pre-Upgrade Checklist

- [ ] PostgreSQL backup ran successfully within last 24h (CronJob `postgresql-backup`)
- [ ] Target version release notes reviewed for breaking changes
- [ ] All services using PostgreSQL identified and owners notified
- [ ] Maintenance window scheduled (expect 30–60 min downtime)
- [ ] Velero cluster backup triggered before starting

---

## Services Using PostgreSQL (ai-platform)

| Service | Database | Notes |
|---------|----------|-------|
| langgraph | langgraph | KAO incident broker state |
| outline | outline | Knowledge wiki |
| error-hunter | error_hunter / estate_work_queue | Estate ops controller |
| incident-db | incidents | Incident tracking |

---

## Upgrade Procedure: Dump/Restore Method

This is the safest approach. pg_upgrade requires more complex orchestration in K8s.

### Step 1 — Verify backup is current

```bash
# Check last postgresql-backup job
KUBECONFIG=/root/.kube/config kubectl get jobs -n ai-platform | grep postgresql-backup
KUBECONFIG=/root/.kube/config kubectl logs -n ai-platform job/<latest-backup-job>
```

### Step 2 — Take a manual pg_dumpall before starting

```bash
KUBECONFIG=/root/.kube/config kubectl exec -n ai-platform statefulset/postgresql -- \
  pg_dumpall -U $(kubectl get secret postgresql-credentials -n ai-platform -o jsonpath='{.data.USERNAME}' | base64 -d) \
  > /tmp/postgresql-full-dump-$(date +%Y%m%d).sql
```

Store this dump safely (copy to a persistent location outside the cluster).

### Step 3 — Scale down all dependent services

```bash
KUBECONFIG=/root/.kube/config kubectl scale deployment -n ai-platform \
  langgraph outline error-hunter alerting-pipeline --replicas=0
```

Verify all pods have terminated before continuing.

### Step 4 — Delete the existing StatefulSet data (destructive)

> ⚠️ Only proceed if you have a verified, complete dump from Step 2.

```bash
# Scale down PostgreSQL itself
KUBECONFIG=/root/.kube/config kubectl scale statefulset postgresql -n ai-platform --replicas=0

# Wait for pod to terminate
KUBECONFIG=/root/.kube/config kubectl wait --for=delete pod/postgresql-0 -n ai-platform --timeout=60s
```

### Step 5 — Update the image in git

Edit `agentic_lab/kubernetes/applications/postgresql/statefulset.yaml`:
```yaml
image: postgres:18-alpine   # or target version
```

Also update backup jobs:
- `kubernetes/applications/backups/postgresql-backup.yaml`
- `kubernetes/applications/incident-db/init-job.yaml`
- `kubernetes/applications/outline/db-init-job.yaml`

### Step 6 — Wipe the PVC data directory and redeploy

The PGDATA from PG16 is incompatible with PG18. You need a fresh init:

```bash
# Create a temporary pod to wipe the PVC
cat <<EOF | KUBECONFIG=/root/.kube/config kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: pgdata-wipe
  namespace: ai-platform
spec:
  restartPolicy: Never
  containers:
  - name: wipe
    image: busybox
    command: ["sh", "-c", "rm -rf /data/pgdata && echo DONE"]
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: postgresql-data-postgresql-0
EOF

# Wait for completion
KUBECONFIG=/root/.kube/config kubectl wait --for=condition=Succeeded pod/pgdata-wipe -n ai-platform --timeout=60s
KUBECONFIG=/root/.kube/config kubectl delete pod pgdata-wipe -n ai-platform
```

### Step 7 — Commit and push, let ArgoCD redeploy

```bash
/home/scripts/git-commit-submodule.sh agentic_lab "chore: upgrade postgresql from 16 to 18"
```

ArgoCD will deploy the new PG18 pod. The fresh PGDATA will be initialized by PG18.

### Step 8 — Restore from dump

```bash
# Wait for PostgreSQL to be ready
KUBECONFIG=/root/.kube/config kubectl wait --for=condition=Ready pod/postgresql-0 \
  -n ai-platform --timeout=120s

# Restore
KUBECONFIG=/root/.kube/config kubectl exec -i -n ai-platform statefulset/postgresql -- \
  psql -U $(kubectl get secret postgresql-credentials -n ai-platform -o jsonpath='{.data.USERNAME}' | base64 -d) \
  < /tmp/postgresql-full-dump-$(date +%Y%m%d).sql
```

### Step 9 — Scale services back up

```bash
KUBECONFIG=/root/.kube/config kubectl scale deployment -n ai-platform \
  langgraph outline error-hunter alerting-pipeline --replicas=1
```

### Step 10 — Verify

```bash
# Check all pods healthy
KUBECONFIG=/root/.kube/config kubectl get pods -n ai-platform

# Test langgraph endpoint
curl -s http://10.20.0.40:30800/health

# Check error-hunter estate queue
curl -s http://10.10.0.22:3456/api/estate/queue | jq '.count'
```

---

## Rollback

If anything goes wrong before Step 6 (data not yet wiped):

1. Scale PostgreSQL back to 1 replica (it will restart with old image if git not yet pushed)
2. Scale services back up

If PGDATA was wiped and restore failed:

1. The pg_dumpall from Step 2 is your only recovery path
2. Re-run the restore step with the dump file

---

## Version-Specific Notes

### PostgreSQL 17
- Released October 2024. No major breaking changes for our usage.
- SCRAM-SHA-256 is now the default password_encryption.

### PostgreSQL 18
- Released 2025 (beta/RC at time of writing). Review release notes before upgrading.
- Consider upgrading to 17 first as an intermediate step.

---

## Related

- Runbook: `infrastructure/agentic-backup-operations.md`
- Renovate rule: `kubernetes-apps` group now excludes database major upgrades
- Finding: estate finding #1237 (renovate_pr_pending, 2026-03-18)
