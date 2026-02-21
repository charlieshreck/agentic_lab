# Alert: KubeJobFailed

**Severity**: Warning

## Description

A Kubernetes Job has failed to complete. This alert indicates that a Job resource's Pod(s) exited with a non-zero status and exceeded the `backoffLimit` threshold.

## Common Causes

### 1. Image Pull Failures
**Symptom**: Pod shows `ImagePullBackOff` status
```
Failed to pull image "docker.io/bitnami/kubectl:1.31": not found
```

**Root Cause**: The image referenced in the Job template doesn't exist or is inaccessible
- Non-existent image tag (e.g., `bitnami/kubectl:1.31` doesn't exist on Docker Hub)
- Registry authentication failure
- Image deleted after Job was created

**Fix**:
1. Identify the failed Job:
   ```bash
   kubectl get job -n <namespace> -o wide
   ```

2. Check the pod logs for image pull error:
   ```bash
   kubectl describe pod -n <namespace> <pod-name>
   ```

3. Verify the correct image in the Git manifest:
   ```bash
   # For CronJob-generated jobs, check the CronJob template
   kubectl get cronjob -n <namespace> <cronjob-name> -o yaml | grep image
   ```

4. If image is wrong, update the manifest and let ArgoCD sync:
   ```bash
   # Force ArgoCD sync (if using GitOps)
   argocd app sync <app-name>

   # Or manually delete the CronJob to force recreation
   kubectl delete cronjob -n <namespace> <cronjob-name>
   ```

5. Clean up old failed jobs:
   ```bash
   kubectl delete job -n <namespace> --field-selector status.successful!=1
   ```

### 2. Velero Restore Drift
**Symptom**: After a Velero restore, CronJobs have outdated configurations
- Image references to old/non-existent versions
- Different backoffLimit or activeDeadlineSeconds than Git
- Service account or RBAC issues

**Fix**:
1. Check if resource was recently restored:
   ```bash
   kubectl get job -n media -o jsonpath='{.items[*].metadata.labels.velero\.io}' | grep -i restore
   ```

2. Verify the GitOps state matches the cluster:
   ```bash
   kubectl diff -f /path/to/manifests
   ```

3. Force ArgoCD to re-sync the application:
   ```bash
   argocd app sync <app-name> --force
   ```

### 3. RBAC or Permissions Issues
**Symptom**: Pod fails quickly, logs mention "permission denied" or "forbidden"

**Fix**:
1. Check the ServiceAccount exists:
   ```bash
   kubectl get sa -n <namespace>
   ```

2. Verify Role/RoleBinding permissions:
   ```bash
   kubectl get role,rolebinding -n <namespace>
   kubectl describe role <role-name> -n <namespace>
   ```

3. Test RBAC permissions:
   ```bash
   kubectl auth can-i --list --as=system:serviceaccount:<namespace>:<sa-name>
   ```

## Incident #121 - huntarr-stop-29524800

**Root Cause**: Image `bitnami/kubectl:1.31` doesn't exist on Docker Hub. The CronJob was configured from a Velero restore with an old image reference.

**Resolution**:
1. Verified Git manifest uses correct image: `registry.k8s.io/kubectl:v1.31` ✅
2. Forced ArgoCD sync of huntarr application ✅
3. ArgoCD re-deployed CronJob with correct image from Git ✅

**Prevention**:
- Always validate Velero-restored resources match GitOps source
- Monitor ImagePullBackOff errors in alerting
- Use image digest tags or pinned versions to prevent surprise breakage

## Verification

After fixing, verify the Job completes successfully:

```bash
# Watch job completion
kubectl get jobs -n <namespace> -w

# Check job status
kubectl get job -n <namespace> <job-name> -o wide

# Verify the next scheduled run succeeds
# (For CronJobs, wait for next schedule time)
```

## References

- [Kubernetes Job Troubleshooting](https://kubernetes.io/docs/concepts/workloads/controllers/job/#troubleshooting)
- [Velero Restore Documentation](https://velero.io/docs/v1.6/restore-reference/)
- [ArgoCD Application Sync](https://argoproj.github.io/argo-cd/user-guide/application-details/)
