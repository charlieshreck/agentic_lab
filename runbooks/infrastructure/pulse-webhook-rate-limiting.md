# Pulse Webhook Rate-Limiting

**Category**: Observability / Monitoring
**Severity**: Warning
**Pattern**: Transient burst alert
**Last Updated**: 2026-02-26

## Summary

Pulse health monitoring sends health checks to the KAO LangGraph webhook (error-hunter) via `http://10.20.0.40:30800/ingest?source=pulse`. When multiple infrastructure alerts fire simultaneously (e.g., memory pressure on hypervisors), pulse may exceed the webhook rate limit (configured at ~10 requests per 60-second window).

This is a **transient pattern** that self-heals once the alert burst subsides. No action required in most cases.

## Recognition

Alert fires as generic "check" from pulse when webhook rate-limiting is detected:
- Message: `"Webhook rate limit exceeded, dropping request"`
- Component: pulse (monitoring cluster)
- Common triggers: Proxmox node memory > 85%, VM memory > 85%

Example incident: #215 (2026-02-26 13:38–13:39, 1-minute burst)

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

Rate-limiting is **intentional rate-shaping** on the webhook to prevent cascade storms. It cannot be disabled without risking system overload.

### Long-Term Mitigations
1. **Reduce alert burst**: Stagger Proxmox memory checks (pulse config)
2. **Increase webhook capacity**: Horizontal-scale error-hunter if persistently rate-limited
3. **Alert grouping**: Combine related memory alerts (Ruapehu node + its VMs) into single check

## Related Alerts

- **Ruapehu/Pihanga high memory**: Proxmox hypervisor memory pressure (separate root cause)
- **Pod CrashLoopBackOff**: If error-hunter itself is crashing, investigate separately

## References

- Error-hunter service: `http://10.20.0.40:30801` (REST API)
- Pulse logs: `kubectl -n monitoring logs pod/pulse-*`
- Monitoring cluster: Talos K3s on Pihanga (10.10.0.30)
