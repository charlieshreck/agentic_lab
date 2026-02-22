# Pulse Webhook Normalizer

## Overview

Pulse (rcourtman/pulse) is a Proxmox/K8s monitoring tool deployed in the monit cluster.
It sends webhooks to KAO LangGraph at `http://10.20.0.40:30800/ingest?source=pulse`.

The `normalize_pulse` function in `langgraph.yaml` converts Pulse alert payloads into
KAO's universal `IngestPayload` format.

## Pulse Webhook Field Mapping

Pulse sends alerts with these JSON fields (Go struct `WebhookPayloadData`):

| Pulse field    | KAO field      | Notes                              |
|----------------|----------------|------------------------------------|
| `id`           | `fingerprint`  | e.g. `"Pihanga:Pihanga:200-memory"` |
| `level`        | `severity`     | `"critical"`, `"warning"`, `"info"` |
| `type`         | alert type     | `"memory"`, `"cpu"`, `"diskRead"` etc |
| `resourceName` | resource       | e.g. `"talos-monitor"`, `"plex"` |
| `resourceId`   | resource ID    | e.g. `"Pihanga:Pihanga:200"` |
| `resourceType` | label          | `"VM"`, `"Container"`, `"Node"` |
| `node`         | label          | Proxmox node name |
| `message`      | `description`  | e.g. `"VM memory at 96.2%"` |
| `value`        | (in desc)      | Numeric value |
| `threshold`    | (in desc)      | Alert threshold |

**IMPORTANT**: Pulse does NOT use `check_name`, `name`, `severity`, or `fingerprint` fields.

## Common Failure: All Pulse Alerts Show as "Pulse Check"

**Symptom**: KAO creates incident titled "Pulse Check" with fingerprint `pulse-unknow`

**Root cause**: `normalize_pulse` using wrong field names:
- `body.get("check_name")` → None
- `body.get("name")` → None
- Falls back to `alert_name = "Pulse Check"`
- `body.get("check_name", "unknown")` → "unknown" → fingerprint = "pulse-unknown" (12-char: "pulse-unknow")
- All alerts deduplicate to same fingerprint → single "Pulse Check" incident

**Fix**: Ensure `normalize_pulse` uses correct field names:
```python
def normalize_pulse(body: dict) -> dict:
    alert_type = body.get("type", "check")
    resource_name = body.get("resourceName") or body.get("resourceId", "unknown")
    alert_name = f"{alert_type} - {resource_name}" if resource_name else alert_type
    return {
        "source": "pulse",
        "alert_name": alert_name,
        "severity": body.get("level") or body.get("severity") or "warning",
        "description": body.get("message") or body.get("description") or "",
        "fingerprint": body.get("id") or f"pulse-{alert_name}",
        "labels": {
            "resource_type": body.get("resourceType"),
            "node": body.get("node"),
            "resource_id": body.get("resourceId"),
        },
        "raw_payload": body,
    }
```

## Alert Suppression Rules

Some Pulse alerts are intentionally suppressed in the KAO (in `SUPPRESSED_ALERT_KEYWORDS`):
- `["memory", "plex"]` — Proxmox reports allocated VM memory, not actual guest usage
- `["memory", "haos"]` — Home Assistant OS runs with high memory by design

After fixing the normalizer, these will match correctly (e.g., `"memory - plex"` contains both keywords).

## Webhook Rate Limiting

Pulse has a built-in rate limiter: max 10 webhooks per 60 seconds per URL.
When many alerts fire simultaneously (e.g., memory pressure across all hosts), some
webhooks get dropped with: `"Webhook rate limit exceeded, dropping request"`

**Mitigation**: This is a Pulse UI configuration — increase the rate limit in
Pulse Settings → Notification Destinations → KAO LangGraph webhook settings.

## Monitoring Cluster Memory Pressure

Pulse frequently alerts on memory for these hosts/VMs:
- `talos-monitor` (VMID 200 on Pihanga) — Monitoring K8s VM, typically ~90%+ due to ClickHouse
- `Pihanga` (node) — Proxmox host, high due to monitoring VM
- `Ruapehu` (node) — Proxmox host, high due to Talos VMs + media stack

These are expected high-memory workloads. Check:
```bash
kubectl --context admin@monitoring-cluster top pods -n monitoring --sort-by=memory
```

The `plex` VM memory alert is suppressed (Proxmox reports balloon allocation, not actual usage).

## Deployment

LangGraph is deployed in the agentic cluster (ai-platform namespace).
After changing `normalize_pulse` in `langgraph.yaml`, ArgoCD auto-syncs and restarts the pod.

Check that the fix took effect:
```bash
kubectl --context admin@agentic-platform logs -n ai-platform deployment/langgraph | grep -i pulse
```

Expected after fix: `Ingest: source=pulse` → creates incidents like `memory - talos-monitor`
instead of `Pulse Check`.
