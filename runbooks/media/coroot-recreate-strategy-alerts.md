# Coroot Critical Alerts for Media Deployments (Recreate Strategy)

## Pattern
Coroot fires a critical availability incident for any media namespace deployment during rollout. The alert self-heals within ~30 seconds but the estate system keeps re-dispatching it to patrol.

## Affected Deployments
All 12 media deployments use `strategy: Recreate`:
- cleanuparr, configarr, huntarr, maintainerr, notifiarr, overseerr
- prowlarr, radarr, recomendarr, sabnzbd, sonarr, tautulli, transmission

## Root Cause
1. All media deployments use `ReadWriteOnce` (RWO) PVCs backed by Mayastor
2. RWO PVCs require `Recreate` strategy (two pods can't mount simultaneously)
3. During rollout: old pod deleted -> ~25s gap -> new pod starts
4. Coroot detects the availability gap and fires a critical incident
5. Webhook sends to error-hunter -> estate incident -> patrol dispatch
6. Pod recovers, but Coroot alert retention window causes re-dispatch

## Verification (Patrol Quick-Check)
Before auto-resolving, verify ALL of these:
1. Pod is Running and Ready: `kubectl_get_pods(cluster="prod", namespace="media")`
2. 0 or low restarts (consistent with rollout, not crash loop)
3. Logs show clean startup with no errors
4. ArgoCD shows Synced/Healthy
5. No other firing Coroot alerts

If ALL pass: auto-resolve as "transient Recreate-strategy rollout alert"
If ANY fail: investigate further — this is a real issue

## Resolution
```bash
curl -s -X POST http://10.10.0.22:3456/webhook/screen-resolve \
  -H 'Content-Type: application/json' \
  -d '{"type":"incident","id":ID,"summary":"Transient Coroot alert from Recreate-strategy rollout. Pod healthy, 0 restarts, logs clean, ArgoCD synced. Known pattern — RWO PVC requires Recreate strategy."}'
```

## Systemic Fix (TODO)
The recurring alert pattern needs one of these permanent fixes:

### Option 1: Coroot SLO Configuration (Recommended)
Configure per-application availability SLOs in Coroot UI to tolerate brief rollout downtime:
- Navigate to Coroot -> each media app -> SLO settings
- Set availability SLO to 99% (allows ~15 min/day downtime, more than enough for rollouts)
- This prevents Coroot from creating critical incidents for brief gaps

### Option 2: Error-Hunter Filter
Add a filter in the error-hunter ingest pipeline to suppress brief Coroot incidents:
- If source=coroot AND namespace=media AND duration < 2 minutes -> auto-resolve
- Requires code change in error-hunter

### Option 3: Coroot Webhook Template Filter
Modify the Coroot CR notification template to exclude media namespace:
- File: `monit_homelab/kubernetes/platform/coroot-config/coroot-cr.yaml`
- Limitation: Coroot CR webhook config doesn't support per-namespace filtering

## History
- 2026-02-21: Incident #109 first seen (cleanuparr@media)
- 2026-02-24: Incident #109 re-dispatched 3+ times, also prowlarr@media (#225)
- Pattern confirmed across multiple media deployments
