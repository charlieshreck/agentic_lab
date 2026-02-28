# kube-state-metrics CrashLoop

## Symptom
`HomelabPodCrashLooping` alert fires for `kube-prometheus-stack-kube-state-metrics-*` in the monitoring namespace. Pod shows repeated restarts, exit code 2.

## Affected Clusters

| Cluster | Managed By | Fix Status |
|---------|-----------|------------|
| monit | ArgoCD via `kube-prometheus-stack-app.yaml` in monit_homelab | Fixed Feb 26 2026 (commit f4a448c) |
| prod | ArgoCD via `kube-state-metrics-resources-app.yaml` in prod_homelab | Fixed Feb 26 2026 |

**Note**: The prod cluster kube-prometheus-stack is an orphaned deployment (ArgoCD app was moved to monit). A separate `kube-state-metrics-resources` ArgoCD app in `prod_homelab/kubernetes/argocd-apps/platform/` manages only the resource requests via SSA.

## Root Cause
PBS backups cause heavy I/O on the host running the cluster's VMs, which degrades the K8s API server's responsiveness. kube-state-metrics connects to the API server on startup — when the API is slow, it exits with code 2 and is restarted by Kubernetes, creating a crash loop.

| Cluster | Hosted On | PBS Backup Window |
|---------|-----------|------------------|
| monit | Pihanga (10.10.0.20) | 02:45 UTC |
| prod | Ruapehu (10.10.0.10) | 02:20 UTC |

Prior to Feb 2026: All 3 Proxmox hosts ran PBS backups simultaneously at 02:00 UTC, creating a severe I/O storm.

After stagger fix (Feb 25 2026): Hikurangi 02:00, Ruapehu 02:20, Pihanga 02:45 — reduced but did not eliminate restarts.

## Known Pattern
- **Crash window**: 02:20–03:30 UTC (during/after Ruapehu or Pihanga PBS backup)
- **Exit code**: 2 (app crash, NOT OOMKill which would be 137)
- **QoS before fix**: BestEffort (no resource requests set) — most vulnerable to eviction
- **QoS after fix**: Burstable (50m CPU / 64Mi RAM requests added Feb 26 2026)

## Verification — Is This Real or Expected?

1. Check current pod status:
   ```
   kubectl_get_pods(namespace="monitoring", cluster="monit")
   kubectl_get_pods(namespace="monitoring", cluster="prod")
   ```
   - If Running/Ready → self-healed, likely transient during backup window

2. Check if in backup window (02:20–03:30 UTC):
   If YES → expected transient during PBS backup

3. Check restart rate metric:
   ```
   query_metrics_instant("increase(kube_pod_container_status_restarts_total{pod=~'kube-prometheus-stack-kube-state-metrics.*'}[2h])")
   ```
   - 0 restarts in 2h → issue has cleared, safe to resolve

4. Check AlertManager — is it still firing?
   ```
   list_alerts()
   ```

## Resolution

### If pod is stable and alert cleared
Auto-resolve as known-pattern transient during PBS backup window.

### If pod is stuck in CrashLoop outside backup window
This is a real issue requiring investigation:

1. Check logs: `kubectl_logs(pod_name=..., namespace="monitoring", cluster="monit"|"prod", previous=True)`
2. Check node events: `kubectl_get_events(namespace="monitoring", cluster=...)`
3. Check if API server is reachable from within the cluster
4. Check Pihanga/Ruapehu host memory/CPU: `proxmox_get_vm_status`

### If crash loop is severe (> 10 restarts/hour)
1. Check if PBS backup is running (SSH to Pihanga or Ruapehu, check processes)
2. If backup running and causing I/O storm: wait for backup to complete (usually < 30 min)
3. Consider pushing backup schedules further apart

## Applied Fixes (Chronological)

| Date | Cluster | Fix | Result |
|------|---------|-----|--------|
| Feb 25 2026 | All | Staggered PBS backup schedules (Hikurangi 02:00, Ruapehu 02:20, Pihanga 02:45) | Reduced crash frequency, not eliminated |
| Feb 26 2026 | monit | Added resource requests to kube-state-metrics (50m/64Mi) in `kube-prometheus-stack-app.yaml` — QoS BestEffort → Burstable | Reduces eviction risk during I/O pressure |
| Feb 26 2026 | prod | Created `kube-state-metrics-resources` ArgoCD app in prod_homelab with SSA resource patch — QoS BestEffort → Burstable | Same fix for orphaned prod deployment |
| Feb 27 2026 | monit | Added AlertManager `time_interval` route to suppress TargetDown for kube-state-metrics during 01:00–05:00 UTC backup window (`kube-prometheus-stack-app.yaml`, commit 3c8191a) | Eliminates false patrol alerts during backup window; alert still fires outside window |

## Patrol Decision Guide (for Auto-Resolution)

The TargetDown alert for kube-state-metrics during 01:00–05:00 UTC is now suppressed in AlertManager.
If you still receive an incident (#349 pattern), check:

1. **Was the alert raised between 01:00–05:00 UTC?** If yes → likely backup window bleed, auto-resolve as transient.
2. **Is the pod Running/Ready now?** If yes → self-healed, auto-resolve.
3. **Has it been down > 1 hour continuously?** If yes → this is a REAL outage, escalate.

## Potential Further Improvements

1. **Push Pihanga backup later**: Change from 02:45 to 04:00 UTC in `/etc/pve/jobs.cfg` on Pihanga
2. **Increase liveness probe tolerance**: Set `failureThreshold: 5` in helm values (default is 3 × 10s = 30s timeout)
3. **Properly re-adopt prod kube-prometheus-stack into GitOps**: The prod deployment is orphaned; consider a full ArgoCD Application with the complete helm values
4. **Remove deprecated `endpoints` resource**: ksm enumerates `endpoints` (deprecated since k8s 1.33) — removing it reduces API pressure at startup
5. **Window boundary leak**: AlertManager re-evaluates suppressed alerts when `active_time_intervals` expires. If the RESOLVED notification fires at 05:00 UTC exactly, it escapes the null route and reaches alerting-pipeline. Fix: extend the window to 06:00 UTC, or suppress TargetDown kube-state-metrics globally (only alerting on extended outages > 30m via a separate alert)

## Related Incidents
- Incident #262: First identification of PBS I/O storm root cause (prod cluster)
- Incidents #300, #302, #303: Post-stagger fix, monit cluster during Pihanga window
- Incident #923: Prod cluster BestEffort QoS fix applied
- Incident #114: monit TargetDown, 2026-02-21 to 2026-02-24 (previously resolved manually)
- Incident #349 (Finding #936): Feb 27 2026 — triggered AlertManager time_interval fix
- Incident #348 (Finding #952): Feb 28 2026 — First incident after time_interval fix; alert leaked at 05:00 UTC window boundary (AlertManager re-evaluates suppressed alerts when window ends; pod was already healthy for 2h+ but resolved notification escaped to pipeline)

## Related Runbooks
- `infrastructure/pbs-operations.md` — PBS backup management
- `infrastructure/proxmox-high-memory-pressure.md` — Ruapehu memory pressure
- `infrastructure/monitoring-vm-high-memory.md` — Monit cluster VM memory
