# Health Check Pattern

Perform a comprehensive health check of the infrastructure.

## Clusters to Check
- **Prod** (10.10.0.0/24): Production workloads
- **Monitoring** (10.30.0.0/24): Observability stack
- **Agentic** (10.20.0.0/24): AI platform

## Checks to Perform

### 1. Kubernetes Health
```bash
kubectl get nodes --context=<context>
kubectl get pods -A --field-selector=status.phase!=Running --context=<context>
kubectl top nodes --context=<context>
```

### 2. Critical Services
- ArgoCD: Check sync status
- Cert-Manager: Check certificate expiry
- Ingress: Check endpoints
- Storage: Check PV/PVC status

### 3. Resource Utilization
- CPU usage across nodes
- Memory pressure
- Disk space on persistent volumes

### 4. Recent Events
- Check for Warning/Error events in last 24h
- Check for pod restarts

## Output Format

```json
{
  "overall_status": "healthy|degraded|critical",
  "clusters": {
    "prod": {"status": "...", "issues": []},
    "monitoring": {"status": "...", "issues": []},
    "agentic": {"status": "...", "issues": []}
  },
  "critical_issues": [],
  "warnings": [],
  "recommendations": []
}
```
