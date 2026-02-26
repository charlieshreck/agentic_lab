# kube-state-metrics CrashLoop (Monit Cluster)

## Symptom
`HomelabPodCrashLooping` alert fires for `kube-prometheus-stack-kube-state-metrics-*` in the monitoring namespace. Pod shows repeated restarts, exit code 2.

## Root Cause
The monit cluster runs on VMs hosted on Pihanga (10.10.0.20). PBS backups cause heavy I/O on the Pihanga host, which degrades the K8s API server's responsiveness. kube-state-metrics connects to the API server on startup — when the API is slow, it exits with code 2 and is restarted by Kubernetes, creating a crash loop.

Prior to Feb 2026: All 3 Proxmox hosts (Hikurangi, Ruapehu, Pihanga) ran PBS backups simultaneously at 02:00 UTC, creating a severe I/O storm.

After stagger fix (Feb 25 2026): Hikurangi 02:00, Ruapehu 02:20, Pihanga 02:45 — reduced but did not eliminate restarts.

## Known Pattern
- **Crash window**: 02:45–03:30 UTC (during/after Pihanga PBS backup)
- **Exit code**: 2 (app crash, NOT OOMKill which would be 137)
- **QoS before fix**: BestEffort (no resource requests set) — most vulnerable to eviction
- **QoS after fix**: Burstable (50m CPU / 64Mi RAM requests added Feb 26 2026)

## Verification — Is This Real or Expected?

1. Check current pod status:
   ```
   kubectl_get_pods(namespace="monitoring", cluster="monit")
   ```
   - If Running/Ready → self-healed, likely transient during backup window

2. Check if in backup window (02:45–03:30 UTC):
   ```
   Current time UTC?
   ```
   If YES → expected transient during Pihanga backup

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

1. Check logs: `kubectl_logs(pod_name=..., namespace="monitoring", cluster="monit", previous=True)`
2. Check node events: `kubectl_get_events(namespace="monitoring", cluster="monit")`
3. Check if API server is reachable from within the cluster
4. Check Pihanga host memory/CPU: `proxmox_get_vm_status`

### If crash loop is severe (> 10 restarts/hour)
1. Check if PBS backup is running on Pihanga (SSH to Pihanga, check processes)
2. If backup running and causing I/O storm: wait for backup to complete (usually < 30 min)
3. If budget allows, consider pushing Pihanga backup schedule to 04:00+ UTC

## Applied Fixes (Chronological)

| Date | Fix | Result |
|------|-----|--------|
| Feb 25 2026 | Staggered PBS backup schedules (Hikurangi 02:00, Ruapehu 02:20, Pihanga 02:45) | Reduced crash frequency, not eliminated |
| Feb 26 2026 | Added resource requests to kube-state-metrics (50m CPU / 64Mi RAM) — changes QoS from BestEffort to Burstable | Reduces eviction risk during I/O pressure |

## Potential Further Improvements

1. **Push Pihanga backup later**: Change from 02:45 to 04:00 UTC in `/etc/pve/jobs.cfg` on Pihanga
2. **Increase liveness probe tolerance**: Set `failureThreshold: 5` in helm values (default is 3 × 10s = 30s timeout)
3. **API server resource limits**: Ensure API server on monit cluster has adequate CPU during I/O spikes

## Related Incidents
- Incident #262: First identification of PBS I/O storm root cause
- Incidents #300, #302, #303: Post-stagger fix, still occurring during Pihanga window

## Related Runbooks
- `infrastructure/pbs-operations.md` — PBS backup management
- `infrastructure/proxmox-high-memory-pressure.md` — Ruapehu memory pressure
- `infrastructure/monitoring-vm-high-memory.md` — Monit cluster VM memory
