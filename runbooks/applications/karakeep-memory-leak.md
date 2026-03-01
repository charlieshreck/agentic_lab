# Karakeep Memory Leak Runbook

## Overview

Karakeep (bookmark manager) has a known steady memory leak that causes RAM usage to grow ~34 MB/hour until the container is OOM killed. This is a confirmed upstream bug.

- **Upstream issue**: https://github.com/karakeep-app/karakeep/issues/2344
- **Status**: Open, labeled `pri/high` — no fix in v0.31.0
- **Pattern**: Linear growth from cold-start (~450MB), hits 2Gi limit in ~47 hours

## Symptoms

- Finding: `HomelabPodOOMKilled` for `karakeep` in `apps` namespace (prod cluster)
- Memory metric `container_memory_working_set_bytes{pod=~"karakeep.*"}` shows steady linear growth
- Pod restarts resolve the issue temporarily

## Mitigation (in place)

A daily CronJob restarts the deployment every day at 03:00 UTC, preventing the OOM kill:

```
prod_homelab/kubernetes/applications/apps/karakeep/restart-cronjob.yaml
```

This CronJob:
- Runs at 03:00 UTC daily
- Uses a scoped ServiceAccount with only `get`/`patch` on deployments in `apps` namespace
- Causes ~30 seconds of downtime during the restart (Recreate strategy)

## When an OOM Kill Alert Fires

1. **Verify**: Check current pod memory: `container_memory_working_set_bytes{namespace="apps", container="karakeep"}`
2. **If growing linearly**: Expected pattern — verify the restart CronJob is running correctly
3. **If CronJob succeeded but OOM still happened**: Memory may be growing faster than ~34 MB/hr; check for unusual usage (bulk imports, AI tagging jobs)
4. **Manual restart**: `kubectl rollout restart deployment/karakeep -n apps`

## Checking CronJob Health

```bash
kubectl get cronjob karakeep-restart -n apps
kubectl get jobs -n apps -l app=karakeep-restart --sort-by=.status.startTime
```

## Resolution

Remove `restart-cronjob.yaml` and its reference in `kustomization.yaml` once the upstream memory leak is fixed in a new karakeep release. Check https://github.com/karakeep-app/karakeep/issues/2344 for status.

## Memory Leak Rate (observed 2026-03-01)

| Metric | Value |
|--------|-------|
| Growth rate | ~34 MB/hour |
| Cold-start baseline | ~450 MB |
| OOM kill threshold | 2048 Mi |
| Time to OOM (from cold start) | ~47 hours |
| Daily restart window | 03:00 UTC |
