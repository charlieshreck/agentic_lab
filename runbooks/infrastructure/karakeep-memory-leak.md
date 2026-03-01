# Karakeep Memory Leak Prevention

**Status**: Mitigated (ongoing upstream issue)
**Severity**: Warning
**Trigger**: HomelabPodOOMKilled alert for karakeep container

## Problem

Karakeep exhibits steady memory growth (baseline ~35–40 MB/hour, spikes during active crawling up to ~140 MB/hour), causing OOMKilled errors after 12–24 hours of uptime.

### Root Cause

Karakeep has application-level memory growth that continues regardless of available memory. Known contributing factors:

1. **Crawler worker memory**: Browser context cleanup issues (partially fixed in v0.31.0 via PR #2503)
2. **Worker process accumulation**: Multiple concurrent workers without proper resource cleanup
3. **Search indexing**: In-memory index growth without bounded cache management
4. **Application-level leak**: Unbounded growth in Node.js heap
5. Upstream tracking issue: https://github.com/karakeep-app/karakeep/issues/2344

## Current Mitigations

Both mitigations are active and committed in git:

### 1. Node.js Heap Cap (`NODE_OPTIONS`)

**File**: `/home/prod_homelab/kubernetes/applications/apps/karakeep/deployment.yaml`

```yaml
env:
- name: NODE_OPTIONS
  value: "--max-old-space-size=1024"
```

Caps V8 heap at 1024 MB (~50% of container limit), forcing more aggressive GC before the container limit is hit.

### 2. Scheduled Restart CronJob

**File**: `/home/prod_homelab/kubernetes/applications/apps/karakeep/restart-cronjob.yaml`

```yaml
schedule: "0 3,15 * * *"  # 3am and 3pm UTC (every 12h)
```

Restarts the pod every 12 hours at 03:00 and 15:00 UTC. With a baseline growth rate of ~37 MB/hour and starting memory of ~350 MB, the pod stays well under the 2048 MB container limit even at 3× baseline activity.

**Remove this CronJob once the upstream leak is fixed.**

## Current Deployment Specs

| Metric | Value |
|--------|-------|
| Version | 0.31.0 |
| Image | ghcr.io/karakeep-app/karakeep:0.31.0 |
| CPU request | 100m |
| CPU limit | 500m |
| Memory request | 768Mi |
| Memory limit | 2048Mi |
| NODE_OPTIONS | --max-old-space-size=1024 |
| Storage | 5Gi PVC (mayastor-3-replica) |
| Restart schedule | 0 3,15 * * * (every 12h) |

## Memory Growth Profile (Observed)

| Phase | Rate |
|-------|------|
| Cold start (first 30 min) | ~76 MB/hour (startup warming) |
| Steady state (baseline) | ~35–40 MB/hour |
| Active crawling/tagging | Up to ~140 MB/hour |
| Time to OOM at baseline (from 350 MB) | ~45 hours (12h restart keeps max at ~790 MB) |
| Time to OOM at 3× rate | ~12 hours (12h restart keeps max at ~1680 MB) |

## Verification

After a restart, confirm the pod is healthy:

```bash
kubectl get pods -l app=karakeep -n apps --context admin@homelab-prod
# Expect: Running, 0 restarts

kubectl top pod -l app=karakeep -n apps --context admin@homelab-prod
# Expect: memory usage starting fresh (250–400 MB after warmup)
```

Monitor CronJob history:

```bash
kubectl get cronjob karakeep-restart -n apps --context admin@homelab-prod
kubectl get jobs -n apps --context admin@homelab-prod | grep karakeep
```

## Escalation Options (If OOM Persists Despite Mitigations)

### Option 1: Reduce Worker Concurrency
```yaml
env:
- name: SEARCH_NUM_WORKERS
  value: "1"
- name: ASSET_PREPROCESSING_NUM_WORKERS
  value: "1"
```

### Option 2: Disable Non-Essential Workers
```yaml
env:
- name: WORKERS_DISABLED_WORKERS
  value: "video,assetPreprocessing"
```

### Option 3: Increase Restart Frequency
Change schedule to `"0 */8 * * *"` (every 8 hours) for high-activity environments.

### Option 4: Increase Container Memory Limit
If the growth rate accelerates significantly:
```yaml
resources:
  limits:
    memory: 3072Mi
```
Then adjust: `NODE_OPTIONS: "--max-old-space-size=2048"`

## Incident History

### Incident #389 / Finding #965 (2026-03-01)
- **Alert**: HomelabPodOOMKilled (karakeep)
- **Root cause**: Daily 03:00 restart was insufficient — pod grew past 2048 MB limit before next scheduled restart during high-activity period
- **Fix applied**: Changed CronJob schedule from `0 3 * * *` (daily) to `0 3,15 * * *` (every 12h)
- **Current pod**: karakeep-7d84f87967-nsmg5, started 2026-03-01T03:00:15Z, healthy

### Incident #360 (2026-02-27)
- **Alert**: HomelabPodOOMKilled (karakeep)
- **Pod killed**: karakeep-f8995dc75-qncr6 at ~605 MB (with old 1536 Mi limit)
- **Fix applied**: Added NODE_OPTIONS --max-old-space-size=1024, increased limit to 2048 Mi, added daily 03:00 restart CronJob

## References

- Karakeep GitHub: https://github.com/karakeep-app/karakeep
- Upstream memory issue: https://github.com/karakeep-app/karakeep/issues/2344
- Browser context fix: https://github.com/karakeep-app/karakeep/pull/2503 (v0.31.0)
