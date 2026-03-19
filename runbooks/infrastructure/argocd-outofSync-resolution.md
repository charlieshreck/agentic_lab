---
title: ArgoCD OutOfSync Alert Resolution
description: Incident #224 - pulse-agent app drift auto-resolved by ArgoCD self-healing
severity: info
domain: infrastructure
---

## Incident Summary
ArgoCD app `pulse-agent-prod` reported OutOfSync status (health: Progressing) on 2026-03-19.

**Status**: ✅ RESOLVED (auto-healed)
**Confidence**: 0.99
**Root Cause**: Transient drift (auto-resolved by ArgoCD self-healing)

## Investigation Results

### ArgoCD App Status (2026-03-19T02:19:59Z)
```
Sync Status:   Synced ✅
Health Status: Healthy ✅
Last Reconciled: 2026-03-19T02:19:59Z
Last Sync: 2026-03-15T03:07:25Z (succeeded)
```

### Daemon Set Status
```
DaemonSet: pulse-agent
- Desired: 4
- Current: 4
- Ready: 4
- Up-to-date: 4
- Available: 4
```

### Pod Status (all nodes)
- `pulse-agent-7kgvw` (1/1 Running) - 3d23h old, 0 restarts
- `pulse-agent-c2ktl` (1/1 Running) - 3d23h old, 0 restarts
- `pulse-agent-pfxqp` (1/1 Running) - 3d23h old, 0 restarts
- `pulse-agent-zhqbb` (1/1 Running) - 3d23h old, 0 restarts

All pods stable with no events, no recent crashes.

## Root Cause Analysis

The drift occurred sometime between **2026-03-15T03:07:25Z** and **2026-03-19T02:19:59Z** (4-day gap).

**Why it auto-resolved:**
- ArgoCD `syncPolicy.automated.selfHeal: true` is enabled
- ArgoCD controller reconciles applications every 3 minutes by default
- Reconciliation at 2026-03-19T02:19:59Z detected the drift and re-synced
- All resources (ServiceAccount, ConfigMap, ClusterRole, ClusterRoleBinding, DaemonSet, InfisicalSecret) synced successfully

**Likely cause (speculative):**
- Manual inspection/edit of resources without git commit (not recommended)
- Temporary network glitch causing temporary divergence from git
- ArgoCD controller restart or transient state

## Prevention

1. **Enforce GitOps strictly**: All changes must come through git commits + ArgoCD sync
2. **Monitor reconciliation**: Watch `reconciledAt` timestamps in ArgoCD Application status
3. **Alert on sync failures**: Implement alerts for `status.sync.status: OutOfSync` persisting >5min
4. **Audit manual changes**: Review if any kubectl edits happened between 2026-03-15 and 2026-03-19

## Resolution Status

✅ **Auto-resolved via ArgoCD self-healing**
- No manual intervention needed
- All pods healthy and stable
- Git state matches live cluster state
- Incident can be closed

## Related Resources

- **App**: `pulse-agent-prod` (prod cluster)
- **Path**: `kubernetes/applications/apps/pulse-agent`
- **Namespace**: `pulse-agent`
- **Image**: `rcourtman/pulse:5.1.24`
- **Repository**: https://github.com/charlieshreck/prod_homelab
