# Project 05: Skills & Orchestration - Status

**Last Updated:** 2026-01-30
**Phase:** 1 Complete ✅ | Phase 2 Ready

---

## Quick Status

| Component | Status | Notes |
|-----------|--------|-------|
| Qdrant skills collection | ✅ | 6 skills seeded |
| Neo4j skill graph | ✅ | v1.2.0 schema, 7 Skill nodes |
| knowledge-mcp skill tools | ✅ | 7 new tools deployed |
| LangGraph skill_router | ✅ | `SKILL_ROUTER_ENABLED=true` |
| Matrix bot slash commands | 🎯 | Phase 2 |
| Skill execution metrics | 🎯 | Phase 2 |

---

## What's Deployed

### Skills in Qdrant

```
infrastructure-skill  - /troubleshoot, /deploy, /remediate
observability-skill   - /investigate, /status, /metrics
home-skill            - /home, /lights, /devices
media-skill           - /media, /plex, /download
research-skill        - /research, /search, /web
data-skill            - /learn, /knowledge
```

### knowledge-mcp Skill Tools

| Tool | Purpose |
|------|---------|
| `search_skills` | Semantic search for matching skill |
| `get_skill` | Get skill by ID |
| `get_skill_by_command` | Get skill by slash command |
| `add_skill` | Add new skill to registry |
| `update_skill` | Update existing skill |
| `list_skills` | List all skills (optionally by domain) |
| `record_skill_execution` | Record success/failure for learning |

### LangGraph Configuration

```yaml
SKILL_ROUTER_ENABLED: "true"
SKILL_COLLISION_THRESHOLD: "0.2"  # 20% relative threshold
MAX_MCPS_PER_REQUEST: "8"
```

---

## Files Created

```
kubernetes/applications/skill-registry/
├── configmap.yaml              # 6 skill definitions
└── seed-job.yaml               # Seeds skills to Qdrant

kubernetes/argocd-apps/
└── skill-registry-app.yaml     # ArgoCD Application

kubernetes/applications/neo4j/schema/
└── 002-skill-relationships.cypher  # Neo4j migration
```

## Files Modified

```
kubernetes/applications/langgraph/langgraph.yaml
├── Added: skill_router node function
├── Added: AgentState fields (skill_id, skill_context, loaded_mcps)
└── Added: Environment variables for skill router

mcp-servers/domains/knowledge/src/knowledge_mcp/tools/qdrant.py
└── Added: 7 skill collection tools
```

---

## Verification Commands

```bash
# Check skills count in Qdrant
curl -s http://qdrant.ai-platform.svc:6333/collections/skills | jq '.result.points_count'
# Expected: 6

# Check Neo4j skills
kubectl exec -n ai-platform neo4j-0 -- cypher-shell -u neo4j -p password \
  "MATCH (s:Skill) RETURN count(s)"
# Expected: 7

# Check LangGraph env vars
kubectl exec -n ai-platform deploy/langgraph -- printenv | grep SKILL
# Expected: SKILL_ROUTER_ENABLED=true

# Check LangGraph health
curl -s http://langgraph.agentic.kernow.io/health
# Expected: {"status":"healthy"}
```

---

## Next Steps (Phase 2)

1. **Matrix Bot Slash Commands**
   - Add command parsing to matrix-bot.yaml
   - Route `/troubleshoot`, `/home`, `/media`, etc. to LangGraph `/skill` endpoint

2. **Test Skill Routing**
   - Send test messages via Matrix
   - Verify correct skill is selected
   - Check MCP loading based on skill

3. **Skill Execution Metrics**
   - Log skill executions to agent_events
   - Create Grafana dashboard for skill usage

---

## Architecture

```
User Message
    ↓
skill_router (LangGraph)
    ↓
Qdrant search_skills()
    ↓
Match skill → Load MCPs → Set context
    ↓
assess_alert → generate_solutions → ...
```

### Collision Detection

When multiple skills match with similar scores:
- Uses 20% relative threshold
- If top scores within 20% of each other → ambiguous
- Slash commands take priority over semantic matches

### MCP Loading

Each skill defines primary and secondary MCPs:
- **Primary**: Always loaded (e.g., infrastructure-mcp, knowledge-mcp)
- **Secondary**: Loaded on demand
- **Limit**: Max 8 MCPs per request

---

## Related Documents

- [Full Implementation Plan](/root/.claude/plans/hazy-rolling-emerson.md)
- [Skill Schema](../kubernetes/applications/skill-registry/configmap.yaml)
- [LangGraph Code](../kubernetes/applications/langgraph/langgraph.yaml)
