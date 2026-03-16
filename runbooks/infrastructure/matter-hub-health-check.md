# Matter Hub Health Check - Troubleshooting & Resolution

## Overview
Matter Hub is the Home Assistant Matter protocol bridge in the production Kubernetes cluster. It includes a periodic health check (CronJob) that runs every 10 minutes to verify both the Matter Hub HTTP server and Matter Server TCP port accessibility.

## Health Check Architecture

**CronJob Schedule**: `*/10 * * * *` (every 10 minutes)

**Health Check Script** (`/data/kubernetes/applications/apps/matter-hub/health-check.yaml`):
- Checks Matter Hub HTTP server responds on port 8482
- Checks Matter Server TCP port 5580 is reachable
- Includes retry logic: 3 attempts with 2-second delays
- Uses busybox:1.37 container with minimal resources (10m CPU request, 16Mi memory)

**Critical Environment Variable Fix**:
```yaml
# DO use MATTER_SERVER_SERVICE_PORT (port number only)
MATTER_SERVER_SERVICE_PORT: "5580"

# DO NOT use MATTER_SERVER_PORT (K8s injects as "tcp://IP:5580")
```

Kubernetes automatically injects `SERVICE_NAME_PORT` as `protocol://IP:port`, which breaks netcat. The health check script works around this by using `MATTER_SERVER_SERVICE_PORT` with a fallback to 5580.

## Common Issues & Resolution

### Issue: Health Check Job Fails

**Symptom**: KubeJobFailed alert for `apps/matter-hub-health-check-*`

**Root Causes** (in order of likelihood):
1. **Matter Server Pod Unavailable** - Service port check fails
   - Check pod status: `kubectl -n apps get pods -l app=matter-server`
   - Check service: `kubectl -n apps get svc matter-server`
   - Verify port 5580 is exposed

2. **Matter Hub Pod Restarting** - HTTP health check fails
   - Check pod logs: `kubectl -n apps logs -l app=matter-hub --tail=50`
   - Check pod restarts: `kubectl -n apps get pods -l app=matter-hub`
   - If restarting: check resource limits and node capacity

3. **Network Connectivity Issue** - Temporary cross-pod communication failure
   - This is typically transient and self-heals
   - Monitor multiple consecutive failures before escalating
   - Check cluster networking: `kubectl get nodes -o wide`

4. **DNS Resolution Failure** - Service names not resolving
   - All three services (matter-hub, matter-server) use cluster DNS
   - Test from busybox: `kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup matter-server.apps.svc.cluster.local`

### Transient Failures (Self-Healing)

**Observed Pattern**: Single or occasional health check job failures followed by consistent successes indicate transient issues:
- Pod startup timing mismatches
- Temporary network latency
- Service cache updates
- Node resource pressure

**Resolution**: Monitor for patterns. If failures are sporadic (< 1 per hour), no action needed. If failures cluster together (multiple consecutive failures), investigate root cause.

## Verification

**Check recent health check status**:
```bash
kubectl -n apps describe cronjob matter-hub-health-check
# Look for Last Schedule Time and events
```

**Manual health check**:
```bash
# Trigger a manual job run
kubectl create job --from=cronjob/matter-hub-health-check matter-hub-check-manual -n apps
kubectl logs -n apps job/matter-hub-check-manual
```

**Service connectivity test**:
```bash
# From any pod
kubectl exec -it <pod> -n apps -- sh
wget http://matter-hub.apps.svc.cluster.local:8482/
nc -z -w10 matter-server.apps.svc.cluster.local 5580
```

## Historical Incident: Job #498 (2026-03-16 16:55 UTC)

**Alert**: KubeJobFailed for `apps/matter-hub-health-check-29557270`

**Investigation**:
- Original job no longer in cluster (cleaned up by failedJobsHistoryLimit: 3)
- All subsequent jobs (29561580 → 29561630) completed successfully
- Matter server pod healthy with 0 restarts (3d uptime)
- Matter hub pod healthy (1 restart unrelated to health checks)
- No errors in pod logs

**Conclusion**: Transient network or timing issue. System self-healed. No manifest changes needed.

**Evidence**:
- Job 29561630 (scheduled 93s after original alert) succeeded
- All 6 subsequent jobs in last 51 minutes completed successfully
- CronJob showing normal event pattern (Create → Delete cycle)
- Last health check succeeded 2 minutes ago

## GitOps Maintenance

The health check manifests are ArgoCD-managed:
- **Application**: `matter-hub` (`kubernetes/argocd-apps/applications/matter-hub-app.yaml`)
- **Path**: `kubernetes/applications/apps/matter-hub/`
- **Manifests**:
  - `deployment.yaml` - Matter Hub app + PVC + Service
  - `health-check.yaml` - ConfigMap + CronJob

**Never manually kubectl apply**. All changes must:
1. Edit manifests in git
2. Commit to main branch
3. ArgoCD syncs automatically

## Related Documents
- `/home/prod_homelab/kubernetes/applications/apps/matter-hub/` - Source manifests
- Matter Server: High-performance Matter protocol server (separate deployment)
- Home Assistant: Primary home automation hub (different namespace, different cluster)
