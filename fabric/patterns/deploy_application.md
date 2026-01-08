# Deploy Application Pattern

Deploy a new application following GitOps principles.

## Prerequisites
- Application manifests in git repository
- ArgoCD Application definition
- Required secrets in Infisical

## Deployment Steps

1. **Validate manifests**
   - Check YAML syntax
   - Verify resource limits are set
   - Confirm Infisical secrets are configured

2. **Create necessary secrets in Infisical**
   - Use `/agentic-platform/<app-name>/` path
   - Store all sensitive values

3. **Create Kubernetes manifests**
   - Deployment/StatefulSet
   - Service
   - InfisicalSecret CRD
   - Ingress (if external access needed)

4. **Create ArgoCD Application**
   - Set appropriate sync-wave
   - Enable auto-sync with prune and self-heal

5. **Commit and push**
   - All changes via git
   - Never kubectl apply directly

## Important Rules
- NO hardcoded secrets
- ALWAYS use InfisicalSecret CRDs
- Follow dual-ingress pattern for external access
- Set resource requests and limits

## Output Format
```json
{
  "files_created": ["path1", "path2"],
  "secrets_stored": ["secret1", "secret2"],
  "argocd_app": "app-name",
  "next_steps": ["commit", "push", "verify sync"]
}
```
