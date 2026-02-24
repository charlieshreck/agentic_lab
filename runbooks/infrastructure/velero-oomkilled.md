# Velero OOMKilled (HomelabPodOOMKilled)

## Alert
`HomelabPodOOMKilled` — container `velero` in namespace `velero` on the production cluster.

## Symptoms
- AlertManager fires `HomelabPodOOMKilled` for pod `velero-*` in namespace `velero`
- Pod restart count increments (typically after 2+ days uptime)
- OOM typically coincides with backup windows (02:00–08:00 UTC daily)

## Root Cause
Velero v1.17.1 with the kopia uploader and `defaultVolumesToFsBackup: true` gradually accumulates memory over multiple backup cycles. With 5 kopia repositories (apps, argocd, media, traefik, velero) and daily full filesystem backups across all non-system namespaces, memory consumption grows with backup data volume.

The OOM typically occurs several hours after the daily backup starts at 02:00 UTC, as Velero processes backup completion, maintenance job scheduling, and GC of expired backups concurrently.

**This is a recurring issue** — as backup data grows, so does Velero's peak memory footprint. The 1Gi limit set in Feb 2026 was exceeded within days on the same backup run pattern.

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
    memory: 512Mi
  limits:
    cpu: 500m
    memory: 2Gi  # Was 1Gi — increased 2026-02-24 (second OOMKill)
```

If OOMs recur after raising to 2Gi, consider:
1. Raising to 3Gi
2. Reducing backup scope (exclude more namespaces or large PVCs)
3. Checking Velero release notes for memory fixes in newer versions
4. Enabling `--backup-file-copy-options` to reduce parallelism

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
| 2026-02-24 | #236, #237 (2nd) | 1Gi | 2Gi | 1Gi insufficient — OOMKilled again same day on subsequent backup run |
