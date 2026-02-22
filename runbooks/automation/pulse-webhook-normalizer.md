# Pulse Webhook Normalizer

## Overview

Pulse (rcourtman/pulse) is a Proxmox/K8s monitoring tool deployed in the monit cluster.
It sends webhooks to KAO LangGraph at `http://10.20.0.40:30800/ingest?source=pulse`.

The `normalize_pulse` function in `langgraph.yaml` converts Pulse alert payloads into
KAO's universal `IngestPayload` format.

## Pulse Webhook Formats

Pulse supports two webhook payload formats depending on whether a custom template is configured.

### Native Format (no custom template)

Go struct `WebhookPayloadData`:

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

### Custom Template Format

When a custom Go template is configured on the Pulse webhook destination, the payload
uses different fields. The Kernow homelab KAO webhook uses this custom format:

| Custom field | Example value              | Notes                               |
|--------------|----------------------------|-------------------------------------|
| `title`      | `"memory: plex on Ruapehu"` | Format: `"{type}: {resource} on {node}"` |
| `text`       | `"VM memory at 100.0%..."`  | Alert description                   |
| `resource`   | `"plex"`                    | Resource name                       |
| `severity`   | `"critical"`                | Alert severity                      |
| `node`       | `"Ruapehu"`                 | Proxmox node                        |
| `duration`   | `"1h 58m"`                  | Time alert has been active          |
| `source`     | `"pulse"`                   | Always "pulse"                      |

**IMPORTANT**: The custom template does NOT include `type`, `level`, `id`, `resourceName`, or `resourceId`.

## Current normalize_pulse Implementation

`normalize_pulse` detects the format by presence of the `type` field:

```python
def normalize_pulse(body: dict) -> dict:
    if "type" in body:
        # Native Pulse format
        alert_type = body.get("type", "check")
        resource_name = body.get("resourceName") or body.get("resourceId", "unknown")
        alert_name = f"{alert_type} - {resource_name}" if resource_name and resource_name != "unknown" else alert_type
        severity = body.get("level") or "warning"
        description = body.get("message") or ""
        fingerprint = body.get("id") or f"pulse-{alert_name}"
    else:
        # Custom template format: title like "memory: plex on Ruapehu"
        title = body.get("title", "")
        resource_name = body.get("resource", "unknown")
        alert_type = title.split(":")[0].strip() if ":" in title else (title or "check")
        alert_name = f"{alert_type} - {resource_name}" if resource_name and resource_name != "unknown" else alert_type
        severity = body.get("severity", "warning")
        description = body.get("text") or ""
        fingerprint = f"pulse-{alert_name}".replace(" ", "-").lower()
    return {
        "source": "pulse",
        "alert_name": alert_name,
        "severity": severity,
        "description": description,
        "fingerprint": fingerprint,
        "labels": {
            "resource_type": body.get("resourceType"),
            "node": body.get("node"),
            "resource_id": body.get("resourceId") or body.get("resource"),
        },
        "raw_payload": body,
    }
```

## Common Failure: All Pulse Alerts Show as "Pulse Check"

**Symptom**: KAO creates incident titled "Pulse Check" with fingerprint `pulse-unknow`

**Root cause**: `normalize_pulse` using wrong field names:
- `body.get("check_name")` → None
- `body.get("name")` → None
- Falls back to `alert_name = "Pulse Check"`
- `body.get("check_name", "unknown")` → "unknown" → fingerprint = "pulse-unknown" (12-char: "pulse-unknow")
- All alerts deduplicate to same fingerprint → single "Pulse Check" incident

## Common Failure: Pod Running Old Code After ConfigMap Update

**Symptom**: ConfigMap has been updated, pod's `/code/main.py` shows new code on disk,
but behavior is unchanged (still generating old fingerprints).

**Root cause**: Python loads and compiles code at startup. If the ConfigMap is updated while
the pod is running, the kubelet syncs the new file to disk but the Python process continues
running the old compiled bytecode from memory.

**Fix**: Force pod restart by adding/updating the `kubectl.kubernetes.io/restartedAt` annotation
on the Deployment's pod template, then commit + push + ArgoCD sync:

```yaml
  template:
    metadata:
      annotations:
        kubectl.kubernetes.io/restartedAt: "2026-02-22T22:00:00Z"  # update timestamp
```

After restart, verify with:
```bash
kubectl --context admin@agentic-platform logs -n ai-platform deployment/langgraph | grep -i pulse
```

## Alert Suppression Rules

Some Pulse alerts are intentionally suppressed in the KAO (in `SUPPRESSED_ALERT_KEYWORDS`):
- `["memory", "plex"]` — Proxmox reports allocated VM memory, not actual guest usage
- `["memory", "haos"]` — Home Assistant OS runs with high memory by design

With the custom template format, `alert_name` is built from title prefix + resource:
- `title="memory: plex on Ruapehu"`, `resource="plex"` → `alert_name="memory - plex"` → suppressed ✓

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
After changing `normalize_pulse` in `langgraph.yaml`, update the `restartedAt` annotation,
then commit + push. ArgoCD auto-syncs and restarts the pod.

Check that the fix took effect:
```bash
kubectl --context admin@agentic-platform logs -n ai-platform deployment/langgraph | grep -i pulse
```

Expected after fix: `Ingest: source=pulse` → creates incidents like `memory - talos-monitor`
(or suppresses `memory - plex`) instead of `Pulse Check`.
