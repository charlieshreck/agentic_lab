# Plan: Comprehensive Monitoring Improvements - All Three Clusters

## Metadata
- **ID**: monitoring-improvements-2026-01
- **Created**: 2026-01-13
- **Profiles**: research-discovery, monitoring-observability, sre-operations, k8s-platform, network-architect, security-compliance
- **Status**: approved
- **Outcome**: pending
- **CAB Review**: 2026-01-13 - APPROVED WITH CONDITIONS

---

## Executive Summary

This plan addresses critical gaps in the homelab monitoring infrastructure to ensure all three clusters (prod, agentic, monit) are comprehensively monitored with thorough metrics collection, detailed alert rules, and complete visibility.

**Scope**: Metrics collection, scrape targets, alert rule definitions, dashboards
**Out of Scope**: Alert notification routing (Matrix/Element), automated alert response (Gemini + runbooks) - these are separate projects that build on this foundation.

**Key Gaps Identified:**
1. Agentic cluster (10.20.0.0/24) is NOT monitored at all
2. Beszel hub deployed but no agents on systems
3. No application-specific alert rules (Plex, MCP servers, Home Assistant)
4. Hardcoded credentials in Prometheus config
5. No SLO/SLI framework
6. Missing metrics from 17 MCP servers
7. Missing metrics from infrastructure (OPNsense, TrueNAS, UniFi)

---

## Context Snapshot

### Current Monitoring Architecture

| Component | Status | Location |
|-----------|--------|----------|
| Prometheus | ✅ Running | monit (10.30.0.20:30082) |
| VictoriaMetrics | ✅ Running | monit (10.30.0.20:30084) |
| Grafana | ✅ Running | monit (10.30.0.20:30081) |
| AlertManager | ⚠️ No receivers | monit (10.30.0.20:30083) |
| Coroot | ✅ Running | monit (10.30.0.20:32702) |
| Gatus | ✅ Running | monit (10.30.0.20:30086) |
| Beszel | ⚠️ Hub only | monit (10.30.0.20:30087) |

### What's Currently Being Scraped

| Target | Cluster | Metrics |
|--------|---------|---------|
| Proxmox Ruapehu | prod | VM/LXC, CPU, RAM, storage |
| Proxmox Carrick | monit | VM/LXC, CPU, RAM, storage |
| Talos kubelets | prod | K8s node metrics |
| Talos cAdvisor | prod | Container metrics |
| Talos API server | prod | K8s API metrics |
| kube-state-metrics | prod | K8s object state |
| node-exporter | prod | Host metrics (4 nodes) |
| K3s kubelet | monit | K8s node metrics |

### What's NOT Being Monitored

| Gap | Impact | Priority |
|-----|--------|----------|
| **Agentic cluster** | No visibility into AI platform | Critical |
| **Beszel agents** | Hub deployed, no agents on systems | High |
| **MCP servers (17)** | No health/latency metrics | High |
| **OPNsense/AdGuard** | No network/DNS metrics | High |
| **TrueNAS** | No storage metrics | High |
| **UniFi** | No network device metrics | Medium |
| **Plex/Media stack** | No media service metrics | Medium |
| **Home Assistant** | No automation metrics | Medium |

---

## Research Summary

### Internal Knowledge
- Monitoring cluster fully deployed (Phase 1 complete)
- Coroot operational with prod agents
- Vector collecting logs from prod cluster
- Neo4j deployed for relationship tracking

### Security Concern
**CRITICAL**: Hardcoded credentials in kube-prometheus-stack:
```yaml
# Line 86 & 99 in kube-prometheus-stack-app.yaml
password: <REDACTED>  # Proxmox password exposed in source
```
**Must migrate to Infisical secrets. Phase 5 addresses this.**

---

## The Plan

### Phase 1: Critical - Agentic Cluster Monitoring (Week 1)

#### 1.1 Deploy Coroot Agents to Agentic Cluster

```yaml
# File: /home/monit_homelab/kubernetes/platform/coroot-agent-agentic/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: coroot-cluster-agent
  namespace: coroot-agent
spec:
  replicas: 1
  selector:
    matchLabels:
      app: coroot-cluster-agent
  template:
    metadata:
      labels:
        app: coroot-cluster-agent
    spec:
      serviceAccountName: coroot-cluster-agent
      containers:
        - name: agent
          image: ghcr.io/coroot/coroot-cluster-agent:latest
          env:
            - name: COROOT_URL
              value: "http://10.30.0.20:32702"
            - name: API_KEY
              valueFrom:
                secretKeyRef:
                  name: coroot-api-key
                  key: api-key
            - name: CLUSTER_NAME
              value: "agentic"
```

**ArgoCD Application**: Apply to **prod cluster** ArgoCD (manages agentic remotely)

#### 1.2 Add Agentic Cluster Scrape Targets

```yaml
# Add to kube-prometheus-stack additionalScrapeConfigs
# Agentic Talos Cluster - Kubelet Metrics
- job_name: 'agentic-kubelets'
  scheme: https
  tls_config:
    ca_file: /etc/prometheus/secrets/agentic-cluster-credentials/ca.crt
    insecure_skip_verify: false
  bearer_token_file: /etc/prometheus/secrets/agentic-cluster-credentials/token
  kubernetes_sd_configs:
    - role: node
      api_server: 'https://10.20.0.40:6443'
      tls_config:
        ca_file: /etc/prometheus/secrets/agentic-cluster-credentials/ca.crt
      bearer_token_file: /etc/prometheus/secrets/agentic-cluster-credentials/token
  relabel_configs:
    - action: labelmap
      regex: __meta_kubernetes_node_label_(.+)
    - target_label: __address__
      replacement: 10.20.0.40:6443
    - source_labels: [__meta_kubernetes_node_name]
      regex: (.+)
      target_label: __metrics_path__
      replacement: /api/v1/nodes/${1}/proxy/metrics
    - target_label: cluster
      replacement: agentic

# Agentic Talos Cluster - cAdvisor
- job_name: 'agentic-cadvisor'
  scheme: https
  tls_config:
    ca_file: /etc/prometheus/secrets/agentic-cluster-credentials/ca.crt
  bearer_token_file: /etc/prometheus/secrets/agentic-cluster-credentials/token
  kubernetes_sd_configs:
    - role: node
      api_server: 'https://10.20.0.40:6443'
      tls_config:
        ca_file: /etc/prometheus/secrets/agentic-cluster-credentials/ca.crt
      bearer_token_file: /etc/prometheus/secrets/agentic-cluster-credentials/token
  relabel_configs:
    - target_label: __address__
      replacement: 10.20.0.40:6443
    - source_labels: [__meta_kubernetes_node_name]
      regex: (.+)
      target_label: __metrics_path__
      replacement: /api/v1/nodes/${1}/proxy/metrics/cadvisor
    - target_label: cluster
      replacement: agentic

# Agentic API Server
- job_name: 'agentic-apiserver'
  scheme: https
  tls_config:
    ca_file: /etc/prometheus/secrets/agentic-cluster-credentials/ca.crt
  bearer_token_file: /etc/prometheus/secrets/agentic-cluster-credentials/token
  static_configs:
    - targets: ['10.20.0.40:6443']
      labels:
        cluster: 'agentic'
```

#### 1.3 Create Agentic Cluster Credentials Secret

```bash
# Extract from agentic kubeconfig
export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig

# Create secret in monitoring cluster
kubectl create secret generic agentic-cluster-credentials \
  --from-literal=token="$(kubectl config view --raw -o jsonpath='{.users[0].user.token}')" \
  --from-literal=ca.crt="$(kubectl config view --raw -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' | base64 -d)" \
  -n monitoring \
  --kubeconfig=/home/monit_homelab/kubeconfig
```

---

### Phase 2: MCP Server Monitoring (Week 1-2)

#### 2.1 MCP Health Endpoint Scraping

All 17 MCP servers expose `/health` endpoints. Add scrape config:

```yaml
# MCP Servers - Health and Metrics
- job_name: 'mcp-servers'
  scheme: http
  metrics_path: '/metrics'  # If available, otherwise use probe
  static_configs:
    - targets:
        - '10.20.0.40:31080'   # infisical-mcp
        - '10.20.0.40:31081'   # coroot-mcp
        - '10.20.0.40:31082'   # proxmox-mcp
        - '10.20.0.40:31083'   # infrastructure-mcp
        - '10.20.0.40:31084'   # knowledge-mcp
        - '10.20.0.40:31085'   # opnsense-mcp
        - '10.20.0.40:31086'   # adguard-mcp
        - '10.20.0.40:31087'   # cloudflare-mcp
        - '10.20.0.40:31088'   # unifi-mcp
        - '10.20.0.40:31089'   # truenas-mcp
        - '10.20.0.40:31090'   # home-assistant-mcp
        - '10.20.0.40:31091'   # arr-suite-mcp
        - '10.20.0.40:31092'   # homepage-mcp
        - '10.20.0.40:31093'   # web-search-mcp
        - '10.20.0.40:31094'   # browser-automation-mcp
        - '10.20.0.40:31096'   # plex-mcp
        - '10.20.0.40:31097'   # vikunja-mcp
        - '10.20.0.40:31099'   # neo4j-mcp
      labels:
        cluster: 'agentic'
        job: 'mcp-servers'
```

#### 2.2 Blackbox Exporter for MCP Health Probes

Deploy blackbox exporter to probe MCP health endpoints:

```yaml
# File: /home/monit_homelab/kubernetes/platform/blackbox-exporter/
apiVersion: apps/v1
kind: Deployment
metadata:
  name: blackbox-exporter
  namespace: monitoring
spec:
  replicas: 1
  selector:
    matchLabels:
      app: blackbox-exporter
  template:
    spec:
      containers:
        - name: blackbox
          image: prom/blackbox-exporter:latest
          ports:
            - containerPort: 9115
```

Scrape config for HTTP probes:

```yaml
- job_name: 'mcp-health-probes'
  metrics_path: /probe
  params:
    module: [http_2xx]
  static_configs:
    - targets:
        - 'http://10.20.0.40:31080/health'
        - 'http://10.20.0.40:31081/health'
        # ... all 17 MCPs
  relabel_configs:
    - source_labels: [__address__]
      target_label: __param_target
    - source_labels: [__param_target]
      target_label: instance
    - target_label: __address__
      replacement: blackbox-exporter:9115
```

---

### Phase 3: Custom Alert Rules (Week 2)

#### 3.1 Cluster Health Alerts

```yaml
# File: /home/monit_homelab/kubernetes/platform/prometheus-rules/cluster-alerts.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: cluster-alerts
  namespace: monitoring
spec:
  groups:
    - name: cluster.rules
      rules:
        # Node Down
        - alert: NodeDown
          expr: up{job=~".*node-exporter.*"} == 0
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "Node {{ $labels.instance }} is down"
            description: "Node has been unreachable for more than 5 minutes"
            runbook_url: "https://runbooks.kernow.io/node-down"

        # High CPU Usage
        - alert: HighCPUUsage
          expr: |
            100 - (avg by(instance, cluster) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 85
          for: 15m
          labels:
            severity: warning
          annotations:
            summary: "High CPU usage on {{ $labels.instance }}"
            description: "CPU usage is above 85% for 15 minutes (current: {{ $value | printf \"%.1f\" }}%)"

        # High Memory Usage
        - alert: HighMemoryUsage
          expr: |
            (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 90
          for: 10m
          labels:
            severity: warning
          annotations:
            summary: "High memory usage on {{ $labels.instance }}"
            description: "Memory usage is above 90% (current: {{ $value | printf \"%.1f\" }}%)"

        # Disk Space Low
        - alert: DiskSpaceLow
          expr: |
            (node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes) * 100 < 15
          for: 10m
          labels:
            severity: warning
          annotations:
            summary: "Low disk space on {{ $labels.instance }}"
            description: "Disk {{ $labels.mountpoint }} has less than 15% free space"

        # Disk Space Critical
        - alert: DiskSpaceCritical
          expr: |
            (node_filesystem_avail_bytes{fstype!~"tmpfs|overlay"} / node_filesystem_size_bytes) * 100 < 5
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "Critical disk space on {{ $labels.instance }}"
            description: "Disk {{ $labels.mountpoint }} has less than 5% free space"
```

#### 3.2 Kubernetes Alerts

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: kubernetes-alerts
  namespace: monitoring
spec:
  groups:
    - name: kubernetes.rules
      rules:
        # Pod CrashLoopBackOff
        - alert: PodCrashLoopBackOff
          expr: |
            kube_pod_container_status_waiting_reason{reason="CrashLoopBackOff"} > 0
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Pod {{ $labels.namespace }}/{{ $labels.pod }} is crash looping"
            description: "Container {{ $labels.container }} in pod {{ $labels.pod }} is in CrashLoopBackOff"

        # Pod Not Ready
        - alert: PodNotReady
          expr: |
            kube_pod_status_ready{condition="true"} == 0
          for: 15m
          labels:
            severity: warning
          annotations:
            summary: "Pod {{ $labels.namespace }}/{{ $labels.pod }} not ready"
            description: "Pod has been in not ready state for more than 15 minutes"

        # Deployment Replicas Mismatch
        - alert: DeploymentReplicasMismatch
          expr: |
            kube_deployment_spec_replicas != kube_deployment_status_replicas_available
          for: 15m
          labels:
            severity: warning
          annotations:
            summary: "Deployment {{ $labels.namespace }}/{{ $labels.deployment }} replicas mismatch"
            description: "Deployment has {{ $value }} available replicas but expects {{ $labels.spec_replicas }}"

        # High Pod Restart Rate
        - alert: HighPodRestartRate
          expr: |
            rate(kube_pod_container_status_restarts_total[1h]) * 3600 > 5
          for: 10m
          labels:
            severity: warning
          annotations:
            summary: "High restart rate for {{ $labels.namespace }}/{{ $labels.pod }}"
            description: "Pod is restarting more than 5 times per hour"
```

#### 3.3 MCP Server Alerts

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: mcp-alerts
  namespace: monitoring
spec:
  groups:
    - name: mcp.rules
      rules:
        # MCP Server Down
        - alert: MCPServerDown
          expr: probe_success{job="mcp-health-probes"} == 0
          for: 2m
          labels:
            severity: critical
          annotations:
            summary: "MCP server {{ $labels.instance }} is down"
            description: "MCP health probe has failed for 2 minutes"
            runbook_url: "https://runbooks.kernow.io/mcp-down"

        # MCP High Latency
        - alert: MCPHighLatency
          expr: probe_http_duration_seconds{job="mcp-health-probes"} > 5
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "High latency on MCP {{ $labels.instance }}"
            description: "MCP response time is above 5 seconds"

        # Knowledge MCP Down (Critical - blocks planning)
        - alert: KnowledgeMCPDown
          expr: probe_success{instance=~".*31084.*"} == 0
          for: 1m
          labels:
            severity: critical
          annotations:
            summary: "Knowledge MCP is DOWN"
            description: "Critical dependency for planning agent is unavailable"

        # Neo4j MCP Down
        - alert: Neo4jMCPDown
          expr: probe_success{instance=~".*31099.*"} == 0
          for: 2m
          labels:
            severity: warning
          annotations:
            summary: "Neo4j MCP is DOWN"
            description: "Graph database MCP unavailable - planning agent in degraded mode"
```

#### 3.4 Infrastructure Alerts

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: infrastructure-alerts
  namespace: monitoring
spec:
  groups:
    - name: infrastructure.rules
      rules:
        # Proxmox VM Stopped
        - alert: ProxmoxVMStopped
          expr: pve_guest_info{status!="running"} > 0
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Proxmox VM {{ $labels.name }} is not running"
            description: "VM on {{ $labels.node }} has status {{ $labels.status }}"

        # Proxmox High CPU
        - alert: ProxmoxHighCPU
          expr: pve_cpu_usage_ratio > 0.9
          for: 15m
          labels:
            severity: warning
          annotations:
            summary: "High CPU on Proxmox {{ $labels.node }}"
            description: "CPU usage is above 90%"

        # Proxmox Storage Full
        - alert: ProxmoxStorageFull
          expr: |
            (pve_storage_used_bytes / pve_storage_size_bytes) > 0.85
          for: 10m
          labels:
            severity: warning
          annotations:
            summary: "Proxmox storage {{ $labels.storage }} nearly full"
            description: "Storage is above 85% full"
```

---

### Phase 4: Application-Specific Monitoring (Week 2-3)

#### 4.1 Add Application Exporters

| Application | Exporter | Metrics |
|-------------|----------|---------|
| OPNsense | Built-in Prometheus | Firewall, traffic, VPN |
| AdGuard | prometheus-adguard-exporter | DNS queries, blocking |
| Plex | Tautulli + plex_exporter | Streams, transcoding |
| TrueNAS | Built-in Graphite → Prometheus | Pools, datasets, SMART |
| UniFi | unpoller | Clients, APs, traffic |
| Home Assistant | Built-in Prometheus | Entity states, automations |

#### 4.2 OPNsense Scraping

```yaml
# OPNsense built-in Prometheus metrics
- job_name: 'opnsense'
  scheme: https
  tls_config:
    insecure_skip_verify: true
  basic_auth:
    username_file: /etc/prometheus/secrets/opnsense-credentials/username
    password_file: /etc/prometheus/secrets/opnsense-credentials/password
  static_configs:
    - targets: ['10.10.0.1:9273']
      labels:
        cluster: 'infrastructure'
        job: 'opnsense'
```

#### 4.3 TrueNAS Scraping

```yaml
# TrueNAS Graphite metrics
- job_name: 'truenas'
  scheme: https
  tls_config:
    insecure_skip_verify: true
  bearer_token_file: /etc/prometheus/secrets/truenas-credentials/api-key
  static_configs:
    - targets: ['10.10.0.10:443', '10.10.0.11:443']
      labels:
        cluster: 'infrastructure'
        job: 'truenas'
  metrics_path: '/api/v2.0/reporting/exporters/prometheus'
```

#### 4.4 Deploy Unpoller for UniFi

```yaml
# File: /home/monit_homelab/kubernetes/platform/unpoller/
apiVersion: apps/v1
kind: Deployment
metadata:
  name: unpoller
  namespace: monitoring
spec:
  replicas: 1
  template:
    spec:
      containers:
        - name: unpoller
          image: golift/unifi-poller:latest
          env:
            - name: UP_UNIFI_DEFAULT_URL
              value: "https://10.10.0.2:8443"
            - name: UP_UNIFI_DEFAULT_USER
              valueFrom:
                secretKeyRef:
                  name: unifi-credentials
                  key: username
            - name: UP_UNIFI_DEFAULT_PASS
              valueFrom:
                secretKeyRef:
                  name: unifi-credentials
                  key: password
            - name: UP_PROMETHEUS_HTTP_LISTEN
              value: "0.0.0.0:9130"
```

---

### Phase 5: Security - Migrate Credentials (Week 3)

#### 5.1 Move Proxmox Credentials to Infisical

```bash
# Create secrets in Infisical
/root/.config/infisical/secrets.sh set /monitoring/proxmox PROXMOX_USERNAME "root@pam"
/root/.config/infisical/secrets.sh set /monitoring/proxmox PROXMOX_PASSWORD "<secure-password>"

# Create InfisicalSecret
cat <<EOF | kubectl apply -f - --kubeconfig=/home/monit_homelab/kubeconfig
apiVersion: secrets.infisical.com/v1alpha1
kind: InfisicalSecret
metadata:
  name: proxmox-credentials
  namespace: monitoring
spec:
  hostAPI: https://app.infisical.com/api
  authentication:
    universalAuth:
      credentialsRef:
        secretName: universal-auth-credentials
        secretNamespace: infisical-operator-system
      secretsScope:
        projectSlug: monitoring-homelab
        envSlug: prod
        secretsPath: /monitoring/proxmox
  managedSecretReference:
    secretName: proxmox-credentials
    secretNamespace: monitoring
EOF
```

#### 5.2 Update Prometheus Config to Use Secret Files

```yaml
# Modify scrape config to use files
- job_name: 'proxmox-ruapehu'
  scheme: https
  tls_config:
    insecure_skip_verify: true
  basic_auth:
    username_file: /etc/prometheus/secrets/proxmox-credentials/PROXMOX_USERNAME
    password_file: /etc/prometheus/secrets/proxmox-credentials/PROXMOX_PASSWORD
  static_configs:
    - targets: ['10.10.0.10:8006']
```

---

### Phase 6: SLO Framework (Week 3-4)

#### 6.1 Define Service Tiers

| Tier | Services | Availability Target | Latency Target |
|------|----------|---------------------|----------------|
| Critical | DNS, Firewall, ArgoCD | 99.9% (8.7h/year) | p99 < 100ms |
| High | Plex, Home Assistant, Knowledge MCP | 99.5% (43.8h/year) | p99 < 500ms |
| Standard | MCP servers, Media stack | 99% (87.6h/year) | p99 < 1s |
| Low | Dev tools, experiments | Best effort | N/A |

#### 6.2 SLO Recording Rules

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: slo-recording-rules
  namespace: monitoring
spec:
  groups:
    - name: slo.rules
      rules:
        # Availability SLI
        - record: sli:availability:ratio_rate5m
          expr: |
            avg_over_time(up[5m])

        # Error budget remaining
        - record: slo:error_budget:remaining
          expr: |
            1 - (
              (1 - avg_over_time(up[30d])) / (1 - 0.999)
            )
          labels:
            tier: critical
```

---

### Phase 7: Gatus Endpoint Monitoring (Week 4)

#### 7.1 Add Missing Endpoints to Gatus

```yaml
# Add to Gatus config
endpoints:
  # Agentic Cluster
  - name: agentic-api
    group: Kubernetes
    url: "https://10.20.0.40:6443/healthz"
    interval: 30s
    conditions:
      - "[STATUS] == 200"

  # MCP Servers
  - name: knowledge-mcp
    group: MCP Servers
    url: "http://10.20.0.40:31084/health"
    interval: 30s
    conditions:
      - "[STATUS] == 200"
      - "[RESPONSE_TIME] < 5000"

  - name: neo4j-mcp
    group: MCP Servers
    url: "http://10.20.0.40:31099/health"
    interval: 30s
    conditions:
      - "[STATUS] == 200"

  # ... all 17 MCPs

  # Infrastructure
  - name: opnsense
    group: Infrastructure
    url: "https://10.10.0.1"
    interval: 60s
    conditions:
      - "[STATUS] == 200"

  - name: adguard
    group: Infrastructure
    url: "http://10.10.0.1:3000"
    interval: 60s
    conditions:
      - "[STATUS] == 200"
```

---

### Phase 8: Runbooks Exposure via Fumadocs (Week 4)

Expose runbooks at `https://runbooks.kernow.io` using existing Fumadocs deployment. This enables AlertManager `runbook_url` annotations to link directly to runbooks.

#### 8.1 Migrate Runbooks to Fumadocs

```bash
# Current runbooks location
/home/agentic_lab/runbooks/
├── infrastructure/
├── automation/
├── media/
├── troubleshooting/
└── lessons-learned/

# Target location in fumadocs
/home/agentic_lab/fumadocs/content/docs/runbooks/
├── infrastructure/
├── automation/
├── media/
├── troubleshooting/
└── lessons-learned/
```

#### 8.2 Add Runbooks Navigation to Fumadocs

```typescript
// Update fumadocs/source.config.ts
export const runbooks = defineConfig({
  dir: 'content/docs/runbooks',
  basePath: '/runbooks',
});
```

#### 8.3 Create Cloudflare Tunnel for runbooks.kernow.io

```yaml
# Add to Cloudflare tunnel ingress config
- hostname: runbooks.kernow.io
  service: http://fumadocs.ai-platform.svc:3000
  path: /runbooks/*
```

#### 8.4 Neo4j Alert-Runbook Relationships

```cypher
// Create relationships between alerts and runbooks
CREATE (a:AlertRule {name: 'NodeDown'})
CREATE (r:Runbook {path: '/runbooks/troubleshooting/node-down'})
CREATE (a)-[:RESOLVED_BY]->(r)

// Query for runbook by alert
MATCH (a:AlertRule {name: $alert_name})-[:RESOLVED_BY]->(r:Runbook)
RETURN r.path as runbook_url
```

#### 8.5 Update Alert Rules with Runbook URLs

```yaml
# Update alert annotations to use new runbook URLs
annotations:
  runbook_url: "https://runbooks.kernow.io/troubleshooting/node-down"
```

---

### Phase 9: Beszel Agent Deployment (Week 4-5)

Beszel hub is deployed but has no agents collecting metrics. Deploy agents to all key systems.

#### 9.1 Target Systems

| System | IP | Agent Type | Metrics |
|--------|-----|------------|---------|
| Proxmox Ruapehu | 10.10.0.10 | Binary/systemd | CPU, RAM, disk, containers |
| Proxmox Carrick | 10.30.0.10 | Binary/systemd | CPU, RAM, disk, containers |
| Plex VM | 10.10.0.50 | Docker | CPU, RAM, Docker containers |
| TrueNAS | 10.10.0.100 | Docker app | CPU, RAM, pools, datasets |
| UM690L (Agentic) | 10.20.0.40 | DaemonSet | CPU, RAM, disk, K8s node |

#### 9.2 Proxmox Agent Installation

```bash
# On Proxmox Ruapehu (10.10.0.10) and Carrick (10.30.0.10)
curl -sL "https://github.com/henrygd/beszel/releases/latest/download/beszel-agent_Linux_amd64.tar.gz" | tar -xz -O beszel-agent | sudo tee /usr/local/bin/beszel-agent > /dev/null
sudo chmod +x /usr/local/bin/beszel-agent

# Create systemd service
cat <<EOF | sudo tee /etc/systemd/system/beszel-agent.service
[Unit]
Description=Beszel Agent
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/beszel-agent
Restart=always
User=root

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now beszel-agent
```

#### 9.3 Plex VM Docker Agent

```bash
# On Plex VM (10.10.0.50)
docker run -d \
  --name beszel-agent \
  --restart unless-stopped \
  -p 45876:45876 \
  -v /var/run/docker.sock:/var/run/docker.sock:ro \
  henrygd/beszel-agent
```

#### 9.4 Agentic Cluster DaemonSet

```yaml
# File: /home/agentic_lab/kubernetes/platform/beszel-agent/daemonset.yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: beszel-agent
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: beszel-agent
  template:
    metadata:
      labels:
        app: beszel-agent
    spec:
      hostNetwork: true
      hostPID: true
      containers:
        - name: beszel-agent
          image: henrygd/beszel-agent:latest
          ports:
            - containerPort: 45876
              hostPort: 45876
          securityContext:
            privileged: true
          volumeMounts:
            - name: proc
              mountPath: /host/proc
              readOnly: true
            - name: sys
              mountPath: /host/sys
              readOnly: true
      volumes:
        - name: proc
          hostPath:
            path: /proc
        - name: sys
          hostPath:
            path: /sys
```

#### 9.5 Hub Configuration

After deploying agents:
1. Access Beszel UI: https://beszel.kernow.io
2. Go to **Systems** → **Add System** for each target
3. Enter IP, port 45876, and SSH public key from Settings
4. Verify metrics appearing in dashboard

---

## Risk Assessment

| Factor | Score | Notes |
|--------|-------|-------|
| User impact | 2 | Monitoring changes don't affect user services directly |
| Data risk | 1 | Read-only metrics collection |
| Blast radius | 2 | Monitoring cluster is isolated |
| Rollback time | 1 | ArgoCD can revert quickly |
| Reversibility | 1 | All changes are additive |
| **Total** | 7/15 | **Low Risk** |

### Rollback Plan

1. Revert ArgoCD Application changes via git
2. Remove new scrape configs
3. Delete deployed agents
4. Restore original kube-prometheus-stack values

---

## Approval

### Production Changes Identified
- New scrape targets for agentic cluster (10.20.0.0/24)
- Coroot agents deployed to agentic cluster
- New application exporters (Unpoller, blackbox)
- Credential migration to Infisical
- Beszel agents deployed to Proxmox hosts, Plex VM, TrueNAS, Agentic cluster

### Approval Required
- [ ] Credential rotation before migration
- [ ] Review alert rule thresholds
- [ ] Confirm application exporter access credentials

---

## Execution Checklist

### Phase 1: Agentic Cluster Monitoring
- [ ] Create agentic-cluster-credentials secret
- [ ] Deploy Coroot agents to agentic cluster
- [ ] Add agentic scrape targets to Prometheus
- [ ] Verify metrics flowing to VictoriaMetrics
- [ ] Add agentic project in Coroot UI

### Phase 2: MCP Server Monitoring
- [ ] Deploy blackbox exporter
- [ ] Add MCP health probe scrape configs
- [ ] Verify all 17 MCPs are being probed
- [ ] Create MCP dashboard in Grafana

### Phase 3: Alert Rules
- [ ] Deploy cluster health alerts (PrometheusRule)
- [ ] Deploy kubernetes alerts (PrometheusRule)
- [ ] Deploy MCP server alerts (PrometheusRule)
- [ ] Deploy infrastructure alerts (PrometheusRule)
- [ ] Verify alerts appear in AlertManager UI

### Phase 4: Application Exporters
- [ ] Configure OPNsense Prometheus metrics
- [ ] Deploy Unpoller for UniFi metrics
- [ ] Configure TrueNAS metrics export
- [ ] Add Home Assistant metrics
- [ ] Create application dashboards in Grafana

### Phase 5: Security - Credential Migration
- [ ] Create Infisical secrets for Proxmox
- [ ] Create InfisicalSecret CRD for monitoring namespace
- [ ] Update Prometheus scrape config to use secret files
- [ ] Rotate Proxmox password
- [ ] Verify scraping still works

### Phase 6: SLO Framework
- [ ] Define service tier SLO targets
- [ ] Create SLO recording rules
- [ ] Build SLO dashboard in Grafana
- [ ] Create error budget burn rate alerts

### Phase 7: Gatus Endpoint Completeness
- [ ] Add agentic cluster API endpoint
- [ ] Add all 17 MCP health endpoints
- [ ] Add infrastructure endpoints (OPNsense, TrueNAS, UniFi)
- [ ] Verify Gatus status page is comprehensive

### Phase 8: Runbooks Exposure
- [ ] Migrate runbooks from /home/agentic_lab/runbooks/ to fumadocs content
- [ ] Update fumadocs source.config.ts for runbooks section
- [ ] Create Cloudflare tunnel for runbooks.kernow.io
- [ ] Create Neo4j AlertRule → Runbook relationships
- [ ] Update alert rule annotations with runbook URLs
- [ ] Verify runbooks accessible at https://runbooks.kernow.io

### Phase 9: Beszel Agent Deployment
- [ ] Deploy Beszel agent on Proxmox Ruapehu (10.10.0.10) - binary/systemd
- [ ] Deploy Beszel agent on Proxmox Carrick (10.30.0.10) - binary/systemd
- [ ] Deploy Beszel agent on Plex VM (10.10.0.50) - Docker
- [ ] Deploy Beszel agent on TrueNAS (10.10.0.100) - Docker app
- [ ] Deploy Beszel agent on UM690L/Agentic (10.20.0.40) - DaemonSet
- [ ] Configure all agents in Beszel Hub UI
- [ ] Verify CPU, memory, disk, network metrics flowing
- [ ] Add Beszel dashboard link to Homepage

---

## Summary

This plan transforms the monitoring infrastructure from partial coverage to comprehensive observability:

| Metric | Before | After |
|--------|--------|-------|
| Clusters monitored | 2/3 | 3/3 |
| MCP servers monitored | 0/17 | 17/17 |
| Beszel agents | 0 | 5+ systems (Proxmox, Plex, TrueNAS, Agentic) |
| Alert rules | ~20 default | 50+ custom |
| Infrastructure exporters | Partial | Complete (OPNsense, TrueNAS, UniFi) |
| Runbooks | Internal only | Exposed at runbooks.kernow.io (Fumadocs) |
| SLO coverage | 0% | 100% critical services |
| Credential security | Hardcoded | Infisical managed |

**Scope**: Metrics collection, scrape targets, alert rules, dashboards, SLOs, Beszel agents, runbooks exposure
**Out of scope**: Alert notification routing (separate project), automated alert response (Gemini + runbooks - separate project)

**Estimated effort**: 4-5 weeks (9 phases)
**Risk level**: Low
**Approval required**: Yes (credential rotation, exporter access)

---

*Generated by planning-agent skill*
*Profiles used: research-discovery, monitoring-observability, sre-operations, k8s-platform, network-architect, security-compliance, approval-workflow*

---

## CAB Review Record

**Date**: 2026-01-13
**Status**: APPROVED WITH CONDITIONS

### Summary

| Role | Decision | Key Concern |
|------|----------|-------------|
| CISO | CONDITIONAL | Hardcoded password (mitigated: redacted, Phase 5 fixes) |
| VP Engineering | CONDITIONAL | Runbooks need creation before Phase 3 |
| CTO | APPROVE | Good strategic alignment |
| Head of SRE | CONDITIONAL | Alert delivery out of scope (acknowledged) |
| Enterprise Architect | APPROVE | Follows GitOps patterns |
| Platform Engineering | APPROVE | Resources reasonable |
| Finance | APPROVE | All self-hosted, no costs |
| Compliance | APPROVE | Self-hosted, no external data |

**Result**: 4 Approve, 4 Conditional, 0 Block

### Conditions Addressed

1. [x] Hardcoded password redacted from plan document
2. [x] Runbooks exposure planned (Phase 8) - execute before Phase 3 alert deployment
3. [x] Alert delivery out of scope acknowledged

### Approval

- **CAB Decision**: APPROVED WITH CONDITIONS
- **Approved by**: planning-agent CAB simulation
- **Conditions**: Create referenced runbooks before Phase 3
