# DeploymentUnavailable

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | DeploymentUnavailable |
| **Severity** | Warning |
| **Source** | error-hunter sweep / PrometheusRule |
| **Clusters Affected** | All (prod, agentic, monit) |

## Description

Fires when a Kubernetes deployment has 0 available replicas while the desired count is >= 1. This means the application is completely down — no pods are serving traffic.

Common in the homelab for workloads with a single replica (no redundancy). A crash loop, image pull failure, or resource pressure can take the entire service offline.

## Quick Diagnosis

### 1. Check deployment and pod status

```
# Via MCP tools
mcp__infrastructure__kubectl_get_deployments(namespace="<ns>", cluster="<cluster>")
mcp__infrastructure__kubectl_get_pods(namespace="<ns>", cluster="<cluster>", label_selector="app=<name>")
```

### 2. Check pod events and logs

```bash
# Describe the deployment for events
mcp__infrastructure__kubectl_describe(resource_type="deployment", name="<name>", namespace="<ns>", cluster="<cluster>")

# Get pod logs
mcp__infrastructure__kubectl_logs(name="<pod-name>", namespace="<ns>", cluster="<cluster>", tail_lines=50)
```

## Common Causes

### 1. Crash Loop (Most Common)

**Symptoms:**
- Pod status shows `CrashLoopBackOff`
- High restart count (e.g., 20+)
- Pod briefly reaches Running then crashes

**Verification:**
```
mcp__infrastructure__kubectl_get_pods(namespace="<ns>", cluster="<cluster>", label_selector="app=<name>")
# Look for: restarts > 5, status = CrashLoopBackOff
```

**Resolution:**
- Check pod logs for the crash reason (OOM, unhandled exception, missing config)
- If OOM: increase memory limits in the deployment manifest
- If config issue: check ConfigMaps, Secrets, env vars
- Often self-heals after transient dependency issues (DB, Redis, NFS)

### 2. Image Pull Failure

**Symptoms:**
- Pod status shows `ImagePullBackOff` or `ErrImagePull`
- Events mention authentication failure or image not found

**Verification:**
```
mcp__infrastructure__kubectl_describe(resource_type="pod", name="<pod>", namespace="<ns>", cluster="<cluster>")
# Look for: "Failed to pull image" events
```

**Resolution:**
- Check `imagePullSecrets` in the deployment manifest
- Verify the image tag exists in the registry (e.g., `ghcr.io`)
- Check if `ghcr-credentials` secret is present and valid

### 3. Resource Pressure (Node)

**Symptoms:**
- Pod stuck in `Pending` state
- Events show `FailedScheduling` — insufficient CPU/memory

**Verification:**
```
mcp__infrastructure__kubectl_get_nodes(cluster="<cluster>")
mcp__infrastructure__kubectl_describe(resource_type="node", name="<node>", cluster="<cluster>")
```

**Resolution:**
- Check node resource usage
- Scale down other workloads or increase node resources
- See: `proxmox-high-memory-pressure.md` for VM-level fixes

### 4. Failed Mount (NFS/PVC)

**Symptoms:**
- Pod stuck in `ContainerCreating`
- Events show `FailedMount` with timeout

**Verification:**
```
mcp__infrastructure__kubectl_get_events(namespace="<ns>", cluster="<cluster>")
# Look for: FailedMount events
```

**Resolution:**
- Check NFS server availability (TrueNAS-HDD at 10.10.0.103 / 10.40.0.10)
- See: `nfs-mount-failures-accumulating.md`

## Resolution Steps

1. Identify the specific failure mode from pod status/events
2. Fix the underlying issue (see common causes above)
3. If the pod is crash-looping, it will auto-recover once the issue is fixed
4. For persistent issues, check the deployment manifest in git and fix via GitOps

## Prevention

1. **Resource limits**: Set appropriate CPU/memory requests and limits
2. **Liveness/readiness probes**: Ensure probes are configured and not too aggressive
3. **Image pull policy**: Use `imagePullPolicy: Always` with `imagePullSecrets`
4. **Monitoring**: `HomelabDeploymentUnavailable` PrometheusRule alerts on 0 available replicas

## Incident History

### 2026-02-23: kernow-hub Crash Loop Recovery

- **Impact**: kernow-hub deployment in agentic cluster had 0/1 available replicas
- **Root Cause**: Transient crash loop (27 restarts accumulated), self-healed
- **Resolution**: No intervention needed — pod recovered automatically
- **Duration**: Brief (detected and self-resolved within sweep interval)

## Related Runbooks

- [PBS Backup Stale](/home/agentic_lab/runbooks/alerts/pbs-backup-stale.md)
- [Proxmox High Memory Pressure](/home/agentic_lab/runbooks/infrastructure/proxmox-high-memory-pressure.md)
- [NFS Mount Failures](/home/agentic_lab/runbooks/alerts/nfs-mount-failures-accumulating.md)
