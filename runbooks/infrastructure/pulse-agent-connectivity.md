# Pulse-Agent Service Connectivity Issues

**Category**: Observability / Monitoring
**Severity**: Warning
**Pattern**: Transient pod-to-service connectivity failure
**Last Updated**: 2026-03-01

## Summary

Pulse-agent DaemonSet (running on all nodes in monitoring cluster) failed to establish connection to pulse service. Symptoms include:
- pulse-agent unable to reach `http://pulse.monitoring.svc.cluster.local:7655`
- Error: `"operation not permitted"` when attempting `/api/agents/host/lookup`
- Monitoring cluster shows all services as "unknown" health (secondary effect)
- Alert: generic "check" from pulse source

This is typically a **transient pod lifecycle issue** where the agent pod starts before the service is fully ready for connections, or DNS resolution is briefly unavailable cross-subnet (agentic cluster case).

## Recognition

Generic "check" alert from pulse monitoring:
- Message: `"operation not permitted"` or similar connectivity error
- Component: pulse-agent (monitoring cluster, monitoring namespace)
- Related logs: `kubectl -n monitoring logs daemonset/pulse-agent`
- Secondary effect: Coroot reports all ~287 services as "unknown" health

Example incident: #215 (2026-03-01 13:38–13:40, 2-minute window)

## Investigation Protocol

1. **Check pulse-agent logs**
   ```bash
   kubectl -n monitoring logs daemonset/pulse-agent --tail=100
   ```
   Look for:
   - `operation not permitted` errors
   - `context deadline exceeded` when querying Kubernetes API
   - `Failed to dial` or `connection refused`

2. **Verify pulse service is running**
   ```bash
   kubectl get svc -n monitoring pulse
   kubectl get pod -n monitoring -l app=pulse
   ```
   Service should be `ClusterIP 10.101.112.103:7655`, pod should be Running/Ready.

3. **Check pulse-agent pod status**
   ```bash
   kubectl get pod -n monitoring -l app=pulse-agent --wide
   ```
   All nodes should have one Running pod. Check for restart loops.

4. **Test service connectivity from pod**
   ```bash
   kubectl exec -n monitoring <pulse-agent-pod> -- curl -v http://pulse.monitoring.svc.cluster.local:7655/api/agents/host/lookup
   ```
   Expected: 404 (fresh agent not yet registered) or 200 (registered agent)
   If connection fails: network/DNS issue

5. **Check Cilium network policies**
   ```bash
   kubectl get networkpolicy -n monitoring
   ```
   Verify no policies are blocking monitoring namespace traffic to pulse service.

## Root Causes

### Primary: Pod Lifecycle Race Condition
- pulse-agent pod starts and attempts to connect before pulse service DNS is ready
- Cross-subnet DNS resolution (agentic → monitoring) may have latency
- Solution: Force pod restart to trigger reconnection with fresh DNS cache

### Secondary: Coredns Resolver Issue
- Kubernetes DNS cache misconfigured (CoreDNS upstream broken)
- Affects cross-cluster service discovery
- Solution: Restart CoreDNS (applies to entire cluster, use as last resort)

### Tertiary: Cilium Network Policy
- Explicit network policy blocking monitoring.monitoring → monitoring.monitoring
- Less common; check if policies were recently added
- Solution: Verify/update network policies, restart pulse-agent

## Resolution

### Quick Fix (Recommended)
Restart pulse deployment and pulse-agent pod:
```bash
# Restart pulse service (forces pod recreation)
kubectl rollout restart deployment/pulse -n monitoring

# Delete pulse-agent pod on each node (DaemonSet will recreate)
kubectl delete pod -n monitoring -l app=pulse-agent

# Wait 30–60 seconds for pods to restart and reconnect
kubectl get pod -n monitoring -l app=pulse-agent --watch
```

### Verification
1. **Check pulse-agent logs for successful connection**
   ```bash
   kubectl -n monitoring logs daemonset/pulse-agent --tail=20 | grep -i "registered\|lookup\|connected"
   ```
   Expected: Agent successfully registers with pulse service.

2. **Verify Coroot shows services as known**
   - Wait 1–2 minutes for Coroot cache to update
   - Check Coroot web UI: services should no longer show "unknown" health
   - Or query: `curl http://10.10.0.22:3456/api/estate/health` (should show real status)

3. **Monitor alert silence**
   - Generic "check" alert from pulse should clear within 2–5 minutes
   - If alert persists, check for secondary issues (see Root Causes)

### If Issue Persists

1. **Restart CoreDNS** (cluster-wide DNS impact)
   ```bash
   kubectl rollout restart deployment/coredns -n kube-system
   ```
   Wait 30 seconds for new pods to be ready.

2. **Check Cilium CNI**
   ```bash
   kubectl get daemonset -n kube-system cilium
   ```
   Should be 1/1 Ready. If not, investigate separately.

3. **Escalate to infrastructure team**
   - If above steps fail, may indicate persistent network issue
   - Check monitoring cluster node health (Talos)
   - Verify vxlan overlay (if applicable) between subnets

## Prevention

1. **Liveness/Readiness Probes**
   - pulse deployment should have readiness probe on service endpoint
   - Ensures service is ready before pulse-agent attempts connection
   - Current: pulse-agent relies on retry logic (acceptable for transient)

2. **DNS Pre-warming**
   - pulse-agent could query pulse service on pod startup (not critical)
   - Current implementation handles DNS resolution attempts automatically

3. **Monitoring**
   - Pulse logs are ingested into Coroot
   - Set up alert if pulse-agent shows repeated connection failures (not just transient)

## Related Alerts

- **pulse-webhook-rate-limiting**: High alert volume to error-hunter (different issue)
- **Coroot "unknown" health**: Secondary symptom of pulse-agent connectivity loss
- **Talos node unreachable**: If monitoring cluster node is down, pulse-agent will fail

## References

- Pulse service config: `kubectl get svc -n monitoring pulse -o yaml`
- Pulse-agent DaemonSet: `kubectl get daemonset -n monitoring pulse-agent -o yaml`
- pulse-agent kubeconfig: `kubectl get configmap -n monitoring pulse-agent-kubeconfig -o yaml`
- Monitoring cluster: Talos K3s on Pihanga (talos-monitor, VMID 200, 10.10.0.30)
- MCP tools: `kubectl_get_pods`, `kubectl_logs`, `kubectl_get_deployments`

## Incident History

| Incident | Date | Root Cause | Fix | Status |
|----------|------|------------|-----|--------|
| #215 | 2026-03-01 13:38–13:40 | Pod lifecycle race (fresh container, DNS warmup) | Restarted pulse + pulse-agent pod | Resolved |

