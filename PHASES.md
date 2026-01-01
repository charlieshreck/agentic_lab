# Implementation Phases

**Cyclical Learning Agentic AI Platform - Deployment Roadmap**

---

## Overview

This document outlines the phased implementation approach for the Agentic AI Platform. Each phase builds on the previous, with clear success criteria and rollback points.

**Timeline**: 8 phases over ~3 months (flexible based on learning and iteration)

**Philosophy**: Start simple, validate early, add complexity incrementally.

---

## Phase 1: Talos Infrastructure (Week 1)

**Goal**: Provision and bootstrap Talos cluster

### Tasks

- [ ] Download Talos ISO and flash to USB drive (see BARE_METAL_INSTALL.md)
- [ ] Boot UM690L from USB into Talos maintenance mode
- [ ] Configure Terraform variables (`terraform.tfvars`) with network and disk settings
- [ ] Run `terraform plan` and review
- [ ] Run `terraform apply` to provision bare metal Talos cluster
- [ ] Remove USB drive and reboot into installed system
- [ ] Verify kubeconfig access
- [ ] Test basic kubectl commands

### Success Criteria

```bash
# All commands succeed:
kubectl get nodes
# NAME         STATUS   ROLES           AGE   VERSION
# agentic-01   Ready    control-plane   5m    v1.31.1

kubectl get pods -A
# System pods running (apiserver, controller-manager, scheduler, etc.)

talosctl health --nodes 10.20.0.40
# All health checks pass
```

### Rollback

```bash
cd infrastructure/terraform/talos-cluster
terraform destroy
```

---

## Phase 2: Core Services (Week 1-2)

**Goal**: Deploy foundational platform services via ArgoCD

### Tasks

- [ ] Bootstrap ArgoCD (`kubectl apply -k kubernetes/bootstrap/`)
- [ ] Access ArgoCD UI and verify
- [ ] Deploy Infisical Operator for secrets management
- [ ] Create Infisical universal auth credentials
- [ ] Deploy cert-manager for certificate automation
- [ ] Configure storage provisioner (local-path)
- [ ] Test InfisicalSecret → Kubernetes Secret workflow

### Success Criteria

```bash
# ArgoCD accessible and healthy
kubectl -n argocd get applications
# All platform apps synced

# Infisical operator running
kubectl -n infisical-operator-system get pods

# Test secret sync
kubectl apply -f test-infisical-secret.yaml
kubectl get secret test-secret  # Should exist

# cert-manager issuing certificates
kubectl get certificaterequests -A
```

### Rollback

```bash
# ArgoCD manages everything, rollback via git:
git revert <commit-hash>
git push
# ArgoCD auto-syncs the revert
```

---

## Phase 3: Inference Layer (Week 2-3)

**Goal**: Deploy local LLM infrastructure

### Tasks

- [ ] Deploy Ollama StatefulSet with PVC
- [ ] Pull models: `qwen2.5:7b`, `nomic-embed-text-v1.5`
- [ ] Test Ollama API: `curl http://ollama:11434/api/tags`
- [ ] Deploy LiteLLM with local model configuration
- [ ] Test LiteLLM routing
- [ ] Configure Gemini API key in Infisical (optional)
- [ ] Configure Claude API key in Infisical (optional)
- [ ] Test hybrid routing (local → cloud escalation)

### Success Criteria

```bash
# Ollama healthy with models loaded
kubectl exec -n ai-platform deploy/ollama -- \
  curl -s localhost:11434/api/tags | jq '.models[].name'
# qwen2.5:7b
# nomic-embed-text-v1.5

# LiteLLM routing works
kubectl port-forward -n ai-platform svc/litellm 4000:4000 &
curl http://localhost:4000/v1/models
# Returns list of available models (local + cloud)

# Test inference
curl http://localhost:4000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "local/qwen2.5:7b", "messages": [{"role": "user", "content": "Hello"}]}'
# Returns response
```

### Rollback

Via ArgoCD (git revert) or:
```bash
kubectl delete -k kubernetes/applications/ollama/
kubectl delete -k kubernetes/applications/litellm/
```

---

## Phase 4: Vector Knowledge Base (Week 3-4)

**Goal**: Deploy Qdrant and establish RAG pipeline

### Tasks

- [ ] Deploy Qdrant StatefulSet with persistent volume
- [ ] Create collection schemas (runbooks, decisions, documentation)
- [ ] Deploy embedding service (nomic-embed)
- [ ] Build ingestion pipeline for documentation
- [ ] Ingest initial docs from `docs/` directory
- [ ] Test semantic search
- [ ] Deploy Redis for caching
- [ ] Deploy PostgreSQL for LangGraph state

### Success Criteria

```bash
# Qdrant accessible
kubectl port-forward -n ai-platform svc/qdrant 6333:6333 &
curl http://localhost:6333/collections
# Returns list of collections

# Collections created
curl http://localhost:6333/collections/runbooks
curl http://localhost:6333/collections/decisions
curl http://localhost:6333/collections/documentation

# Test search
curl -X POST http://localhost:6333/collections/documentation/points/search \
  -H "Content-Type: application/json" \
  -d '{"vector": [...], "limit": 5}'
# Returns semantically similar documents

# PostgreSQL accepting connections
kubectl exec -n ai-platform deploy/postgres -- psql -U postgres -c '\l'
```

### Rollback

```bash
# Via ArgoCD or:
kubectl delete -k kubernetes/applications/qdrant/
kubectl delete pvc qdrant-data  # WARNING: Deletes vector data
```

---

## Phase 5: MCP Servers (Week 4-5)

**Goal**: Build and deploy custom tool integrations

### Tasks

- [ ] Set up MCP development environment
- [ ] Build `infrastructure-mcp` (kubectl, talosctl tools)
- [ ] Build `home-assistant-mcp` (Home Assistant API)
- [ ] Build `arr-suite-mcp` (Sonarr, Radarr, Prowlarr)
- [ ] Build `knowledge-mcp` (Qdrant search wrapper)
- [ ] Deploy MCP servers to cluster
- [ ] Configure secrets in Infisical for each MCP server
- [ ] Test tool execution

### Success Criteria

```bash
# All MCP servers running
kubectl get pods -n ai-platform -l component=mcp
# infrastructure-mcp, home-assistant-mcp, arr-suite-mcp, knowledge-mcp all ready

# Test MCP endpoints
curl http://infrastructure-mcp:8001/tools
# Returns list of available tools (kubectl, talosctl, etc.)

curl http://home-assistant-mcp:8002/tools
# Returns Home Assistant tools (lights, climate, etc.)

# Execute test tool call
curl -X POST http://infrastructure-mcp:8001/execute \
  -d '{"tool": "kubectl_get_nodes", "args": {}}'
# Returns node list
```

### Rollback

```bash
kubectl delete -k kubernetes/applications/mcp-servers/
```

---

## Phase 6: Orchestration & Human-in-the-Loop (Week 5-6)

**Goal**: Deploy LangGraph orchestrator and Telegram interface

### Tasks

- [ ] Create Telegram bot via @BotFather
- [ ] Create Telegram Forum Supergroup
- [ ] Add bot as admin with `can_manage_topics` permission
- [ ] Store bot token in Infisical `/agentic-platform/telegram`
- [ ] Deploy LangGraph orchestrator
- [ ] Deploy Telegram service
- [ ] Initialize standing topics (Critical, Arr Suite, Infrastructure, etc.)
- [ ] Register webhook URL with Telegram API
- [ ] Test approval workflow end-to-end

### Success Criteria

```bash
# LangGraph orchestrator healthy
kubectl get pods -n ai-platform -l app=langgraph

# Telegram service receiving webhooks
kubectl logs -n ai-platform deploy/telegram-service --tail=20
# Shows webhook POST requests from Telegram

# Test approval flow:
# 1. Trigger test alert
# 2. Verify message appears in correct Telegram Forum topic
# 3. Click inline keyboard button
# 4. Verify callback processed
# 5. Check decision logged in Qdrant

# Verify topic creation
# Open Telegram Forum, confirm standing topics exist:
# - 🔴 Critical Alerts
# - 🟡 Arr Suite
# - 🔵 Infrastructure
# - 🏠 Home Assistant
# - 📊 Weekly Reports
# - ✅ Resolved
```

### Rollback

```bash
kubectl delete -k kubernetes/applications/langgraph/
kubectl delete -k kubernetes/applications/telegram-service/

# Delete webhook registration
curl -X POST "https://api.telegram.org/bot${BOT_TOKEN}/deleteWebhook"
```

---

## Phase 7: Go Live - Verbose Mode (Week 6-7)

**Goal**: Enable live operations in maximum verbosity mode

### Tasks

- [ ] Enable detection sources (Coroot, Prometheus, Renovate)
- [ ] Configure alert routing to LangGraph
- [ ] Set inference mode to `LOCAL_FIRST`
- [ ] Set approval policy to `VERBOSE` (ask for everything)
- [ ] Monitor all notifications for 1 week
- [ ] Create initial runbooks from approved actions
- [ ] Tune false positive filters
- [ ] Document patterns in knowledge base

### Success Criteria

```bash
# Alerts flowing end-to-end:
# 1. Prometheus alert fires → AlertManager webhook
# 2. LangGraph receives alert
# 3. Qdrant search for similar runbooks
# 4. Telegram notification sent to appropriate topic
# 5. Human approves/ignores
# 6. Decision logged to Qdrant
# 7. Runbook updated with outcome

# Metrics:
# - No missed alerts
# - All notifications in correct topics
# - <5 min latency from alert to notification
# - 100% of decisions logged to Qdrant
```

### Weekly Report (Telegram)

```
📊 Week 1 Verbose Mode Report

Alerts Processed: 47
├── Approved: 23
├── Ignored: 18
└── Modified: 6

Top Alert Sources:
├── Radarr OOM: 8 occurrences
├── Prowlarr timeout: 5 occurrences
└── Disk space warning: 4 occurrences

Runbooks Created: 3
├── radarr-memory-increase
├── prowlarr-restart
└── nfs-mount-recovery

Confidence Scores:
├── Local inference avg: 0.78
├── Cloud escalations: 5 (10.6%)
└── PII detections: 0
```

### Rollback

```bash
# Disable alert routing
kubectl scale deployment prometheus-alertmanager-webhook --replicas=0

# Continue monitoring manually while investigating issues
```

---

## Phase 8: Progressive Autonomy (Month 2+)

**Goal**: Graduate runbooks from manual → prompted → standard

### Tasks

- [ ] Track approval patterns in Qdrant
- [ ] Identify high-success runbooks (>95% success rate, 5+ approvals)
- [ ] Promote first runbook to `STANDARD` automation level
- [ ] Monitor automated execution for 1 week
- [ ] Gradually promote more runbooks based on reliability
- [ ] Implement confidence thresholds
- [ ] Configure weekly digests
- [ ] Set up quarterly trust reviews

### Success Criteria

```bash
# Automation levels tracked:
curl http://knowledge-mcp:8001/runbooks/stats
# {
#   "manual": 5,      # Still require approval every time
#   "prompted": 12,   # High confidence, ask first
#   "standard": 3     # Fully automated, notify after
# }

# Example standard runbook:
# ID: runbook-mem-001
# Pattern: ".*OOM.*" in namespace "apps"
# Solution: Increase memory by 1GB
# Success rate: 97.2% (35/36 executions)
# Automation level: STANDARD
# Last failed: 2024-01-15 (investigated, pattern updated)

# Weekly metrics show:
# - Auto-executed actions: 8
# - Human approvals: 12
# - Ignored alerts: 3
# - New runbooks: 1
```

### Quarterly Trust Review

Review automation decisions, success rates, and adjust policies:

1. **Audit**: Review all automated actions from past quarter
2. **Analyze**: Identify any failures or near-misses
3. **Adjust**: Update confidence thresholds, demote unreliable runbooks
4. **Expand**: Promote new high-performing patterns to standard

---

## Ongoing Maintenance

### Daily

- Monitor Telegram notifications
- Approve/ignore agent proposals
- Review automated actions (standard runbooks)

### Weekly

- Review weekly digest in Telegram 📊 topic
- Check knowledge base growth
- Validate inference costs (cloud API usage)
- Review new runbooks for promotion

### Monthly

- Backup Qdrant snapshots
- Review automation levels and success rates
- Update documentation
- Plan new MCP server integrations

### Quarterly

- Trust review (audit automated decisions)
- Infrastructure updates (Talos, Kubernetes versions)
- Model updates (new Ollama models, cloud model changes)
- Architecture review and optimization

---

## Success Metrics

### Phase 1-2 (Infrastructure)

- ✅ Cluster provisioned and accessible
- ✅ ArgoCD deploying applications
- ✅ Secrets management working

### Phase 3-5 (AI Platform)

- ✅ Local inference <100ms latency
- ✅ Cloud escalation <500ms latency
- ✅ Vector search <10ms for 100K vectors
- ✅ MCP tools executing correctly

### Phase 6-7 (Learning)

- ✅ Alerts → Telegram < 5 minutes
- ✅ 100% decisions logged to Qdrant
- ✅ Knowledge base growing weekly
- ✅ Runbooks created from approvals

### Phase 8 (Autonomy)

- ✅ 3+ runbooks promoted to standard
- ✅ >95% success rate for automated actions
- ✅ Reduced notification volume (fewer manual approvals)
- ✅ Weekly digest shows learning progress

---

## Risk Mitigation

1. **Phase 1-2 failures**: Infrastructure issues
   - Mitigation: Terraform state backup, documented manual steps
   - Rollback: `terraform destroy`, redeploy from scratch

2. **Phase 3-5 failures**: AI platform issues
   - Mitigation: ArgoCD manages all deployments, easy rollback via git
   - Rollback: `git revert`, ArgoCD auto-syncs

3. **Phase 6-7 failures**: Learning system issues
   - Mitigation: Verbose mode requires approval for everything
   - Rollback: Disable alert routing, continue manual operations

4. **Phase 8 failures**: Autonomous action failures
   - Mitigation: Demote runbooks back to prompted/manual
   - Rollback: Set all automation_level = "prompted"

---

## Future Enhancements (Post Phase 8)

- **Multi-agent specialization**: Research agent, DocOps agent, Architect agent
- **Proactive monitoring**: Scheduled queries for security, health, optimization
- **Cross-cluster integration**: Monitor and manage prod_homelab, monit_homelab
- **Advanced reasoning**: Agentic workflows (planning, execution, reflection loops)
- **Community runbooks**: Share (anonymized) patterns with community
- **Continuous learning**: Regular model fine-tuning on successful decisions

---

## Current Status

**Phase**: 1 (Infrastructure provisioning)
**Last Updated**: {{ date }}
**Next Milestone**: Terraform apply to provision Talos cluster

See [CLAUDE.md](./CLAUDE.md) for detailed architecture.
See [GITOPS-WORKFLOW.md](./GITOPS-WORKFLOW.md) for deployment workflows.
