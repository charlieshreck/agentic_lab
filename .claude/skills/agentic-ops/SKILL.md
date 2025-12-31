# Agentic Operations Skill

This skill assists with the Agentic AI Platform infrastructure and application management.

## Context

**Infrastructure**: Talos cluster on UM690L (10.20.0.109)
**Network**: 10.20.0.0/24 (isolated from prod/monitoring)
**Stack**: Ollama + Qdrant + LangGraph + Telegram + MCP servers
**Purpose**: Cyclical learning AI agent for homelab management

## Common Operations

### Infrastructure
- Talos OS management (talosctl)
- Kubernetes operations (kubectl)
- Terraform infrastructure changes
- ArgoCD application sync

### AI Platform
- Ollama model management
- Qdrant collection operations
- LangGraph state inspection
- MCP server debugging
- Telegram bot management

### Monitoring
- Check inference metrics
- Analyze learning patterns
- Review runbook success rates
- Audit agent decisions

## Architecture Notes

- **Hybrid Inference**: Local Ollama (qwen2.5:7b, nomic-embed) + Cloud (Gemini, Claude)
- **PII Detection**: Presidio + GLiNER before cloud escalation
- **Learning**: Qdrant vector DB with runbooks, decisions, documentation
- **Human-in-the-Loop**: Telegram Forum with inline keyboard approvals
- **Progressive Autonomy**: Runbooks graduate from manual → prompted → standard

## Related Repositories

- `prod_homelab`: Production Talos cluster (10.10.0.0/24)
- `monit_homelab`: Monitoring K3s cluster (10.30.0.0/24)
- `agentic_lab`: This repository - AI platform (10.20.0.0/24)

## Common Queries

### "Check if Ollama is running"
```bash
kubectl get pods -n ai-platform -l app=ollama
kubectl logs -n ai-platform deploy/ollama --tail=50
```

### "List loaded models"
```bash
kubectl exec -n ai-platform deploy/ollama -- \
  curl -s localhost:11434/api/tags | jq '.models[].name'
```

### "Check Qdrant collection sizes"
```bash
kubectl port-forward -n ai-platform svc/qdrant 6333:6333 &
curl -s http://localhost:6333/collections | jq '.result.collections[] | {name: .name, points: .points_count}'
```

### "View recent agent decisions"
```bash
curl -X POST http://localhost:6333/collections/decisions/points/scroll \
  -H "Content-Type: application/json" \
  -d '{"limit": 10, "with_payload": true, "with_vector": false}' | \
  jq '.result.points[] | {timestamp: .payload.timestamp, outcome: .payload.outcome}'
```

### "Check Telegram webhook status"
```bash
kubectl logs -n ai-platform deploy/telegram-service --tail=20 | grep webhook
```

### "Force ArgoCD sync for application"
```bash
argocd app sync <app-name> --prune
kubectl get applications -n argocd
```

### "Talos cluster health"
```bash
export TALOSCONFIG=infrastructure/terraform/talos-cluster/generated/talosconfig
talosctl health --nodes 10.20.0.109
talosctl dashboard --nodes 10.20.0.109
```

### "Get kubeconfig for MCP development"
```bash
export KUBECONFIG=infrastructure/terraform/talos-cluster/generated/kubeconfig
kubectl config view --raw
```

## Debugging Common Issues

### Ollama not responding
```bash
kubectl describe pod -n ai-platform -l app=ollama
kubectl logs -n ai-platform deploy/ollama --tail=100
# Check if models are loaded:
kubectl exec -n ai-platform deploy/ollama -- ls -lh /root/.ollama/models
```

### Qdrant collection not syncing
```bash
kubectl logs -n ai-platform deploy/qdrant --tail=50
kubectl get pvc -n ai-platform | grep qdrant
# Check storage:
kubectl exec -n ai-platform deploy/qdrant -- df -h /qdrant/storage
```

### Telegram webhook not receiving messages
```bash
# Check if webhook is registered:
curl "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
# Check service exposure:
kubectl get svc -n ai-platform telegram-service
kubectl get ingress -n ai-platform telegram-webhook
```

### InfisicalSecret not syncing
```bash
kubectl get infisicalsecrets -A
kubectl describe infisicalsecret <name> -n <namespace>
kubectl logs -n infisical-operator-system deploy/infisical-operator-controller-manager --tail=50
```

## GitOps Reminders

**ALWAYS follow GITOPS-WORKFLOW.md:**
- Commit to git FIRST
- Push to GitHub
- Let ArgoCD sync (or terraform apply)
- NEVER manual kubectl apply
- NEVER manual talosctl patches
- Secrets via Infisical only

## Performance Targets

- **Ollama inference**: <100ms (local qwen2.5:7b)
- **Qdrant search**: <10ms (for 100K vectors)
- **Telegram webhook**: <5min from alert to notification
- **ArgoCD sync**: <3min auto-sync interval

## Learning Metrics

Monitor these in Qdrant:
- Runbook success rates
- Approval vs. ignore ratios
- Cloud escalation frequency
- Automation level distribution (manual/prompted/standard)

## References

- CLAUDE.md - Complete architecture overview
- GITOPS-WORKFLOW.md - Mandatory deployment workflow
- PHASES.md - Implementation timeline
- docs/unified-architecture-updated.md - Detailed system design
