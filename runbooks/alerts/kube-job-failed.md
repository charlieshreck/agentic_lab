# KubeJobFailed

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | KubeJobFailed |
| **Severity** | Warning |
| **Threshold** | Job has failed |
| **Source** | kube-state-metrics |
| **Clusters Affected** | All (prod, agentic, monit) |

## Description

This alert fires when a Kubernetes Job has failed to complete successfully. Jobs are typically used for:
- CronJob-triggered tasks (daily validations, backups, syncs)
- One-off batch processing
- Database migrations
- Manual triggered tasks

## Quick Diagnosis

### 1. Identify the failed job

```bash
# From alert labels
# Example: job_name=claude-validator-daily-29474280, namespace=ai-platform

kubectl get job <job-name> -n <namespace>
kubectl describe job <job-name> -n <namespace>
```

### 2. Check job pods

```bash
kubectl get pods -n <namespace> -l job-name=<job-name>
kubectl logs -n <namespace> -l job-name=<job-name>
```

### 3. Check parent CronJob (if applicable)

```bash
# Job names from CronJobs follow pattern: <cronjob-name>-<timestamp>
kubectl get cronjob -n <namespace>
```

## Common Causes

### 1. Application/Script Error

**Symptoms:**
- Pod completed but job shows failed
- Non-zero exit code

**Verification:**
```bash
kubectl logs -n <namespace> -l job-name=<job-name>
```

**Resolution:**
- Fix the script/application bug
- Check input data validity
- Verify external dependencies are accessible

### 2. Container Configuration Error

**Symptoms:**
- Pod never started
- CreateContainerConfigError

**Verification:**
```bash
kubectl describe pods -n <namespace> -l job-name=<job-name>
```

**Resolution:**
- See `KubeContainerWaiting` runbook
- Fix missing secrets/configmaps
- Verify image exists

### 3. Resource Limits Exceeded

**Symptoms:**
- OOMKilled
- Pod evicted

**Verification:**
```bash
kubectl describe pods -n <namespace> -l job-name=<job-name> | grep -A 5 "State:"
# Look for: OOMKilled, Evicted
```

**Resolution:**
- Increase memory/CPU limits in job spec
- Optimize application memory usage

### 4. Timeout Exceeded

**Symptoms:**
- Job ran but didn't complete in time
- `activeDeadlineSeconds` exceeded

**Verification:**
```bash
kubectl get job <job-name> -n <namespace> -o yaml | grep activeDeadlineSeconds
```

**Resolution:**
- Increase `activeDeadlineSeconds` in job spec
- Optimize job execution time

### 5. Backoff Limit Reached

**Symptoms:**
- Multiple failed pod attempts
- `backoffLimit` exceeded

**Verification:**
```bash
kubectl get job <job-name> -n <namespace> -o yaml | grep backoffLimit
kubectl get pods -n <namespace> -l job-name=<job-name>
```

**Resolution:**
- Fix underlying pod failure
- Increase `backoffLimit` if appropriate

## Resolution Steps

### Step 1: Get job status

```bash
kubectl describe job <job-name> -n <namespace>
```

### Step 2: Check pod logs

```bash
kubectl logs -n <namespace> -l job-name=<job-name>

# If multiple pods, check all
kubectl logs -n <namespace> -l job-name=<job-name> --all-containers
```

### Step 3: Fix the issue

Based on the cause identified above.

### Step 4: Clean up failed job

```bash
# Delete failed job to clear alert
kubectl delete job <job-name> -n <namespace>
```

### Step 5: Re-run if needed

```bash
# For CronJobs, manually trigger
kubectl create job --from=cronjob/<cronjob-name> <new-job-name> -n <namespace>

# Example
kubectl create job --from=cronjob/claude-validator-daily claude-validator-manual -n ai-platform
```

### Step 6: Verify next run succeeds

```bash
# Wait for next CronJob trigger or watch manual job
kubectl get jobs -n <namespace> -w
```

## Common Jobs in Kernow Homelab

### claude-validator-daily
- **Schedule:** Daily at 06:00 UTC
- **Purpose:** Validates AI agent outputs from previous day
- **Common Issues:**
  - ConfigMap syntax errors
  - Missing secrets
  - Claude API rate limits

### configarr (media namespace)
- **Schedule:** Daily
- **Purpose:** Syncs TRaSH Guides custom formats to Sonarr/Radarr
- **Common Issues:**
  - TRaSH API unreachable
  - Sonarr/Radarr API errors

### runbook-indexer
- **Purpose:** Indexes runbooks to Qdrant
- **Common Issues:**
  - Qdrant unavailable
  - Malformed runbook files

### huntarr-start / huntarr-stop (media namespace)
- **Schedule:** Start at 00:00 UTC, Stop at 08:00 UTC
- **Purpose:** Scale up/down Huntarr deployment for missing media discovery
- **Common Issues:**
  - **activeDeadlineSeconds timeout (120s) too short** ⚠️
    - kubectl scale command needs time for image pull + pod startup
    - Solution: Increase `activeDeadlineSeconds` to 300+ seconds
    - Config: `/home/prod_homelab/kubernetes/applications/media/huntarr/schedule.yaml`

## Cleaning Up Failed Jobs

Failed jobs don't auto-delete. To prevent alert spam:

### Manual cleanup
```bash
# Delete specific failed job
kubectl delete job <job-name> -n <namespace>

# Delete all failed jobs in namespace
kubectl delete jobs -n <namespace> --field-selector status.successful=0
```

### Automatic cleanup (configure in CronJob)
```yaml
apiVersion: batch/v1
kind: CronJob
spec:
  failedJobsHistoryLimit: 1
  successfulJobsHistoryLimit: 3
```

## Escalation

If jobs repeatedly fail:

1. Check if external dependencies are healthy
2. Review recent changes to job configuration
3. Check cluster resource availability
4. Review application logs for patterns

## Prevention

1. **Test jobs manually:** Before relying on CronJob schedule
2. **Set appropriate limits:** `backoffLimit`, `activeDeadlineSeconds`
3. **Configure history limits:** Keep only recent job history
4. **Monitor job duration:** Alert if jobs take longer than expected

## Related Alerts

- `KubeCronJobRunning` - CronJob taking too long
- `KubeJobNotCompleted` - Job not completing in time
- `KubeContainerWaiting` - Job pod can't start

## Historical Incidents

### January 2026 - claude-validator-daily Failed
- **Job:** claude-validator-daily-29474280
- **Cause:** YAML syntax error in configmap broke the validator
- **Resolution:** Fixed configmap YAML, deleted failed job
- **Lesson:** Validate YAML changes before committing
