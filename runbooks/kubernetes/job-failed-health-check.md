# Runbook: KubeJobFailed - Health Check Jobs

**Alert Name**: `KubeJobFailed`
**Typical Symptoms**: Job pods fail with "port not reachable" errors when performing health checks
**Severity**: warning (application impact depends on what the job monitors)
**Last Updated**: 2026-02-22

---

## Overview

The `KubeJobFailed` alert triggers when Kubernetes Jobs fail to complete successfully. This runbook specifically addresses recurring failures of the `matter-hub-health-check` CronJob, which validates that both Matter Hub HTTP and Matter Server TCP services are reachable.

## Root Causes

### 1. **Kubernetes Auto-Injected Environment Variables Conflict** (Most Common - Fixed 2026-02-22)
- **Symptom**: Health-check fails with "port X not reachable" where X is a URL like `tcp://IP:PORT`
- **Root Cause**: Kubernetes automatically injects `SERVICE_PORT=protocol://IP:port` for all services in a namespace
- **Example Issue**: Script uses `$MATTER_SERVER_PORT` which becomes `tcp://10.96.219.201:5580` instead of `5580`
- **Netcat expects**: Just the port number (e.g., `5580`), not a URL
- **Solution**: Use `${SERVICE_NAME}_SERVICE_PORT` instead of `${SERVICE_NAME}_PORT`
  ```bash
  # WRONG - Kubernetes sets this to "protocol://IP:port"
  nc -z -w10 "$HOST" "$MATTER_SERVER_PORT"  # MATTER_SERVER_PORT=tcp://10.96.219.201:5580

  # CORRECT - This is always just the port number
  nc -z -w10 "$HOST" "$MATTER_SERVER_SERVICE_PORT"  # MATTER_SERVER_SERVICE_PORT=5580
  ```

### 2. **Insufficient Timeout / No Retry Logic** (Secondary)
- **Symptom**: Health-check pods fail with "port not reachable" despite the service being healthy
- **Root Cause**: Network timing issues or transient DNS resolution failures
- **Solution**: Implement retry logic with exponential backoff and increased timeouts
- **Example**: 3 attempts with 10-second timeouts and 2-second delays between attempts

### 2. **ConfigMap Out of Sync with Git (GitOps Drift)**
- **Symptom**: Deployed ConfigMap has outdated health-check script without retry logic
- **Root Cause**: ArgoCD hasn't synced recent Git changes
- **Solution**: Delete the ConfigMap to trigger ArgoCD to recreate it from Git
  ```bash
  kubectl delete configmap <name> -n <namespace>
  ```

### 3. **Service Endpoints Not Ready**
- **Symptom**: `nc` (netcat) command times out when connecting to service IP
- **Root Cause**: Pods not passing readiness probes, or network policies blocking traffic
- **Verification**:
  ```bash
  kubectl get endpoints <service> -n <namespace>
  kubectl get networkpolicy -n <namespace>
  kubectl describe pod <pod> -n <namespace> | grep -A5 "Readiness:"
  ```

### 4. **DNS Resolution Failures**
- **Symptom**: Health-check pod cannot resolve service FQDN
- **Root Cause**: CoreDNS issues or cluster DNS misconfiguration
- **Verification**:
  ```bash
  kubectl exec -it <pod> -- nslookup <service-fqdn>
  kubectl get svc -n kube-system | grep dns
  ```

---

## Investigation Steps

### Step 1: Check Job Status
```bash
kubectl get jobs -n <namespace> -l <selector>
kubectl describe job <job-name> -n <namespace>
```

### Step 2: Review Logs
```bash
# Get logs from failed pod
kubectl logs -n <namespace> <pod-name>

# Look for specific errors:
# - "port tcp://IP:port not reachable" → Kubernetes env var conflict (see Root Cause #1)
# - "port 5580 not reachable" → timeout/retry issue (see Root Cause #2)
# - "HTTP error" → target service down
# - "cannot resolve" → DNS issue
```

### Step 2.5: Check for Kubernetes Env Var Issues (NEW - 2026-02-22)
If logs show error message with format like `port tcp://10.96.219.201:5580`:
```bash
# Run a pod in the namespace to see what Kubernetes injects
kubectl run -it --rm --image=busybox --restart=Never --namespace=<namespace> debug-env -- env | grep -i "<SERVICE_NAME>"

# Look for:
# <SERVICE>_PORT=tcp://IP:port  (WRONG for netcat/port numbers)
# <SERVICE>_SERVICE_PORT=port   (CORRECT - just the number)
```

### Step 3: Verify Target Service
```bash
# Check service exists and has endpoints
kubectl get svc <service> -n <namespace>
kubectl get endpoints <service> -n <namespace>

# Check target pod is healthy
kubectl get pods -n <namespace> -l <label>
kubectl describe pod <pod-name> -n <namespace>

# Verify port is listening
kubectl exec <pod> -- netstat -tln | grep <port>
```

### Step 4: Check for GitOps Drift
```bash
# If ConfigMap looks outdated, check Git vs deployed
# Look at job source file in Git repo
cat kubernetes/applications/<app>/health-check.yaml

# Compare with deployed version
kubectl get configmap <name> -n <namespace> -o yaml
```

---

## Resolution Steps

### For Kubernetes Auto-Injected Env Var Conflict (NEW - 2026-02-22)

If error message shows `port tcp://IP:port format`:

1. **Identify the problematic variable**
   ```bash
   # Script is using wrong variable name
   grep "\$MATTER_SERVER_PORT" /scripts/check.sh  # (or whatever the service is)
   ```

2. **Fix the script to use SERVICE_NAME_SERVICE_PORT**
   ```bash
   # Change from:
   nc -z -w10 "$MATTER_SERVER_HOST" "$MATTER_SERVER_PORT"

   # To:
   nc -z -w10 "$MATTER_SERVER_HOST" "$MATTER_SERVER_SERVICE_PORT"

   # Or use a fallback:
   PORT="${MATTER_SERVER_SERVICE_PORT:-5580}"
   nc -z -w10 "$MATTER_SERVER_HOST" "$PORT"
   ```

3. **Commit to git and force ConfigMap recreation**
   ```bash
   git add kubernetes/applications/.../health-check.yaml
   git commit -m "fix: use correct Kubernetes SERVICE_PORT env var"
   git push origin main

   # Force ArgoCD to sync by deleting the ConfigMap
   kubectl delete configmap <name> -n <namespace>
   ```

### For ConfigMap Out of Sync (Common)

1. **Delete the outdated ConfigMap**
   ```bash
   kubectl delete configmap <name> -n <namespace>
   ```
   ArgoCD will automatically recreate it within 3-5 minutes with the correct version.

2. **Verify the fix**
   ```bash
   kubectl get configmap <name> -n <namespace> -o yaml | grep -A 20 "check.sh:"
   ```

3. **Monitor next job execution**
   ```bash
   kubectl get jobs -n <namespace> -l <selector> --watch
   kubectl logs -f -n <namespace> <pod-name>
   ```

### For Insufficient Timeout (Edit Manifest)

If the Git version itself has weak timeouts, update the health-check script:

```yaml
# Increase timeout and add retry logic
for i in $(seq 1 3); do
  if nc -z -w10 "$HOST" "$PORT" 2>/dev/null; then
    echo "OK: Port reachable"
    break
  fi
  if [ $i -lt 3 ]; then
    echo "WARN: Failed (attempt $i/3), retrying in 2s..."
    sleep 2
  else
    echo "CRITICAL: Port not reachable after 3 attempts"
    exit 1
  fi
done
```

### For Service Not Ready

1. **Check pod health**
   ```bash
   kubectl get pods -n <namespace>
   kubectl logs -n <namespace> <pod-name>
   ```

2. **Check readiness probes**
   ```bash
   kubectl describe pod <pod> -n <namespace> | grep -A 10 "Readiness:"
   ```

3. **If pod is stuck CrashLooping, restart it**
   ```bash
   kubectl rollout restart deployment/<name> -n <namespace>
   ```

---

## Prevention

### 1. Ensure Robust Health Check Scripts
- ✅ Implement retry logic (3-5 attempts)
- ✅ Use longer timeouts (10-15 seconds per attempt)
- ✅ Add delays between retries (2-5 seconds)
- ✅ Log each attempt for debugging

### 2. Monitor Git Sync
- Use `argocd app status <app>` to verify sync status
- Set up alerts for ArgoCD sync failures
- Review audit logs for last-applied-configuration drift

### 3. Test Health Checks
- Manually trigger a one-off job during testing
- Verify logs show expected behavior
- Check that retries actually work

### 4. Configure Job Cleanup
```yaml
spec:
  successfulJobsHistoryLimit: 1  # Keep only latest success
  failedJobsHistoryLimit: 3      # Keep last 3 failures for debugging
```

---

## Testing the Fix

After applying the fix, verify with:

```bash
# Create a one-off job from the CronJob
kubectl create job --from=cronjob/matter-hub-health-check test-health-check -n apps

# Watch the job
kubectl get job test-health-check -n apps --watch

# Check logs
kubectl logs -n apps -l job-name=test-health-check -f
```

Expected output from a healthy health-check:
```
[INFO] Checking Matter Hub and Matter Server...
[OK] Matter Hub HTTP responding (200)
[OK] Matter Server port 5580 reachable
[OK] matter_hub_health_check: All checks passed
```

---

## Related Alerts

- **KubePodCrashLooping**: If target pods are crashing
- **KubeServiceNotHealthy**: If endpoints are missing
- **ArgocdSyncFailed**: If ConfigMap isn't syncing from Git

## References

- Kubernetes Jobs: https://kubernetes.io/docs/concepts/workloads/controllers/job/
- CronJobs: https://kubernetes.io/docs/concepts/workloads/controllers/cron-jobs/
- Health checks in scripts: Shell script robust error handling patterns
