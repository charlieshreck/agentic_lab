# Alert: HomelabPodCrashLooping

## Trigger Pattern
`increase(kube_pod_container_status_restarts_total[1h]) > 5 for 15m`

Any pod (excluding Talos control plane static pods) with more than 5 container restarts in the past hour.

## Quick Diagnosis

```bash
# Check which pods have high restart rates right now
kubectl --kubeconfig=/root/.kube/config get pods -A --sort-by='.status.containerStatuses[0].restartCount' 2>/dev/null | tail -20

# Check if pods are actually in CrashLoopBackOff (active crash) vs just high historical count
kubectl --kubeconfig=/root/.kube/config get pods -A | grep CrashLoop
```

## Step 1: Identify the Crashing Pod

The AlertManager alert description includes the pod name:
> "Container `<container>` in pod `<pod>` has restarted `<N>` times in the last hour."

Check the pod's logs and previous container logs:
```bash
kubectl --context=admin@<cluster> logs -n <namespace> <pod> --tail=50
kubectl --context=admin@<cluster> logs -n <namespace> <pod> --previous --tail=50
```

## Step 2: Classify the Crash Type

| Crash Pattern | Likely Cause | Action |
|---|---|---|
| `OOMKilled` in last terminated reason | Memory limit too low | Increase memory limit |
| `leaderelection lost` + API timeout to 127.0.0.1:7445 | API server I/O contention (PBS backup window) | Transient — see below |
| `leaderelection lost` + API timeout to 10.96.0.1 | Network or API server issue | Investigate API server health |
| Application-specific errors in logs | Code bug or config issue | Fix config or restart |
| `ImagePullBackOff` | Bad image tag | Fix image reference in manifest |
| `CrashLoopBackOff` with exit code 1 | Application startup failure | Check logs for startup error |

## Known Transient Pattern: PBS Backup Window (02:00–03:30 UTC)

### What Happens
PBS backup runs daily at 02:00 UTC from both Proxmox hosts (Ruapehu and Pihanga).
The monit cluster VM (`talos-monitor`) runs on Pihanga. During backup:
1. Heavy I/O on Pihanga storage causes etcd latency
2. `kube-scheduler-talos-monitor` and `kube-controller-manager-talos-monitor` fail to renew leader election leases (timeout to `127.0.0.1:7445`)
3. Both pods crash (exit code 1: "Leaderelection lost")
4. They restart and self-recover once backup I/O subsides (~03:05–03:15 UTC)

**This alert should NOT fire for these pods** — the rule now excludes `kube-scheduler-.*`, `kube-controller-manager-.*`, `kube-apiserver-.*`, `etcd-.*` pods.

If you see incidents from before 2026-02-26, they were caused by this pattern.

### Verification
```bash
# Check if kube-scheduler is now stable
kubectl --context=admin@monitoring-cluster -n kube-system get pod kube-scheduler-talos-monitor

# Check Pihanga for running vzdump (backup process)
sshpass -p 'H4ckwh1z' ssh root@10.10.0.20 "ps aux | grep vzdump | grep -v grep"
```

If vzdump is running AND the alert is for kube-scheduler/kube-controller-manager → **transient, self-resolving**.

## Step 3: Fix Actions by Crash Type

### OOM Kill
1. Find current memory limit in manifest
2. Increase by 50% (or to the next resource tier: 256Mi → 512Mi → 1Gi)
3. Edit manifest in appropriate repo, commit, push
4. ArgoCD will sync the change

### Application Startup Failure
1. Read the logs carefully — look for config errors, missing env vars, connection refused
2. Check InfisicalSecret CRD status for secrets issues
3. Check the referenced ConfigMap/Secret exists
4. Fix the root cause in the manifest, commit, push

### Grafana Sidecar (grafana-sc-dashboard / grafana-sc-datasources) Crashes
These crash when the Kubernetes API server is slow (same I/O contention pattern as kube-scheduler).
They self-recover. If they crash outside the backup window, investigate API server health:
```bash
kubectl --context=admin@monitoring-cluster -n monitoring logs \
  kube-prometheus-stack-grafana-<pod-id> -c grafana-sc-dashboard --previous --tail=30
```

### Mayastor LocalPV Provisioner Crashes
Uses deprecated v1 Endpoints for leader election. Expected to crash when API server is slow.
Upgrade mayastor when a version using Lease objects is available.
Current restart count (~26) is stable and not actively crash-looping.

## Step 4: Verify Recovery
After applying a fix:
```bash
# Check restart rate is no longer increasing
kubectl --context=admin@<cluster> get pod -n <namespace> <pod> -w
```

## Related Runbooks
- `infrastructure/proxmox-high-memory-pressure.md` — Pihanga I/O contention
- `infrastructure/monitoring-vm-high-memory.md` — talos-monitor memory pressure

## Alert Rule Location
`monit_homelab/kubernetes/platform/prometheus-rules/homelab-rules.yaml`

## Metadata
- **Domain**: alerts
- **Tags**: crash-loop, kube-scheduler, PBS-backup, Talos, leader-election
- **Decay Rate**: 0.1
- **Last Updated**: 2026-02-26
