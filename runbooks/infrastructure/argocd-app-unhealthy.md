# ArgoCDAppUnhealthy Runbook

**Alert**: `ArgoCDAppUnhealthy`
**Severity**: warning
**Source**: AlertManager → kube-prometheus-stack

## Description

Fires when an ArgoCD application has `health_status != Healthy` for more than 15 minutes.

## Investigation Steps

### 1. Identify the affected app
Check alert labels for `name` (app name) and `health_status` (Degraded/Missing/Unknown).

### 2. Check current ArgoCD status
All apps should be visible via MCP:
```
mcp__infrastructure__argocd_get_applications
```
If the app shows Healthy now → it self-healed. Check metrics history for root cause.

### 3. Check pod/job status in the app's namespace
```
mcp__infrastructure__kubectl_get_pods (cluster=prod, namespace=<dest_namespace>)
mcp__infrastructure__kubectl_get_jobs (cluster=prod, namespace=<dest_namespace>)
```

Look for pods in:
- `OOMKilled` / `Error` → resource limit issue
- `CrashLoopBackOff` → application error
- `Pending` → scheduling/resource issue
- `Succeeded` with no failed jobs → likely self-healed

### 4. Read pod logs
```
mcp__infrastructure__kubectl_logs (pod_name=<failed_pod>, previous=True)
```

### 5. Describe the ArgoCD Application resource
```
mcp__infrastructure__kubectl_describe (resource_type=application, name=<app>, namespace=argocd, cluster=prod)
```
Check `Health.Status`, `Operation State`, and `History` fields.

## Common Patterns

### CronJob OOM (e.g., Renovate)
**Symptom**: Job pod in OOMKilled state, app Degraded until old pod GC'd
**Check**: `kubectl_logs (previous=True)` shows `JavaScript heap out of memory` or container killed signal
**Fix**: Increase `resources.limits.memory` and `--max-old-space-size` env var
**Recovery**: ArgoCD returns to Healthy after OOMKilled pod is garbage collected

#### Renovate specific (prod cluster, renovate namespace)
- **Current stable config**: 4Gi memory limit, 3072MB Node.js heap (`--max-old-space-size=3072`)
- **Dep count**: ~317 in agentic_lab, ~110 in monit_homelab (Jan 2026)
- **Manifest**: `prod_homelab/kubernetes/applications/platform/renovate/cronjob.yaml`
- **OOM threshold**: < 3Gi is insufficient for current dep count

### Completed Jobs Causing Degraded
**Symptom**: All pods in `Succeeded` state but app shows Degraded
**Check**: Is this a known ArgoCD false positive? Check if any job *failed* first
**Fix**: If genuine false positive, add `ttlSecondsAfterFinished: 300` to job template

### Missing Resources (health_status=Missing)
**Symptom**: App sync_status=OutOfSync, a resource was deleted outside ArgoCD
**Check**: ArgoCD app events, compare live vs git
**Fix**: ArgoCD auto-sync with self-heal should recreate it. If not, check `prune` settings.

### Progressing (slow rollout)
**Symptom**: health_status=Progressing for extended period
**Check**: Deployment rollout status, pod scheduling, image pull
**Fix**: Check resource limits, node capacity, image availability

## Fix Protocol

1. **Identify root cause** from pod logs
2. **Edit the manifest** in the appropriate repo
3. **Commit and push** (never `kubectl apply`)
4. **Wait for ArgoCD sync** (auto-sync should pick it up within 3 minutes)
5. **Verify** app returns to Healthy in ArgoCD

```bash
# Example: fix renovate memory
# Edit: /home/prod_homelab/kubernetes/applications/platform/renovate/cronjob.yaml
git -C /home/prod_homelab add kubernetes/applications/platform/renovate/cronjob.yaml
git -C /home/prod_homelab commit -m "fix(renovate): increase memory limit to <X>Gi"
git -C /home/prod_homelab push origin main
```

## History

| Date | App | Root Cause | Fix |
|------|-----|-----------|-----|
| 2026-02-25 | renovate | OOM crash (1Gi → too small for 317 deps) | Increased to 4Gi / 3072MB heap |
