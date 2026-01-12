# Runbook: Configarr (TRaSH Guides Sync)

## Overview

Configarr synchronizes TRaSH Guides custom formats and quality profiles to Sonarr and Radarr. Runs as a CronJob daily at midnight.

## Quick Reference

| Property | Value |
|----------|-------|
| Namespace | `media` |
| Type | CronJob |
| Schedule | `0 0 * * *` (midnight daily) |
| ArgoCD App | `configarr` |
| Config | `configarr-config` ConfigMap |

## Common Operations

### Check Status
```bash
export KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig

# CronJob status
kubectl get cronjob configarr -n media

# Recent job history
kubectl get jobs -n media -l app.kubernetes.io/name=configarr

# ArgoCD app health
kubectl get application configarr -n argocd
```

### Trigger Manual Sync
```bash
kubectl create job --from=cronjob/configarr configarr-manual-$(date +%s) -n media
```

### View Sync Logs
```bash
# Latest job
kubectl logs -n media -l job-name --tail=200

# Specific job
kubectl logs -n media job/configarr-manual-1234567890
```

### Force ArgoCD Sync
```bash
kubectl patch application configarr -n argocd --type merge \
  -p '{"operation": {"initiatedBy": {"username": "manual"}, "sync": {"prune": true}}}'
```

## Troubleshooting

### Job Failed - Config Not Found

**Symptom**:
```
Error: Config file in location "/app/config/config.yml" does not exists.
```

**Diagnosis**:
```bash
kubectl get cm configarr-config -n media -o yaml
kubectl describe cronjob configarr -n media | grep -A5 "Volume Mounts"
```

**Fix**: Ensure volumeMount path is `/app/config/config.yml` (not `/app/config.yml`)

---

### Job Failed - Permission Denied

**Symptom**:
```
Error: EACCES: permission denied, mkdir '/app/repos/...'
```

**Diagnosis**:
```bash
kubectl describe cronjob configarr -n media | grep -A10 "Volumes"
```

**Fix**: Ensure emptyDir volume is mounted at `/app/repos`:
```yaml
volumeMounts:
- name: repos
  mountPath: /app/repos
volumes:
- name: repos
  emptyDir: {}
```

---

### Job Failed - API Connection Error

**Symptom**:
```
Error: connect ECONNREFUSED ...
```

**Diagnosis**:
```bash
# Check Sonarr/Radarr pods
kubectl get pods -n media | grep -E "sonarr|radarr"

# Check services
kubectl get svc -n media | grep -E "sonarr|radarr"

# Test connectivity from temp pod
kubectl run -n media curl-test --rm -it --restart=Never --image=curlimages/curl \
  -- curl -s http://sonarr.media.svc.cluster.local:8989/api/v3/system/status
```

**Fix**:
- Ensure Sonarr/Radarr are running
- Check API key in secrets matches app configuration

---

### Job Failed - Invalid API Key

**Symptom**:
```
401 Unauthorized
```

**Diagnosis**:
```bash
# Check secret exists
kubectl get secret sonarr-credentials -n media
kubectl get secret radarr-credentials -n media

# Verify key (base64 decode)
kubectl get secret sonarr-credentials -n media -o jsonpath='{.data.API_KEY}' | base64 -d
```

**Fix**:
- Verify API key in Infisical matches Sonarr/Radarr Settings → General → API Key
- Check InfisicalSecret is syncing: `kubectl get infisicalsecrets -n media`

---

### Profiles Not Appearing in Sonarr/Radarr

**Symptom**: Job completes successfully but profiles don't show in UI

**Diagnosis**:
```bash
# Check job output for "Created QualityProfile"
kubectl logs -n media job/<job-name> | grep -i "QualityProfile"
```

**Possible causes**:
1. Profile already exists with same name (Configarr skips)
2. API permissions insufficient
3. Browser cache - try hard refresh

**Fix**: Clear browser cache or check Sonarr/Radarr logs

## Adding New Profiles

### 1. Find Template Name

Browse [Recyclarr Config Templates](https://github.com/recyclarr/config-templates/tree/master/sonarr) or [TRaSH Guides](https://trash-guides.info/).

### 2. Update ConfigMap

Edit `/home/prod_homelab/kubernetes/applications/media/configarr/configmap.yaml`:

```yaml
include:
  # Existing profiles...
  - template: sonarr-v4-quality-profile-anime
  - template: sonarr-v4-custom-formats-anime
```

### 3. Commit and Sync

```bash
cd /home/prod_homelab
git add kubernetes/applications/media/configarr/configmap.yaml
git commit -m "feat(configarr): Add anime profile"
git push
```

### 4. Trigger Sync

```bash
kubectl create job --from=cronjob/configarr configarr-anime -n media
kubectl logs -n media job/configarr-anime -f
```

## Adding Custom Formats

### Define in Config

```yaml
custom_formats:
  - trash_ids:
      - 85c61753df5da1fb2aab6f2a47426b09  # BR-DISK (avoid)
    assign_scores_to:
      - name: WEB-1080p
        score: -10000
```

### Find TRaSH IDs

1. Go to [TRaSH Guides JSON](https://github.com/TRaSH-Guides/Guides/tree/master/docs/json)
2. Find the custom format JSON file
3. Copy the `trash_id` value

## Changing Schedule

Edit `cronjob.yaml`:

```yaml
spec:
  schedule: "0 */6 * * *"  # Every 6 hours
```

Common schedules:
- `0 0 * * *` - Daily at midnight
- `0 */6 * * *` - Every 6 hours
- `0 0 * * 0` - Weekly on Sunday
- `0 0 1 * *` - Monthly on 1st

## Disaster Recovery

### Complete Reinstall

```bash
# Delete existing
kubectl delete -n argocd application configarr

# Reapply
kubectl apply -f /home/prod_homelab/kubernetes/argocd-apps/applications/configarr-app.yaml

# Wait for sync
kubectl get application configarr -n argocd -w

# Trigger manual run
kubectl create job --from=cronjob/configarr configarr-recovery -n media
```

### Reset Custom Formats in Sonarr/Radarr

If CFs are corrupted, delete them in the UI first, then re-run Configarr:
1. Sonarr/Radarr → Settings → Custom Formats → Delete All
2. Trigger manual Configarr job

## Related Resources

- **Config Location**: `/home/prod_homelab/kubernetes/applications/media/configarr/`
- **ArgoCD App**: `/home/prod_homelab/kubernetes/argocd-apps/applications/configarr-app.yaml`
- **Lessons Learned**: `/home/agentic_lab/runbooks/lessons-learned/configarr-deployment-2026-01.md`
- **Configarr Docs**: https://configarr.de
- **TRaSH Guides**: https://trash-guides.info/
