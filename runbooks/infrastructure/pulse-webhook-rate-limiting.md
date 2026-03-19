# Pulse Webhook Rate-Limiting

**Category**: Observability / Monitoring
**Severity**: Warning
**Pattern**: Transient burst alert (RESOLVED 2026-03-19)
**Last Updated**: 2026-03-19

## Summary

Pulse health monitoring sends health checks to the KAO LangGraph webhook (error-hunter) via `http://10.20.0.40:30800/ingest?source=pulse`. Previously, when multiple infrastructure alerts fired simultaneously (e.g., memory pressure on hypervisors), pulse would exceed the webhook rate limit.

**Status**: FIXED as of 2026-03-19 by increasing `PULSE_WEBHOOK_RATE_LIMIT` from 10/60s to 60/60s in the deployment configuration. The rate limit can now sustain 1 webhook request per second without dropping notifications.

## Recognition

Alert fires as generic "check" from pulse when webhook rate-limiting is detected:
- Message: `"Webhook rate limit exceeded, dropping request"`
- Component: pulse (monitoring cluster)
- Common triggers: Proxmox node memory > 85%, VM memory > 85%

Example incident: #215 (2026-03-19, resolved by permanent fix)

## Permanent Fix (Applied 2026-03-19)

**Issue**: Dual persistent memory alerts (Synapse LXC 86-87%, Ruapehu node 87%) firing every ~10 seconds generated webhook notifications at unsustainable rate (~2 requests per 10 seconds), exceeding the hardcoded 10-request-per-60-second rate limit.

**Solution Applied**:
- Updated `PULSE_WEBHOOK_RATE_LIMIT` environment variable from default (10/60s) to **60/60s** in `/home/monit_homelab/kubernetes/platform/pulse/deployment.yaml`
- This provides 6x capacity headroom for alert bursts while maintaining rate-shaping
- Storage class: Uses `local-path` (standard on monit cluster, sufficient for Pulse state persistence)

**Result**: Pulse pod now sustains ~1 webhook per second without rate-limiting. Persistent memory alerts no longer cause dropped webhook notifications.

## Investigation Protocol

1. **Check current webhook status**
   ```bash
   kubectl -n ai-platform logs deployment/error-hunter | tail -50 | grep -i rate
   ```
   Look for recent rate-limit errors or backpressure indicators.

2. **Verify infrastructure health**
   - Check if the underlying alerts (memory, CPU) are real or just noise
   - Run: `curl http://10.10.0.22:3456/webhook/screen/status` (Tamar estate status)

3. **Check webhook latency**
   - High latency on error-hunter can cause rate-limit hits
   - Pulse logs show: `"Notification failed, scheduled for retry"`

## Resolution

### If Still Rate-Limited
1. Check error-hunter pod status:
   ```bash
   kubectl get pod -n ai-platform deployment/error-hunter
   ```
2. Check for processing backlog:
   ```bash
   kubectl logs -n ai-platform deployment/error-hunter | grep -i queue | tail -5
   ```

### If Self-Healed (Expected)
- Mark as transient in patrol system
- No action needed if alerts return to normal within 2–5 minutes
- Pattern is benign: webhook recovers after alert burst subsides

## Prevention

Rate-limiting is **intentional rate-shaping** on the webhook to prevent cascade storms.

### Implemented Mitigations (2026-03-19)
1. ✅ **Increased webhook rate limit**: Pulse now handles 60 requests per 60-second window (was 10/60s)
   - Provides 6x headroom for alert bursts
   - No longer requires manual remediation for dual persistent memory alerts

### Future Optimizations (if rate-limiting recurs)
1. **Reduce alert burst**: Stagger Proxmox memory checks (pulse config)
2. **Horizontal-scale error-hunter**: Add replicas if webhook processing becomes bottleneck
3. **Alert grouping**: Combine related memory alerts (Ruapehu node + its VMs) into single check

## Related Alerts

- **Ruapehu/Pihanga high memory**: Proxmox hypervisor memory pressure (separate root cause)
- **Pod CrashLoopBackOff**: If error-hunter itself is crashing, investigate separately

## References

- Error-hunter service: `http://10.20.0.40:30801` (REST API)
- Pulse logs: `kubectl -n monitoring logs pod/pulse-*`
- Monitoring cluster: Talos K3s on Pihanga (10.10.0.30)
