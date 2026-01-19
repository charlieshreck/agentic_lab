# Lessons Learned: Outline Wiki Deployment (2026-01-19)

## Summary

Full deployment of Outline wiki to the agentic cluster with GitHub OAuth authentication and external access via Cloudflare Tunnel.

## What Went Well

1. **External Service Bridge Pattern**: Successfully implemented the standard pattern for exposing agentic cluster services externally via prod cluster bridge
2. **Shared PostgreSQL**: Leveraged existing PostgreSQL instance with database init job
3. **Shared Redis**: Used existing ai-platform Redis for session/cache storage
4. **GitHub OAuth**: Integrated successfully after version upgrade
5. **Homepage Integration**: Automatic via ingress annotations

## What Went Wrong

### Issue 1: GitHub OAuth Callback Failure (Initial Version)

**Problem**: Outline v0.81.1 failed to complete GitHub OAuth flow with "invalid_request" error

**Root Cause**: Older Outline version had incompatibility with GitHub OAuth callback handling

**Solution Applied**: Upgraded to Outline v1.3.0:
```yaml
image: outlinewiki/outline:1.3.0  # was 0.81.1
```

**Lesson**: When OAuth fails mysteriously, check if a newer version of the application exists. OAuth provider APIs evolve and older clients may become incompatible.

### Issue 2: Database Connection String Format

**Problem**: Initial deployment used incorrect DATABASE_URL format

**Root Cause**: Environment variable substitution in Kubernetes doesn't work the same as shell

**Solution Applied**: Use multi-env-var approach:
```yaml
env:
  - name: POSTGRES_USER
    valueFrom:
      secretKeyRef:
        name: postgresql-credentials
        key: username
  - name: POSTGRES_PASSWORD
    valueFrom:
      secretKeyRef:
        name: postgresql-credentials
        key: password
  - name: DATABASE_URL
    value: "postgres://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@postgresql:5432/outline"
```

**Lesson**: Kubernetes allows env var references in `value` fields using `$(VAR_NAME)` syntax.

### Issue 3: Redis URL Without Auth

**Problem**: Initially tried to configure Redis with authentication

**Root Cause**: The shared ai-platform Redis doesn't require authentication

**Solution Applied**: Simple Redis URL:
```yaml
- name: REDIS_URL
  value: "redis://redis:6379"
```

**Lesson**: Check existing service configuration before adding authentication where none exists.

## Architecture Decisions

### Decision 1: GitHub OAuth vs Google OIDC

**Choice**: GitHub OAuth (plan originally specified Google OIDC)

**Rationale**:
- Development team already uses GitHub
- Simpler setup than Google OIDC
- Works well for small teams
- Easy to manage access via GitHub org membership

### Decision 2: Local File Storage vs S3

**Choice**: Local file storage with PVC

**Rationale**:
- Simpler deployment
- No external S3 dependency
- 10Gi PVC sufficient for documentation
- Easy backup via snapshot

**Trade-off**: No built-in redundancy. Consider MinIO in future if growth requires.

### Decision 3: Agentic Cluster vs Prod Cluster

**Choice**: Deploy to agentic cluster with external bridge

**Rationale**:
- Documentation closely tied to AI platform development
- Shares infrastructure with other ai-platform services (PostgreSQL, Redis)
- MCP integration easier within same cluster
- External access via established bridge pattern

## Final Architecture

```
Internet
    │
    ▼
Cloudflare Tunnel
    │
    ▼
Prod Cluster (10.10.0.0/24)
├── Ingress (outline-cloudflare)
├── Service (outline-external, ClusterIP)
└── Endpoints (10.20.0.40:31113)
    │
    ▼
Agentic Cluster (10.20.0.0/24)
├── Service (outline, NodePort 31113)
├── Deployment (outline)
│   ├── PostgreSQL → postgresql:5432/outline
│   ├── Redis → redis:6379
│   └── File Storage → PVC (10Gi)
└── MCP Server (outline-mcp, NodePort 31114)
```

## Configuration Summary

### Outline Wiki
| Component | Value |
|-----------|-------|
| Image | outlinewiki/outline:1.3.0 |
| NodePort | 31113 |
| External URL | https://outline.kernow.io |
| Database | postgresql:5432/outline |
| Redis | redis:6379 |
| File Storage | /var/lib/outline/data (10Gi PVC) |
| Auth | GitHub OAuth |

### Outline MCP
| Component | Value |
|-----------|-------|
| Image | ghcr.io/vortiago/mcp-outline:latest |
| NodePort | 31114 |
| API URL | http://outline/api (internal) |
| Transport | streamable-http |

### Secrets (Infisical)
| Path | Keys |
|------|------|
| /agentic-platform/outline | SECRET_KEY, UTILS_SECRET, GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET |
| /agentic-platform/outline-mcp | OUTLINE_API_KEY |

## Files Created/Modified

### Agentic Cluster
```
/home/agentic_lab/kubernetes/applications/outline/
├── kustomization.yaml
├── infisical-secret.yaml
├── db-init-job.yaml
├── deployment.yaml
├── service.yaml
└── ingress.yaml (internal, if needed)

/home/agentic_lab/kubernetes/applications/mcp-servers/
├── outline-mcp.yaml
├── infisical-secrets.yaml (modified)
└── kustomization.yaml (modified)
```

### Prod Cluster (Bridge)
```
/home/prod_homelab/kubernetes/applications/apps/agentic-external/
├── services.yaml (added outline-external)
├── endpoints.yaml (added outline-external)
└── cloudflare-tunnel-ingresses.yaml (added outline-cloudflare)
```

### Configuration Files
```
/home/.mcp.json (added outline MCP)
/root/.claude-ref/mcp-ports.txt (added 31114)
```

## Verification Commands

```bash
# Check Outline wiki
KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig
kubectl get pods -n ai-platform -l app.kubernetes.io/name=outline
kubectl logs -n ai-platform deployment/outline --tail=50
curl -I https://outline.kernow.io

# Check Outline MCP
kubectl get pods -n ai-platform -l app=outline-mcp
curl -s http://10.20.0.40:31114/health

# Check external bridge (prod cluster)
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig
kubectl get svc outline-external -n apps
kubectl get endpoints outline-external -n apps
kubectl get ingress outline-cloudflare -n apps
```

## Post-Deployment Tasks

1. First user to login becomes admin
2. Create initial workspace structure
3. Invite team members via GitHub
4. Create API token for MCP server
5. Restart Claude Code to enable MCP

## Related Runbooks

- [MCP Deployment Pattern](../automation/mcp-deployment.md)
- [New App Agentic External](../infrastructure/new-app-agentic-external.md)
- [Outline MCP Lessons Learned](./outline-mcp-deployment-2026-01.md)

## Tags

`outline`, `wiki`, `knowledge-base`, `github-oauth`, `cloudflare-tunnel`, `agentic-cluster`, `mcp`
