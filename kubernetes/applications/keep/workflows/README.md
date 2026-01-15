# Keep Workflows

These workflow definitions should be imported into Keep via the UI or API after deployment.

## Workflow: triage-to-langgraph

Routes all alerts to LangGraph for AI-powered triage.

```yaml
workflow:
  id: triage-to-langgraph
  description: Route alerts to LangGraph for AI triage
  triggers:
    - type: alert
      filters:
        - severity in ['critical', 'warning']
  actions:
    - name: Forward to LangGraph
      provider:
        type: http
        config:
          url: http://langgraph.ai-platform.svc.cluster.local:8000/alert
          method: POST
          headers:
            Content-Type: application/json
          body: |
            {
              "id": "{{ alert.id }}",
              "alertname": "{{ alert.name }}",
              "severity": "{{ alert.severity }}",
              "description": "{{ alert.description }}",
              "namespace": "{{ alert.labels.namespace | default('unknown') }}",
              "labels": {{ alert.labels | tojson }},
              "annotations": {{ alert.annotations | tojson }},
              "source": "{{ alert.source }}"
            }
```

## Workflow: notify-matrix-critical

Sends critical alerts directly to Matrix for immediate visibility.

```yaml
workflow:
  id: notify-matrix-critical
  description: Send critical alerts to Matrix immediately
  triggers:
    - type: alert
      filters:
        - severity == 'critical'
  actions:
    - name: Matrix notification
      provider:
        type: http
        config:
          url: http://matrix-bot.ai-platform.svc.cluster.local:8000/alert
          method: POST
          headers:
            Content-Type: application/json
          body: |
            {
              "title": "{{ alert.name }}",
              "severity": "{{ alert.severity }}",
              "message": "{{ alert.description }}",
              "source": "keep",
              "context": "Via Keep aggregation"
            }
```

## Workflow: escalate-claude-unresolved

Escalates unresolved critical alerts to Claude Agent for deep investigation.

```yaml
workflow:
  id: escalate-claude-unresolved
  description: Escalate unresolved critical alerts to Claude Agent
  triggers:
    - type: alert
      filters:
        - severity == 'critical'
        - status == 'firing'
        - lastReceived > 30m  # Firing for over 30 minutes
  actions:
    - name: Escalate to Claude
      provider:
        type: http
        config:
          url: http://claude-agent.ai-platform.svc.cluster.local:8000/escalate
          method: POST
          headers:
            Content-Type: application/json
          body: |
            {
              "alert": {{ alert | tojson }},
              "reason": "Unresolved critical alert for 30+ minutes",
              "request": "Investigate and provide remediation steps"
            }
```

## Provider Configuration

After deploying Keep, configure these providers in the Keep UI:

### 1. AlertManager Provider
- Type: alertmanager
- URL: http://10.30.0.120:9093
- Purpose: Receive alerts from Prometheus

### 2. Gatus Provider (Webhook)
- Type: webhook
- Endpoint: /alerts/event/gatus
- Purpose: Receive health check alerts from Gatus

### 3. TrueNAS Provider (Webhook)
- Type: webhook
- Endpoint: /alerts/event/truenas
- Purpose: Receive storage alerts from TrueNAS

### 4. Proxmox Provider (Webhook)
- Type: webhook
- Endpoint: /alerts/event/proxmox
- Purpose: Receive hypervisor alerts from Proxmox
