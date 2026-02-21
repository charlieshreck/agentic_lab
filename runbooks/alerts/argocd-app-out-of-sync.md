# ArgoCDAppOutOfSync

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | ArgoCDAppOutOfSync |
| **Severity** | Warning |
| **Threshold** | App not Synced for 15 minutes |
| **Source** | ArgoCD metrics / error-hunter / alerting-pipeline |
| **Clusters Affected** | All (prod ArgoCD manages prod, agentic, monit) |

## Description

This alert fires when an ArgoCD application has been in a non-Synced state (typically OutOfSync) for more than 15 minutes. OutOfSync means the live cluster state differs from the desired state defined in Git.

ArgoCD runs on the **prod cluster only** and manages all three clusters (prod, agentic, monit). All applications are defined in Git repositories and synced via ArgoCD.

## Quick Diagnosis

### 1. Check current sync status

```
# Via MCP tool (preferred)
mcp__infrastructure__argocd_get_applications()

# Look for apps with sync_status != "Synced"
```

### 2. Check specific app details

```bash
# Via ArgoCD CLI (if available)
argocd app get <app-name> --server argocd.kernow.io

# Via kubectl on prod cluster
kubectl get application <app-name> -n argocd -o yaml
```

### 3. Check ArgoCD UI

Navigate to `https://argocd.kernow.io` and inspect the application for sync errors.

## Common Causes

### 1. Manual Changes on Cluster (Drift)

**Symptoms:**
- App shows OutOfSync but no recent Git commits
- Diff shows fields that were manually changed

**Verification:**
```
# Check app diff in ArgoCD UI or CLI
argocd app diff <app-name>
```

**Resolution:**
- Sync the app to restore Git state: `argocd app sync <app-name>`
- Or revert the manual change and commit to Git
- Avoid manual `kubectl apply/patch/edit` — use GitOps

### 2. Git Repository Changes Not Auto-Synced

**Symptoms:**
- Recent commits in the Git repo
- App configured with manual sync policy

**Verification:**
```
# Check sync policy
kubectl get application <app-name> -n argocd -o jsonpath='{.spec.syncPolicy}'
```

**Resolution:**
- Manually trigger sync: `argocd app sync <app-name>`
- Or enable auto-sync in the Application spec:
```yaml
spec:
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

### 3. App-of-Apps Drift

**Symptoms:**
- `app-of-apps` or `agentic-applications` or `monitoring-platform` is OutOfSync
- Child Application resources don't match what's in Git

**Verification:**
```
# Check the parent app-of-apps
mcp__infrastructure__argocd_get_applications()
# Look for app-of-apps, agentic-applications, monitoring-platform
```

**Resolution:**
- Sync the parent app: `argocd app sync app-of-apps`
- Check if new Application manifests were added to `kubernetes/argocd-apps/`
- Verify the bootstrap app-of-apps manifest exists:
  - Prod: `prod_homelab/kubernetes/bootstrap/app-of-apps.yaml`
  - Agentic: via `agentic-applications` app
  - Monit: via `monitoring-platform` app

### 4. Helm Values Changed

**Symptoms:**
- Helm-based apps show OutOfSync
- Values in Git differ from what's deployed

**Verification:**
```bash
# Check helm release values
kubectl get application <app-name> -n argocd -o yaml | grep -A 20 helm
```

**Resolution:**
- Sync the app to apply new Helm values
- Check for Helm chart version bumps via Renovate

### 5. Target Cluster Unreachable

**Symptoms:**
- Multiple apps targeting the same cluster are OutOfSync
- Sync attempts fail with connection errors

**Verification:**
```
# Check cluster connectivity from prod ArgoCD
# Agentic: 10.20.0.40:6443
# Monit: 10.10.0.30:6443
```

**Resolution:**
- Verify target cluster is running (check Proxmox VM status)
- Check network connectivity between clusters
- Verify ArgoCD cluster secrets haven't expired

## Resolution Steps

### Step 1: Identify the out-of-sync app

```
mcp__infrastructure__argocd_get_applications()
```

### Step 2: Check the app diff

Review what's different between Git and the live cluster state.

### Step 3: Sync the app

```
mcp__infrastructure__argocd_sync_application(name="<app-name>")
```

### Step 4: Verify sync succeeded

```
mcp__infrastructure__argocd_get_applications()
# Confirm app shows sync_status: "Synced", health: "Healthy"
```

### Step 5: Investigate root cause

If the app keeps going OutOfSync, identify what's causing drift:
- Manual kubectl changes
- External controllers modifying resources
- Missing pruning policy

## Prevention

1. **Never use manual kubectl apply/patch** — all changes via Git commits
2. **Enable auto-sync with self-heal** on all applications
3. **Use pruning** to remove resources deleted from Git
4. **Monitor app-of-apps** — if the parent drifts, child apps may not update
5. **Keep bootstrap manifests in Git** — `app-of-apps.yaml` must exist

## Related Alerts

- `ArgoCDAppUnhealthy` — App health is Degraded/Missing/Unknown
- `KubeDeploymentRolloutStuck` — Deployment not progressing (may cause Unhealthy)

## Detection Methods

| Method | Status |
|--------|--------|
| PrometheusRule (argocd_app_info metric) | Active — scrapes via API server proxy from monit Prometheus |
| error-hunter sweep | Active — polls ArgoCD API periodically |
| alerting-pipeline | Active — polls infrastructure MCP tools |

ArgoCD metrics are scraped from the prod cluster via the Kubernetes API server proxy pattern. The `argocd-metrics` service (port 8082) exposes `argocd_app_info` which powers both the `ArgoCDAppOutOfSync` and `ArgoCDAppUnhealthy` PrometheusRules. Scrape config is in the kube-prometheus-stack Helm values (`monit_homelab/kubernetes/argocd-apps/platform/kube-prometheus-stack-app.yaml`).
