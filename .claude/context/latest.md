# Agentic Platform Context

**Last Updated**: 2026-01-26
**Status**: Operational - Core platform running

---

## Architecture Overview

| Role | Model | Responsibility |
|------|-------|----------------|
| **Agent** | Ollama (qwen2.5:7b) via LiteLLM | Alert response, runbook execution, local inference |
| **Orchestrator** | LangGraph (StateGraph) | Incident flow, confidence routing, escalation |
| **Validator** | Human-triggered skill (`/validate`) | Ground truth verification, autonomy audits |
| **Architect** | Claude Code (with Charlie) | Architecture, planning, context-aware review |
| **Reviewer** | Gemini (peer review) | Quality gating, audit, devil's advocate |

**Key change from original design**: Claude Validator (cloud API) removed. Replaced by `/validate` skill using LiteLLM routing to any configured backend. Validation is human-triggered, not automated.

---

## Service Status

| Service | Status | Notes |
|---------|--------|-------|
| Ollama | ✅ Running | qwen2.5:7b + nomic-embed-text, AMD ROCm |
| LiteLLM | ✅ Running | Routes all model aliases to local Ollama |
| Qdrant | ✅ Running | 9+ collections, dual-indexed with Neo4j |
| Neo4j | ✅ Running | Knowledge graph, relationships, dependencies |
| LangGraph | ✅ Running | 5-node incident flow, Keep webhook handler |
| Matrix/Conduit | ✅ Running | Self-hosted, reaction-based approvals |
| Matrix Bot | ✅ Running | Alert, approval, brain-trust, runbook-proposal |
| Knowledge MCP | ✅ Running | 38 tools across 6 modules |
| Pattern Detector | ⚠️ Partial | Runs daily but notifications silenced (missing env vars) |
| Outline | ✅ Running | Wiki, project docs, brain trust escalation |
| PostgreSQL | ✅ Running | LangGraph state checkpointing |
| Redis | ✅ Running | Semantic caching, job queues |

---

## Knowledge System Projects (Outline Collection)

| # | Project | Status |
|---|---------|--------|
| 01 | Neo4j Schema Design | ✅ Complete |
| 02 | Dual-Indexing & Retrieval | ✅ Complete |
| 03 | Evaluator System | 🟡 Redesigned (validator-as-skill) |
| 04 | LangGraph Incident Flow | 🟡 Largely implemented (Phase 7 pending) |
| 05 | Skills & Orchestration | 🔴 Not Started |
| 06 | Development Flow & CLI | 🔴 Not Started |
| 07 | Runbook System | 🟡 Partial (pattern detector) |
| 08 | Bootstrap & Migration | 🔴 Not Started |

**Outline Collection**: "Agentic Knowledge System" - all project docs and reviews

---

## Active Work: Autonomy Progression

Remaining (2 days):
1. Add MATRIX_WEBHOOK_URL to pattern-detector CronJob
2. Fix thresholds (70/85/95 for prompted/standard/autonomous)
3. Add Matrix bot `!approve-autonomy` and `!list-autonomy-candidates` commands
4. Test end-to-end: detection -> notification -> approval -> promotion

---

## MCP Servers (6 domains)

All running in agentic cluster (ai-platform namespace):

| Domain | Endpoint |
|--------|----------|
| observability | observability-mcp.agentic.kernow.io |
| infrastructure | infrastructure-mcp.agentic.kernow.io |
| knowledge | knowledge-mcp.agentic.kernow.io |
| home | home-mcp.agentic.kernow.io |
| media | media-mcp.agentic.kernow.io |
| external | external-mcp.agentic.kernow.io |

---

## Key Decisions

- **Local-first inference**: All LLM calls route through LiteLLM to Ollama (no cloud API costs)
- **Validator-as-skill**: `/validate` replaces automated claude-validator
- **Autonomy progression**: manual -> prompted -> standard -> autonomous (earned through reliability)
- **Matrix for approvals**: Reaction-based (no buttons in Matrix spec yet)
- **Neo4j + Qdrant dual-indexing**: Graph for relationships, vectors for semantic search

---

## Quick Reference

```bash
# Check platform health
kubectl get pods -n ai-platform

# Trigger pattern detector manually
kubectl create job --from=cronjob/pattern-detector pd-test -n ai-platform

# Check LangGraph status
curl http://langgraph.ai-platform.svc:8000/status

# Search knowledge base
# Use knowledge-mcp tools: search_runbooks(), search_entities(), retrieve()
```
