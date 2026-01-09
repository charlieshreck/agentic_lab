# Agentic Platform Context - Initial Setup

**Last Updated**: Initial deployment
**Status**: Platform initializing

---

## Session Checkpoint

Last reviewed: Not yet reviewed
Checkpoint ID: initial-setup
Changes since last session: Initial deployment

---

## Architecture Overview

This is a split-role AI architecture:

| Role | Model | Responsibility |
|------|-------|----------------|
| **Workhorse** | Gemini 2.0 Pro (via LiteLLM) | Alert response, runbook execution, maintenance |
| **Validator** | Claude (via claude-validator) | Reviews outputs, auto-corrects, flags issues |
| **Architect** | Claude Code (you) | Architecture decisions, planning, context review |

---

## Attention Required

- [ ] Configure Matrix rooms after Conduit deployment
- [ ] Add GEMINI_API_KEY to Infisical at `/agentic-platform/Gemini/`
- [ ] Verify ArgoCD sync for new applications
- [ ] Test end-to-end alert flow

---

## Recent Activity Summary

**Platform Status**: Initializing (not yet deployed)

- Alerts processed: 0
- Gemini decisions: 0
- Pending validations: 0
- New runbooks: 0

---

## Key Services

| Service | Status | Notes |
|---------|--------|-------|
| LiteLLM | Pending | Gemini-only config |
| Qdrant | Pending | 9 collections configured |
| LangGraph | Pending | Orchestrator with comprehensive context |
| Matrix/Conduit | Pending | Replaces Telegram |
| Matrix Bot | Pending | Conversational interface |
| Claude Validator | Pending | Daily validation + webhooks |
| Coroot MCP | Pending | Observability metrics |

---

## Quick Links (Qdrant Queries)

Query recent decisions:
```bash
curl -s -X POST "http://qdrant:6333/collections/decisions/points/scroll" \
  -H "Content-Type: application/json" \
  -d '{"limit": 10, "with_payload": true}'
```

Query runbook inventory:
```bash
curl -s -X POST "http://qdrant:6333/collections/runbooks/points/scroll" \
  -H "Content-Type: application/json" \
  -d '{"limit": 20, "with_payload": true}'
```

Query pending validations:
```bash
curl -s -X POST "http://qdrant:6333/collections/validations/points/scroll" \
  -H "Content-Type: application/json" \
  -d '{"limit": 10, "with_payload": true, "filter": {"must": [{"key": "status", "match": {"value": "pending"}}]}}'
```

---

## Architectural Notes

- **Context Strategy**: Gemini uses 1M token context window for comprehensive context injection
- **Learning Loop**: All decisions stored in Qdrant, outcomes tracked, patterns identified
- **Progressive Autonomy**: Runbooks graduate from manual -> prompted -> standard based on success rate
- **Self-Evolution**: MCPs and skills auto-generated when gaps detected (requires approval)

---

## Next Steps

1. Deploy platform via ArgoCD
2. Verify secret synchronization from Infisical
3. Test Matrix integration
4. Send test alert to verify end-to-end flow
5. Review first Gemini decisions

---

*This file is auto-updated by Claude Validator after each validation run.*
*For deep dives, use the slash commands: /agentic-status, /review-pending, /gemini-activity*
