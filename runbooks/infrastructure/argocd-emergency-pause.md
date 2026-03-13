# ArgoCD Emergency Pause (Incident Mode)

**When to use**: During incidents where ArgoCD self-heal is reverting manual recovery changes (pod deletions, deployment edits, PVC recreations).

---

## Option 1: Pause Specific Apps (Preferred)

Disables automated sync for individual applications while keeping all other syncing active.

```bash
# Disable automated sync (self-heal + auto-sync)
kubectl patch application <app-name> -n argocd --type merge \
  -p '{"spec":{"syncPolicy":{"automated":null}}}'

# Verify
kubectl get application <app-name> -n argocd -o jsonpath='{.spec.syncPolicy}'; echo
```

To re-enable after incident:
```bash
kubectl patch application <app-name> -n argocd --type merge \
  -p '{"spec":{"syncPolicy":{"automated":{"prune":true,"selfHeal":true}}}}'
```

**Batch pause** (all apps in a namespace):
```bash
# Pause all media apps
for app in $(kubectl get applications -n argocd --no-headers | grep -E "sonarr|radarr|transmission|sabnzbd|tautulli|overseerr|cleanuparr|maintainerr|notifiarr|prowlarr" | awk '{print $1}'); do
  kubectl patch application $app -n argocd --type merge -p '{"spec":{"syncPolicy":{"automated":null}}}'
  echo "Paused: $app"
done
```

---

## Option 2: Scale Controller to 0 (Nuclear)

Stops ALL ArgoCD syncing across ALL three clusters (prod, agentic, monit). Use only when Option 1 is insufficient.

```bash
# Stop the controller
kubectl scale statefulset argocd-application-controller -n argocd --replicas=0

# Verify stopped
kubectl get statefulset argocd-application-controller -n argocd
```

**CRITICAL**: This stops syncing for 100+ applications across 3 clusters. Re-enable ASAP:
```bash
kubectl scale statefulset argocd-application-controller -n argocd --replicas=1
```

---

## Option 3: Annotation-Based Pause

Pause sync for an app without changing its syncPolicy (useful for Helm-managed apps where patching syncPolicy causes drift):

```bash
kubectl annotate application <app-name> -n argocd \
  argocd.argoproj.io/refresh=normal --overwrite
```

This doesn't actually pause — for true pause, use Option 1.

---

## When ArgoCD Self-Heal Fights You

Common scenarios during incidents:

| What you did | ArgoCD response | Fix |
|-------------|-----------------|-----|
| Deleted a pod | Deployment recreates it (K8s, not ArgoCD) | This is normal K8s behavior — ArgoCD isn't involved |
| Deleted a deployment | ArgoCD self-heal recreates it | Pause the app (Option 1) |
| Edited a deployment spec | ArgoCD self-heal reverts it | Pause the app (Option 1) |
| Created a temporary pod | ArgoCD prunes it (not in git) | Add `argocd.argoproj.io/compare-options: IgnoreExtraneous` annotation |
| Deleted a PVC | ArgoCD self-heal recreates it (if in git) | Pause the app, or delete from git first |

---

## Recovery Checklist (After Incident)

1. Re-enable paused apps:
   ```bash
   # List all apps without automated sync
   kubectl get applications -n argocd -o json | \
     python3 -c "import sys,json; apps=json.load(sys.stdin)['items']; [print(a['metadata']['name']) for a in apps if not a.get('spec',{}).get('syncPolicy',{}).get('automated')]"
   ```

2. If controller was scaled to 0, scale back to 1

3. Verify all apps synced and healthy:
   ```bash
   kubectl get applications -n argocd --no-headers | grep -v "Synced.*Healthy"
   ```

4. Check for any apps stuck in "OutOfSync" or "Degraded" state
