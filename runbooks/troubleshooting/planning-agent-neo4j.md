# Planning Agent Neo4j Troubleshooting

## Overview

This runbook covers troubleshooting issues when the planning-agent skill cannot connect to or query Neo4j.

**Deployment Status**: ✅ Neo4j and neo4j-mcp deployed 2026-01-13

**Key principle**: Neo4j is an **enhancement**, not a hard dependency. If Neo4j is down, the planning agent should fall back to Qdrant-only mode with a warning.

## Quick Diagnosis

### 1. Check Neo4j Health

```bash
# Set kubeconfig for agentic cluster
export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig

# Check Neo4j pod status
kubectl get pods -l app=neo4j -n ai-platform

# Check Neo4j logs
kubectl logs -l app=neo4j -n ai-platform --tail=100

# Port-forward to test directly
kubectl port-forward svc/neo4j 7474:7474 7687:7687 -n ai-platform &

# Test HTTP interface
curl http://localhost:7474

# Test Bolt connection (requires cypher-shell or neo4j-client)
# Alternatively, test via MCP
```

### 2. Check neo4j-mcp Health

```bash
export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig

# Pod status
kubectl get pods -l app=neo4j-mcp -n ai-platform

# Logs
kubectl logs -l app=neo4j-mcp -n ai-platform --tail=100

# Service
kubectl get svc neo4j-mcp -n ai-platform

# Health check via NodePort
curl http://10.20.0.40:31099/health

# Health check via ClusterIP (from within cluster)
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -- \
  curl http://neo4j-mcp.ai-platform.svc.cluster.local:8000/health
```

### 3. Test Neo4j Query via MCP

```bash
# If MCP is accessible via NodePort
curl -X POST http://10.20.0.40:31099/mcp \
  -H "Content-Type: application/json" \
  -d '{"method": "tools/call", "params": {"name": "query_graph", "arguments": {"cypher": "RETURN 1 as ok"}}}'
```

## Common Issues

| Symptom | Likely Cause | Resolution |
|---------|--------------|------------|
| "Neo4j unavailable" warning in plan | Neo4j pod down or restarting | Check pod status, wait for ready |
| Slow queries (>10s) | Large traversal depth or missing indexes | Reduce depth param, add indexes |
| "Incompatible schema" error | Schema version mismatch | Run migration or redeploy neo4j-mcp |
| Empty results for known entities | Data not synced from sources | Trigger graph-sync CronJob manually |
| Connection refused | Network policy blocking, service misconfigured | Check NetworkPolicy, verify service port |
| Authentication failed | Credentials rotated, secret not synced | Check Infisical secret, restart pods |
| "Rate limit exceeded" | >50 queries in planning session | Wait 5 minutes for window reset |

## Resolution Steps

### Force Graph Resync

If entities are missing or stale:

```bash
export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig

# Trigger manual sync job
kubectl create job graph-sync-manual --from=cronjob/graph-sync -n ai-platform

# Watch job completion
kubectl get jobs -n ai-platform -w

# Check logs
kubectl logs job/graph-sync-manual -n ai-platform
```

### Restart neo4j-mcp

If MCP is unhealthy but Neo4j is fine:

```bash
export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig

kubectl rollout restart deployment/neo4j-mcp -n ai-platform
kubectl rollout status deployment/neo4j-mcp -n ai-platform
```

### Restart Neo4j

If Neo4j is unresponsive:

```bash
export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig

# Check if StatefulSet or Deployment
kubectl get statefulset neo4j -n ai-platform || kubectl get deployment neo4j -n ai-platform

# Restart (StatefulSet)
kubectl rollout restart statefulset/neo4j -n ai-platform

# Or restart (Deployment)
kubectl rollout restart deployment/neo4j -n ai-platform

kubectl rollout status statefulset/neo4j -n ai-platform
```

### Neo4j Memory Issues

If Neo4j is OOMKilled:

```bash
export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig

# Check memory usage
kubectl top pod -l app=neo4j -n ai-platform

# Check for OOMKilled
kubectl describe pod -l app=neo4j -n ai-platform | grep -A5 "Last State"

# If OOM, edit resource limits (via GitOps, not kubectl edit!)
# File: /home/agentic_lab/kubernetes/applications/neo4j/neo4j.yaml
# Increase: resources.limits.memory: 6Gi
# Commit, push, ArgoCD syncs
```

### Schema Migration

If "Incompatible schema" error:

```bash
# Check current schema version
curl -X POST http://10.20.0.40:31099/mcp \
  -H "Content-Type: application/json" \
  -d '{"method": "tools/call", "params": {"name": "query_graph", "arguments": {"cypher": "MATCH (s:SchemaVersion) RETURN s.version"}}}'

# If version mismatch, redeploy neo4j-mcp with updated COMPATIBLE_SCHEMA_VERSIONS
# or run migration via neo4j-mcp migrate_schema tool
```

### Credential Rotation

If authentication fails after Infisical rotation:

```bash
export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig

# Check InfisicalSecret
kubectl get infisicalsecret -n ai-platform | grep neo4j

# Check synced secret
kubectl get secret neo4j-credentials -n ai-platform -o yaml

# Force secret refresh
kubectl delete secret neo4j-credentials -n ai-platform
# InfisicalSecret controller will recreate it

# Restart services to pick up new credentials
kubectl rollout restart statefulset/neo4j -n ai-platform
kubectl rollout restart deployment/neo4j-mcp -n ai-platform
```

## Degraded Mode Verification

If Neo4j cannot be fixed immediately, verify the planning agent is running in degraded mode:

1. Run a planning task
2. Check output for warning:
   ```
   ⚠️ **Degraded Mode Active**: Neo4j unavailable. This plan was created
   without relationship context (dependencies, impact analysis).
   Consider re-planning when Neo4j is restored.
   ```
3. Verify Qdrant-only results are being used

## Monitoring

### Prometheus Metrics (via neo4j-mcp)

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `neo4j_mcp_queries_total{status="error"}` | Failed queries | >10/min |
| `neo4j_mcp_query_duration_seconds` | Query latency | p99 > 10s |
| `neo4j_mcp_connection_status` | Neo4j health | 0 for >5 min |

### Coroot Integration

Check Coroot dashboard for:
- Neo4j pod resource usage
- neo4j-mcp error rates
- Network connectivity issues

```bash
# Access Coroot (monit cluster)
# Dashboard: Neo4j / neo4j-mcp service
```

## Escalation

If issues persist after above steps:

1. Check Coroot for detailed Neo4j metrics and anomalies
2. Review neo4j-admin logs for database corruption
3. Consider neo4j-admin dump/restore if corruption suspected
4. For persistent performance issues, review graph size and consider index optimization

## Related Runbooks

- [MCP Servers](../infrastructure/mcp-servers.md) - General MCP troubleshooting
- [DNS Architecture](../infrastructure/dns-architecture.md) - If DNS resolution is the issue

## References

- Plan file: `/root/.claude/plans/nifty-whistling-wirth.md`
- Neo4j plan: `/root/.claude/plans/nifty-coalescing-badger.md`
- Planning agent plan: `/root/.claude/plans/harmonic-cuddling-bird.md`
