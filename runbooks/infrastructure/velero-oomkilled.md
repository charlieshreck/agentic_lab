# Velero OOMKilled (HomelabPodOOMKilled)

## Alert
`HomelabPodOOMKilled` — container `velero` in namespace `velero` on the production cluster.

## Symptoms
- AlertManager fires `HomelabPodOOMKilled` for pod `velero-*` in namespace `velero`
- Pod restart count increments (typically after 2+ days uptime)
- OOM typically coincides with backup windows (02:00–08:00 UTC daily)

## Root Cause
Velero v1.17.1 with the kopia uploader and `defaultVolumesToFsBackup: true` gradually accumulates memory over multiple backup cycles. With 5 kopia repositories (apps, argocd, media, traefik, velero) and daily full filesystem backups across all non-system namespaces, the server process can exceed 512Mi after several days.

The OOM typically occurs several hours after the daily backup starts at 02:00 UTC, as Velero processes backup completion, maintenance job scheduling, and GC of expired backups concurrently.

## Investigation Steps

```bash
# Check current pod state
kubectl get pods -n velero --context admin@homelab-prod

# Check last termination reason
kubectl describe pod -n velero <velero-pod-name> --context admin@homelab-prod | grep -A5 "Last State"

# Check current memory usage
# PromQL: container_memory_working_set_bytes{namespace="velero",container="velero"}
```

## Fix

Memory limit is configured in:
```
prod_homelab/kubernetes/argocd-apps/platform/velero-app.yaml
```

Under `helm.valuesObject.resources`:
```yaml
resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: 500m
    memory: 1Gi  # Was 512Mi — increased 2026-02-24
```

If OOMs recur after raising to 1Gi, consider:
1. Raising to 2Gi
2. Reducing backup scope (exclude more namespaces)
3. Checking Velero release notes for memory fixes

## GitOps

Edit `prod_homelab/kubernetes/argocd-apps/platform/velero-app.yaml`, commit + push. ArgoCD auto-syncs and restarts Velero with new limits.

```bash
git -C /home/prod_homelab add kubernetes/argocd-apps/platform/velero-app.yaml
git -C /home/prod_homelab commit -m "fix: increase velero memory limit"
git -C /home/prod_homelab push origin main
```

## Resolution History

| Date | Incident | Old Limit | New Limit | Notes |
|------|----------|-----------|-----------|-------|
| 2026-02-24 | #236, #237 | 512Mi | 1Gi | OOM after 3.5d uptime during daily kopia backup |
