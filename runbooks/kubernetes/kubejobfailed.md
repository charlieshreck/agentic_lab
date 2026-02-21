# KubeJobFailed Alert Runbook

## Alert Description
Fires when a Kubernetes Job fails to complete successfully. This alert indicates that a Job resource has exceeded its backoff limit or hit other failure conditions.

## Common Causes

1. **Image Issues**
   - Container image cannot be pulled or doesn't exist
   - Image contains incompatible tools/binaries

2. **Timeout Issues**
   - `activeDeadlineSeconds` too short for the actual work
   - Pod initialization taking longer than expected
   - Network connectivity issues

3. **Permission Issues**
   - Service account lacks RBAC permissions
   - Resource doesn't exist or is in wrong namespace

4. **Resource Constraints**
   - Pod OOMKilled due to insufficient memory
   - Node CPU throttling
   - Storage issues (PVC not bound, full disk, etc.)

5. **Command Failures**
   - Command exits with non-zero status
   - Missing required environment variables or configuration

## Investigation Steps

### 1. Check Job Status
```bash
kubectl describe job <job-name> -n <namespace>
kubectl get job <job-name> -n <namespace> -o yaml
```

Look for:
- Failure reason and message in status
- Pod count (failed/succeeded)
- Backoff limit exceeded

### 2. Check Pod Logs
```bash
# Find the failed pod
kubectl get pods -n <namespace> -l job-name=<job-name>

# Get logs (may be empty if pod was cleaned up)
kubectl logs -n <namespace> <pod-name> --tail=100
kubectl logs -n <namespace> <pod-name> --previous
```

### 3. Check Events
```bash
kubectl get events -n <namespace> --sort-by='.lastTimestamp' | grep <job-name>
```

### 4. Verify Configuration
- Check service account has proper RBAC roles
- Verify image exists and is accessible
- Check activeDeadlineSeconds is sufficient

## Huntarr Cronjob Specific Fix

The huntarr scheduler jobs (huntarr-start, huntarr-stop) failed due to:
- Using `registry.k8s.io/kubectl:v1.31` image which had compatibility issues
- Short `activeDeadlineSeconds` (120s) causing timeouts
- Low `backoffLimit` (1) meaning jobs would fail permanently on first error

### Resolution
1. Changed kubectl image to `bitnami/kubectl:latest`
2. Increased `activeDeadlineSeconds` to 300s
3. Increased `backoffLimit` to 3
4. Added shell wrapper with error handling and logging
5. Committed fix to `prod_homelab/kubernetes/applications/media/huntarr/schedule.yaml`
6. Triggered ArgoCD sync to apply changes
7. Cleaned up old failed jobs

### Prevention
- Always use proven/stable container images (bitnami for kubectl)
- Set realistic timeouts for the actual work being performed
- Allow reasonable retry attempts (backoffLimit >= 2)
- Add logging/error handling to job commands

## Long-Term Monitoring

1. Monitor job failure patterns in Prometheus
   - Query: `increase(kube_job_status_failed_total[1h])`
2. Alert on repeated failures (same job failing multiple times)
3. Review and update cronjob configurations quarterly
