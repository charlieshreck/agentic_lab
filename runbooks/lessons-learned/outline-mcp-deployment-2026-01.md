# Lessons Learned: Outline MCP Deployment (2026-01-19)

## Summary

Deployment of `outline-mcp` to integrate Claude Code with Outline wiki for document and collection management.

## What Went Well

1. **Pre-built Docker Image**: Using `ghcr.io/vortiago/mcp-outline:latest` eliminated need to write/maintain custom server code
2. **Internal Service Communication**: Outline MCP connects to Outline wiki via internal Kubernetes DNS (`http://outline/api`) - no external exposure needed
3. **InfisicalSecret Pattern**: Secrets integration worked smoothly using existing pattern
4. **Streamable HTTP Transport**: MCP server properly configured for Claude Code compatibility

## What Went Wrong

### Issue 1: Repeated NodePort Conflicts

**Problem**: Multiple NodePort allocation failures during deployment:
- First attempt: Used 31103 (already taken by `mcp-config-sync`)
- Second attempt: Used 31105 (already taken by `keep` service)
- Final success: Used 31114

**Root Cause**: No systematic NodePort allocation tracking. Ports were checked in isolation without a comprehensive view.

**Impact**: Extended deployment time, multiple commit/push cycles, ArgoCD sync failures

**Solution Applied**: Used port 31114 after comprehensive check of all services in 311xx range

**Future Prevention**:
1. **ALWAYS** check existing NodePorts comprehensively before allocation:
   ```bash
   kubectl get svc -A -o custom-columns="NAME:.metadata.name,NODEPORT:.spec.ports[*].nodePort" | grep "311"
   ```
2. Keep `/root/.claude-ref/mcp-ports.txt` updated as source of truth
3. Consider extending NodePort range to 311xx for MCP servers (31100-31199)

### Issue 2: ArgoCD Manifest Caching

**Problem**: After fixing NodePort from 31105 to 31114, ArgoCD continued trying to apply old value

**Root Cause**: ArgoCD caches manifests; hard refresh required to pick up changes

**Solution Applied**:
```bash
kubectl annotate application mcp-servers -n argocd argocd.argoproj.io/refresh=hard --overwrite
```

**Future Prevention**: Always force hard refresh after committing manifest changes:
```bash
kubectl annotate application <app> -n argocd argocd.argoproj.io/refresh=hard --overwrite
```

## Architecture Decisions

### Pre-built Image vs ConfigMap Pattern

**Decision**: Use pre-built Docker image (`ghcr.io/vortiago/mcp-outline:latest`) instead of ConfigMap-based deployment

**Rationale**:
- Maintained by community (Vortiago)
- Better collection support including `get_collection_structure()`
- No need to write/maintain Python server code
- Regular updates via container registry

**Trade-offs**:
- Less control over implementation
- Dependency on external maintainer
- May need to fork if customizations required

### Internal vs External API URL

**Decision**: Use internal Kubernetes DNS (`http://outline/api`) for Outline API URL

**Rationale**:
- MCP server and Outline wiki are in same namespace (ai-platform)
- No need for external network traversal
- Faster, more reliable communication
- Security: API key stays within cluster

## Final Configuration

| Component | Value |
|-----------|-------|
| NodePort | 31114 |
| Internal API URL | http://outline/api |
| Container Image | ghcr.io/vortiago/mcp-outline:latest |
| Transport | streamable-http |
| Internal Port | 3000 |
| Infisical Path | /agentic-platform/outline-mcp |
| Secret Key | OUTLINE_API_KEY |

## Files Changed

1. `/home/agentic_lab/kubernetes/applications/mcp-servers/outline-mcp.yaml` - Created
2. `/home/agentic_lab/kubernetes/applications/mcp-servers/infisical-secrets.yaml` - Added InfisicalSecret
3. `/home/agentic_lab/kubernetes/applications/mcp-servers/kustomization.yaml` - Added to resources
4. `/home/.mcp.json` - Added outline MCP endpoint
5. `/root/.claude-ref/mcp-ports.txt` - Added port 31114

## Verification Commands

```bash
# Check pod status
KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig \
  kubectl get pods -n ai-platform -l app=outline-mcp

# Check service
KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig \
  kubectl get svc outline-mcp -n ai-platform

# Health check
curl -s http://10.20.0.40:31114/health

# View logs
KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig \
  kubectl logs -n ai-platform -l app=outline-mcp --tail=50
```

## Available MCP Tools (outline-mcp)

Once session is restarted, these tools become available:
- `list_documents` - List documents in workspace
- `search_documents` - Search for documents by query
- `get_document` - Get document content by ID
- `create_document` - Create new document
- `update_document` - Update existing document
- `list_collections` - List collections
- `get_collection_structure` - Get full collection hierarchy
- `create_collection` - Create new collection

## Tags

`mcp`, `outline`, `wiki`, `documentation`, `nodeport-conflict`, `argocd-caching`
