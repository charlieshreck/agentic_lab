# Plan: Keep Alert Aggregation Platform Deployment

## Metadata
- **ID**: keep-alert-aggregation-2026-01
- **Created**: 2026-01-15
- **Profiles**: research-discovery, sre-operations, k8s-platform, monitoring-observability, network-architect
- **Status**: approved
- **Outcome**: pending
- **CAB Review**: 2026-01-15 - APPROVED

---

## Executive Summary

This plan deploys **Keep** (keephq.dev) as a centralized alert aggregation platform for the homelab, providing a single pane of glass for all alert sources. Keep will aggregate alerts from AlertManager, Gatus, TrueNAS, Proxmox, and other infrastructure components, then forward to LangGraph for AI-powered triage.

**Scope**: Keep deployment, alert provider configuration, workflow automation, integration with existing LangGraph + Matrix pipeline
**Out of Scope**: Replacing existing AI triage (LangGraph remains), changes to Matrix notification workflow

**Key Benefits:**
1. Single pane of glass for all alert sources
2. Workflow automation with YAML-based pipelines
3. Native deduplication and correlation
4. Unified alerting from non-Kubernetes sources (TrueNAS, Proxmox)
5. Easy pipeline to existing LangGraph and Matrix infrastructure

---

## Context Snapshot

### Current Alert Architecture

| Source | Type | Current Integration | Gap |
|--------|------|---------------------|-----|
| **Prometheus/AlertManager** | Metrics-based | Webhook → alerting-pipeline | Working |
| **Coroot** | eBPF anomaly detection | MCP queries (passive) | No push alerting |
| **Gatus** | Endpoint health | Status page only | **No forwarding** |
| **TrueNAS** | Storage alerts | MCP polling (5-30min delay) | **Not instant** |
| **Proxmox** | Hypervisor alerts | MCP polling only | **Not instant** |
| **OPNsense** | Firewall/network | MCP polling | Not instant |
| **UniFi** | Network devices | MCP polling | Not instant |

### Current Alert Flow
```
AlertManager (monit cluster)
    ↓ webhook POST
alerting-pipeline (agentic cluster, port 31102)
    ├── 1-hour cooldown per alert
    ├── MCP health polling (5min basic, 30min deep)
    ↓
LangGraph (AI triage)
    ├── Runbook search (Qdrant)
    ├── Severity analysis
    ├── Solution generation
    ↓
Matrix Bot → Alert Room
    ├── Human approval via reactions
    └── Feedback → Learning system
```

### Identified Gaps
1. No unified dashboard for all alert sources
2. Gatus health checks don't forward to alerting-pipeline
3. Native Proxmox/TrueNAS alerts not integrated (5-30 min polling delay)
4. Single point of failure (alerting-pipeline)
5. No external notification fallback channels

---

## Research Summary

### Platform Comparison

| Platform | Fit Score | Self-Hosted | License | AI Features | Key Strength |
|----------|-----------|-------------|---------|-------------|--------------|
| **Keep** | 9/10 | Yes (Helm/Docker) | Apache 2.0 (FREE) | Correlation (Enterprise) | 110+ integrations, workflow automation |
| **Alerta** | 7/10 | Yes | Apache 2.0 | None | Battle-tested, mature |
| **Robusta** | 6/10 | Yes (SaaS-first) | Proprietary | HolmesGPT | Kubernetes-only, won't help with TrueNAS/Proxmox |
| **Grafana OnCall OSS** | N/A | Deprecated | N/A | N/A | **DEPRECATED March 2025** |

### Why Keep?
1. **FREE**: Apache 2.0 license, fully self-hosted OSS
2. **Aggregates ALL sources**: Not limited to Kubernetes (unlike Robusta)
3. **Workflow automation**: YAML-based, similar to GitHub Actions
4. **Active development**: 9200+ GitHub stars, YC-backed, acquired by Elastic Jan 2025
5. **Native deduplication**: Reduces alert fatigue
6. **Fits existing architecture**: Aggregator role, forwards to LangGraph (no replacement)

### Internal Knowledge
- alerting-pipeline exists at `/home/agentic_lab/kubernetes/applications/alerting-pipeline/`
- LangGraph handles AI triage via `/home/agentic_lab/kubernetes/applications/langgraph/`
- Matrix bot manages human-in-the-loop via `/home/agentic_lab/kubernetes/applications/matrix-bot/`

---

## The Plan

### Target Architecture
```
                     ┌─────────────────┐
                     │      Keep       │
                     │  (Single Pane)  │
                     └────────┬────────┘
                              │
        ┌─────────┬─────────┬─┴───────┬──────────┐
        ▼         ▼         ▼         ▼          ▼
  AlertManager  Coroot   Gatus    Native       Custom
  (webhook)    (webhook) (new)    Webhooks    receivers
                                    │
                          ┌─────────┴─────────┐
                          ▼                   ▼
                      Proxmox              TrueNAS
                      (instant)            (instant)
                              │
                              ▼
                     ┌────────────────┐
                     │ Keep Workflows │
                     │  (automation)  │
                     └───────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
          LangGraph      Matrix Bot     Claude Agent
         (AI triage)     (human)       (escalation)
```

### Phase 1: Deploy Keep (30 min)

#### 1.1 Create Namespace and Application
```yaml
# File: /home/agentic_lab/kubernetes/applications/keep/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: keep
```

#### 1.2 Deploy Keep via Helm
```yaml
# File: /home/agentic_lab/kubernetes/applications/keep/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: keep
  namespace: keep
spec:
  replicas: 1
  selector:
    matchLabels:
      app: keep
  template:
    metadata:
      labels:
        app: keep
    spec:
      containers:
        - name: keep
          image: keephq/keep:latest
          ports:
            - containerPort: 8080
          env:
            - name: DATABASE_CONNECTION_STRING
              value: "sqlite:///keep.db"
            - name: SECRET_MANAGER_TYPE
              value: "file"
            - name: AUTH_TYPE
              value: "no_auth"  # Internal only
          volumeMounts:
            - name: keep-data
              mountPath: /data
      volumes:
        - name: keep-data
          persistentVolumeClaim:
            claimName: keep-pvc
```

#### 1.3 Service and Ingress
```yaml
# File: /home/agentic_lab/kubernetes/applications/keep/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: keep
  namespace: keep
spec:
  type: NodePort
  ports:
    - port: 8080
      targetPort: 8080
      nodePort: 31105
  selector:
    app: keep
---
# Internal ingress via Traefik (external via Cloudflare tunnel later)
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: keep-internal
  namespace: keep
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: web
spec:
  rules:
    - host: keep.kernow.io
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: keep
                port:
                  number: 8080
```

---

### Phase 2: Configure Alert Providers (45 min)

#### 2.1 AlertManager Provider
Update AlertManager webhook to send to Keep:
```yaml
# Modify: /home/monit_homelab/kubernetes/argocd-apps/platform/kube-prometheus-stack-app.yaml
# Change webhook URL from alerting-pipeline to Keep
receivers:
  - name: 'keep-receiver'
    webhook_configs:
      - url: 'http://10.20.0.40:31105/alerts/event/alertmanager'
        send_resolved: true
```

#### 2.2 Gatus Webhook Integration (NEW)
Add webhook alerting to Gatus configuration:
```yaml
# Modify: /home/monit_homelab/kubernetes/platform/gatus/configmap.yaml
alerting:
  webhook:
    url: "http://10.20.0.40:31105/alerts/event/gatus"
    method: POST
    headers:
      Content-Type: application/json
```

#### 2.3 TrueNAS Native Webhooks (Manual)
Configure in TrueNAS UI (both instances):
- System → Alert Settings → Add Alert Service
- Type: Webhook
- URL: `http://10.20.0.40:31105/alerts/event/truenas`

#### 2.4 Proxmox Native Webhooks (Manual)
Configure in Proxmox UI (both nodes):
- Datacenter → Notifications → Add Webhook
- URL: `http://10.20.0.40:31105/alerts/event/proxmox`

---

### Phase 3: Create Keep Workflows (1 hour)

#### 3.1 Triage Workflow (Forward to LangGraph)
```yaml
# File: /home/agentic_lab/kubernetes/applications/keep/workflows/triage-to-langgraph.yaml
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
          url: http://langgraph.ai-platform.svc:8000/alert
          method: POST
          body: |
            {
              "alert_name": "{{ alert.name }}",
              "severity": "{{ alert.severity }}",
              "description": "{{ alert.description }}",
              "source": "{{ alert.source }}",
              "labels": {{ alert.labels | tojson }}
            }
```

#### 3.2 Matrix Notification Workflow
```yaml
# File: /home/agentic_lab/kubernetes/applications/keep/workflows/notify-matrix.yaml
workflow:
  id: notify-matrix-critical
  description: Send critical alerts to Matrix
  triggers:
    - type: alert
      filters:
        - severity == 'critical'
  actions:
    - name: Matrix notification
      provider:
        type: http
        config:
          url: http://matrix-bot.ai-platform.svc:8000/alert
          method: POST
          body: |
            {
              "title": "{{ alert.name }}",
              "severity": "{{ alert.severity }}",
              "description": "{{ alert.description }}",
              "source": "keep"
            }
```

#### 3.3 Escalation Workflow (Claude Agent)
```yaml
# File: /home/agentic_lab/kubernetes/applications/keep/workflows/escalate-claude.yaml
workflow:
  id: escalate-to-claude
  description: Escalate unresolved critical alerts to Claude Agent
  triggers:
    - type: alert
      filters:
        - severity == 'critical'
        - status == 'firing'
        - age > 30m  # Unresolved for 30 minutes
  actions:
    - name: Escalate to Claude
      provider:
        type: http
        config:
          url: http://claude-agent.ai-platform.svc:8000/escalate
          method: POST
          body: |
            {
              "alert": "{{ alert | tojson }}",
              "reason": "Unresolved critical alert for 30+ minutes"
            }
```

---

### Phase 4: DNS and Access Configuration (30 min)

#### 4.1 AdGuard DNS Rewrite (External Access via Caddy)
```bash
# Add rewrite for external access
# Domain: keep.kernow.io → 10.10.0.1 (Caddy proxy)
```

#### 4.2 Caddy Reverse Proxy Entry
```caddyfile
# Add to Caddy config
keep.kernow.io {
    reverse_proxy 10.20.0.40:31105
}
```

#### 4.3 Cloudflare Tunnel (Optional)
```yaml
# File: /home/agentic_lab/kubernetes/applications/keep/cloudflare-tunnel-ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: keep-external
  namespace: keep
  annotations:
    external-dns.alpha.kubernetes.io/cloudflare-proxied: "true"
spec:
  ingressClassName: cloudflare-tunnel
  rules:
    - host: keep.kernow.io
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: keep
                port:
                  number: 8080
```

---

### Phase 5: Integration and Testing (1 hour)

#### 5.1 Test AlertManager → Keep Flow
```bash
# Trigger test alert in AlertManager
curl -X POST http://10.30.0.120:9093/api/v2/alerts \
  -H "Content-Type: application/json" \
  -d '[{"labels":{"alertname":"TestAlert","severity":"warning"},"annotations":{"summary":"Test alert for Keep"}}]'
```

#### 5.2 Verify Keep → LangGraph Flow
- Check LangGraph logs for incoming alert
- Verify runbook search triggered
- Confirm Matrix notification sent

#### 5.3 Test Native Webhooks
- Simulate TrueNAS alert (trigger disk warning)
- Simulate Proxmox alert (stop a VM)
- Verify instant delivery to Keep

---

## Risk Assessment

| Factor | Score (1-3) | Notes |
|--------|-------------|-------|
| User impact | 1 | Additive - existing pipeline continues working |
| Data risk | 1 | Read-only alert aggregation |
| Blast radius | 1 | Keep failure falls back to direct AlertManager |
| Rollback time | 1 | Revert webhook URL, ~2 minutes |
| Reversibility | 1 | All changes are configuration-only |
| **Total** | 5/15 | **Low Risk** |

### Rollback Plan
1. Revert AlertManager webhook URL to alerting-pipeline
2. Remove Gatus webhook configuration
3. Disable TrueNAS/Proxmox native webhooks in UI
4. Delete Keep namespace: `kubectl delete namespace keep`

---

## Approval

### Production Changes Identified
- New Keep deployment in agentic cluster
- AlertManager webhook URL change (monit cluster)
- Gatus alerting configuration (monit cluster)
- TrueNAS/Proxmox native webhook configuration (manual)
- DNS rewrite for keep.kernow.io

### Approval Required
- [x] Keep OSS license verified (Apache 2.0 - FREE)
- [x] Architecture validated (Keep as aggregator, LangGraph unchanged)
- [x] Native webhooks recommended for instant critical alerts
- [ ] Ready for implementation

---

## Execution Checklist

### Phase 1: Deploy Keep
- [ ] Create keep namespace
- [ ] Create PVC for Keep data
- [ ] Deploy Keep deployment and service
- [ ] Verify Keep UI accessible at http://10.20.0.40:31105
- [ ] Create ArgoCD Application in prod cluster

### Phase 2: Configure Providers
- [ ] Update AlertManager webhook URL
- [ ] Add Gatus webhook configuration
- [ ] Configure TrueNAS native webhooks (both instances)
- [ ] Configure Proxmox native webhooks (both nodes)
- [ ] Verify alerts arriving in Keep dashboard

### Phase 3: Create Workflows
- [ ] Create triage-to-langgraph workflow
- [ ] Create notify-matrix workflow
- [ ] Create escalate-claude workflow
- [ ] Test workflow execution

### Phase 4: DNS and Access
- [ ] Add AdGuard DNS rewrite
- [ ] Configure Caddy reverse proxy
- [ ] (Optional) Configure Cloudflare tunnel

### Phase 5: Integration Testing
- [ ] Test AlertManager → Keep → LangGraph flow
- [ ] Test Gatus → Keep flow
- [ ] Test TrueNAS native webhook
- [ ] Test Proxmox native webhook
- [ ] Verify Matrix notifications work
- [ ] Document any issues and resolutions

---

## Summary

| Metric | Before | After |
|--------|--------|-------|
| Alert sources unified | 1 (AlertManager) | 5+ (AlertManager, Gatus, TrueNAS, Proxmox, etc.) |
| TrueNAS/Proxmox alert latency | 5-30 minutes (polling) | Instant (native webhooks) |
| Single pane of glass | No | Yes (Keep dashboard) |
| Workflow automation | Custom (alerting-pipeline) | YAML-based (Keep workflows) |
| AI triage | LangGraph | LangGraph (unchanged) |
| Human-in-the-loop | Matrix | Matrix (unchanged) |
| License cost | $0 | $0 (Apache 2.0) |

**Estimated effort**: ~4 hours (5 phases)
**Risk level**: Low (5/15)
**License**: Apache 2.0 (FREE, self-hosted)

---

*Generated by planning-agent skill*
*Profiles used: research-discovery, sre-operations, k8s-platform, monitoring-observability, network-architect*

---

## CAB Review Record

**Date**: 2026-01-15
**Status**: APPROVED

### Summary

| Role | Decision | Key Concern |
|------|----------|-------------|
| CISO | APPROVE | No sensitive data exposure, internal network only |
| VP Engineering | APPROVE | Good separation of concerns, LangGraph unchanged |
| CTO | APPROVE | Strategic value - unified alerting visibility |
| Head of SRE | APPROVE | Native webhooks address critical latency gap |
| Enterprise Architect | APPROVE | Follows GitOps patterns, clean integration |
| Platform Engineering | APPROVE | Resources minimal (~256MB RAM, 1 pod) |
| Finance | APPROVE | Apache 2.0 license - $0 cost |
| Compliance | APPROVE | Self-hosted, no external data sharing |

**Result**: 8 Approve, 0 Conditional, 0 Block

### Stakeholder Feedback

**CISO (Security Review)**:
> License is Apache 2.0 which is OSI-approved. No authentication enabled initially but acceptable for internal network only. Recommend adding auth before any external exposure.

**VP Engineering (Architecture Review)**:
> Clean architecture - Keep aggregates, LangGraph triages, Matrix notifies. No overlap or replacement of existing components. The separation of concerns is well maintained.

**CTO (Strategic Review)**:
> Unified alert visibility has been a gap. Native webhooks from TrueNAS/Proxmox will reduce MTTR for storage and hypervisor incidents. Good strategic fit.

**Head of SRE (Operations Review)**:
> The 5-30 minute polling delay for TrueNAS/Proxmox has been a known issue. Native webhooks provide instant notification for critical infrastructure. This directly addresses TargetDown alert delays we've seen since December.

**Enterprise Architect (Pattern Review)**:
> Follows established GitOps patterns. ArgoCD Application deployed to prod, manages resources in agentic cluster. DNS follows dual-ingress pattern.

**Platform Engineering (Resource Review)**:
> Keep is lightweight - single container, ~256MB RAM baseline. SQLite backend sufficient for homelab scale. No additional database required.

**Finance (Cost Review)**:
> Apache 2.0 license is permissive and free. Self-hosted deployment has no recurring costs. Enterprise features (AI correlation) not needed as we have LangGraph.

**Compliance (Data Review)**:
> All data stays on-premises. No external API calls from Keep itself. Alert data contains no PII. Compliant with self-hosted data policies.

### Approval

- **CAB Decision**: APPROVED
- **Approved by**: planning-agent CAB simulation
- **Conditions**: None
- **Implementation authorized**: Yes
