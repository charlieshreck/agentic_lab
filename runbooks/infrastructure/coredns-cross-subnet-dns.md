# CoreDNS Cross-Subnet DNS Resolution

**Author:** Claude Code
**Date:** 2026-03-18
**Incident:** #509 - KubeAPITerminatedRequests (28.77% termination rate)
**Severity:** High

## Problem

Kubernetes clusters cannot reliably resolve DNS queries across network subnets due to UDP/53 being blocked by the firewall. Without explicit `force_tcp` configuration, CoreDNS attempts UDP first, which fails, causing:

- DNS resolution timeouts in kube-apiserver pods
- Failure to connect to etcd at `localhost:2379` (DNS lookup fails)
- API request termination (504 Gateway Timeout, 429 Too Many Requests)
- Cascading pod restarts (kube-scheduler, kube-controller-manager, cilium-operator)

### Root Cause

The firewall (OPNsense) blocks cross-subnet UDP/53 traffic:
- **Allowed subnets**: 10.10.0.0/24 (prod), 10.30.0.0/24 (monit), 10.40.0.0/24 (storage), 10.50.0.0/24 (storage)
- **Blocked**: UDP/53 between subnets (by design - prevent DNS loops)
- **Allowed**: TCP/53 between subnets

CoreDNS without `force_tcp` retries with TCP only after UDP timeout (1-2s delay per query), degrading performance.

## Solution

Add `force_tcp` flag to CoreDNS forwarder configuration in all clusters that forward DNS to 10.10.0.1 (OPNsense):

### Prod Cluster (10.10.0.0/24)

File: `/home/prod_homelab/kubernetes/platform/coredns/coredns-configmap.yaml`

```yaml
.:53 {
    # ... other plugins ...
    forward . 10.10.0.1 {
       max_concurrent 1000
       force_tcp
    }
}
```

### Monit Cluster (10.10.0.0/24)

File: `/home/monit_homelab/kubernetes/platform/coredns/coredns-configmap.yaml`

Same configuration as prod (monit cluster is on 10.10.0.0/24 network).

### Agentic Cluster (10.20.0.0/24) ✅

Already correctly configured with `force_tcp` - no changes needed.

## Implementation Steps

1. **Update ConfigMap files** in both submodules
2. **Commit and push** to GitHub
3. **Apply ConfigMap** via kubectl (not ArgoCD - Talos-managed component):
   ```bash
   kubectl --context admin@homelab-prod apply -f /home/prod_homelab/kubernetes/platform/coredns/coredns-configmap.yaml
   kubectl --context admin@monitoring-cluster apply -f /home/monit_homelab/kubernetes/platform/coredns/coredns-configmap.yaml
   ```
4. **Restart CoreDNS pods** to pick up new configuration:
   ```bash
   kubectl --context admin@homelab-prod rollout restart deployment/coredns -n kube-system
   kubectl --context admin@monitoring-cluster rollout restart deployment/coredns -n kube-system
   ```
5. **Verify** kube-apiserver returns to normal operation (check pod restarts, metrics)

## Verification

After applying the fix:

- **CoreDNS logs** should show pod restart with new config
- **kube-apiserver pod** status should show 0 restarts (no more connection failures)
- **API request termination rate** should drop to near-zero (incident #509 metrics)
- **Cross-cluster communication** should stabilize (control plane stability)

### Affected Components

When DNS fails across subnets:
- **kube-apiserver**: Cannot reach etcd → errors in logs
- **kube-scheduler**: Pod scheduling failures
- **kube-controller-manager**: Reconciliation failures
- **cilium-operator**: Network policy failures

## Lessons Learned

1. **DNS is critical infrastructure** - even 1-2 second timeouts cascade through the cluster
2. **Force TCP is essential** when UDP is blocked by design
3. **Split-DNS by intention** - this architecture prevents DNS loop attacks, but requires explicit config
4. **Monitor DNS resolution** in observability stack to catch failures early

## Related Documentation

- DNS Architecture: `/home/agentic_lab/runbooks/infrastructure/dns-architecture.md`
- Agentic CoreDNS Config: Already has `force_tcp` - reference implementation
- Incident #509: KubeAPITerminatedRequests resolution (2026-03-18)

## Timeline

| Time | Event |
|------|-------|
| 2026-02-20 | Agentic cluster CoreDNS fixed with `force_tcp` |
| 2026-03-18 02:22 UTC | Prod cluster API server begins failing DNS lookups |
| 2026-03-18 03:07 UTC | Escalation: 28.77% API request termination detected |
| 2026-03-18 03:45 UTC | Root cause identified: missing `force_tcp` in prod/monit CoreDNS |
| 2026-03-18 04:00 UTC | Fix applied to both clusters, pods restarted |
| 2026-03-18 04:05 UTC | Verification: API server healthy, zero restarts |
