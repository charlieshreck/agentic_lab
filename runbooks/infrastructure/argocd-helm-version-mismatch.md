# ArgoCD OutOfSync: Helm Chart Version Mismatch

**Incident #224** | Severity: Warning | Domain: ARC (Actions Runner Controller)

## Problem

ArgoCD Application shows **OutOfSync** status when pre-rendered Helm manifest versions don't match the controller/operator version:

```
Status: OutOfSync (Healthy)
Sync Status: Unknown changes detected
```

This typically happens when:
1. Controller/operator deployed with new version (e.g., arc-controller 0.14.0)
2. Dependent manifests still reference old chart version (e.g., arc-runner-set v0.13.1)
3. Manifests are pre-rendered from Helm (stored as `manifests.yaml`)

## Root Cause

Pre-rendered Helm manifests contain version metadata that must match the deployed chart version:
- `helm.sh/chart: gha-rs-0.13.1` → must be updated when chart version changes
- `app.kubernetes.io/version: "0.13.1"` → must be updated when chart version changes

When Update Patrol (or manual updates) change the controller version but skip the dependent manifests, ArgoCD detects the drift.

## Fix

Update all version references in the pre-rendered manifests:

```bash
# Example: Update arc-runner-set manifests from 0.13.1 to 0.14.0
cd /home/agentic_lab/kubernetes/platform/arc-runner-set/

# Find what version the manifests currently reference
grep "gha-rs-\|version:" manifests.yaml | head -4

# Update all version references (both old and new versions)
OLD_VERSION="0.13.1"
NEW_VERSION="0.14.0"
OLD_CHART_VERSION="gha-rs-${OLD_VERSION}"
NEW_CHART_VERSION="gha-rs-${NEW_VERSION}"

sed -i "s/${OLD_CHART_VERSION}/${NEW_CHART_VERSION}/g" manifests.yaml
sed -i "s/\"${OLD_VERSION}\"/\"${NEW_VERSION}\"/g" manifests.yaml

# Verify the changes
grep "gha-rs-\|version:" manifests.yaml | head -4
diff -u manifests.yaml.bak manifests.yaml | head -20
```

Then commit and push:

```bash
cd /home
git -C agentic_lab add kubernetes/platform/arc-runner-set/manifests.yaml
git -C agentic_lab commit -m "fix: update arc-runner-set manifests to v${NEW_VERSION}"
git -C agentic_lab push origin main
```

## Verification

After fixing the manifests:

1. **Wait for ArgoCD to detect the change** (~30 seconds):
   ```bash
   kubectl get applications.argoproj.io arc-runner-set -n argocd \
     -o jsonpath='{.status.sync.status}{"\n"}'
   ```

2. **Expected output**: `Synced` (not `OutOfSync`)

3. **If still OutOfSync after 30s**, trigger a hard refresh:
   ```bash
   export KUBECONFIG=/root/.kube/config
   kubectl config use-context admin@homelab-prod
   kubectl patch applications.argoproj.io arc-runner-set -n argocd \
     --type merge -p '{"metadata":{"annotations":{"argocd.argoproj.io/refresh":"hard"}}}'
   ```

## Prevention

**Update Patrol Enhancement Needed**: When Update Patrol updates controller versions, it should also regenerate dependent pre-rendered manifests to keep versions in sync.

Current behavior:
- ✅ Updates controller image tag (e.g., `gha-runner-scale-set-controller:0.13.1` → `0.14.0`)
- ❌ Does NOT update dependent manifest chart versions (arc-runner-set labels remain 0.13.1)

Suggested fix:
1. Add logic to detect controller version changes
2. Automatically regenerate or update version labels in dependent manifests
3. Include both updates in the same commit

## Related Applications

This issue can affect any pre-rendered Helm manifests paired with controllers:
- `arc-controller` (gha-runner-scale-set-controller) ↔ `arc-runner-set` (gha-runner-scale-set)
- Similar patterns in other infrastructure operators

## Alert Rules

**Current Alert**: ArgoCD OutOfSync (generic)

Could be enhanced to detect Helm version mismatches specifically:
```yaml
- alert: ArgoCDHelmVersionMismatch
  expr: argocd_app_info{name=~"arc-.*"} and sync_status != "Synced"
  for: 5m
```

## Incident Log

- **2026-03-20**: arc-controller updated to 0.14.0 (commit 0bd276d) - arc-runner-set NOT updated
- **2026-03-20**: Incident #224 detected - OutOfSync status
- **2026-03-20**: Fixed by updating arc-runner-set to 0.14.0 (commit 02c2e70)
- **Result**: Synced within 2 seconds

## See Also
- ArgoCD OutOfSync Runbook (general)
- Update Patrol Automation (`/home/scripts/update-patrol/`)
- ARC Controller GitHub API Runbook
