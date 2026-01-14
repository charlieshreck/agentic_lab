# Planning Agent Runbook

## Overview

The planning-agent is a Claude Code skill that orchestrates thorough, context-aware planning using 32 expert profiles and full infrastructure visibility.

## Quick Reference

| Item | Value |
|------|-------|
| Skill location | `/root/.claude/skills/planning-agent/` |
| Plans repository | `/home/agentic_lab/plans/` |
| Qdrant collections | plans, external_research, profiles |
| Neo4j integration | Deployed, optional enhancement |

## Activation

The skill activates when Claude Code detects planning-related requests:
- Keywords: "plan", "design", "architect", "strategy", "implement"
- Questions: "how should I", "what's the best way to"

## Workflow

```
1. RESEARCH FIRST     → research-discovery profile activates
2. GATHER CONTEXT     → Query MCPs, entities, past plans
3. SELECT PROFILES    → Choose domain-specific profiles
4. EXTERNAL RESEARCH  → Search web/docs if needed
5. SYNTHESIZE PLAN    → Combine inputs into plan
6. STORE & LEARN      → Save to Git + Qdrant
```

## Profile Categories

| Category | Profiles | Primary Use |
|----------|----------|-------------|
| Research | research-discovery, entity-intelligence | Context gathering |
| Infrastructure | k8s-platform, storage-architect, compute-infra | K8s/VM/storage |
| Networking | network-architect, dns-routing, ingress-access, firewall-security | Network changes |
| Applications | media-services, home-automation, secrets-management | App config |
| Operations | sre-operations, monitoring-observability, incident-response, log-analysis | Ops tasks |
| Development | gitops-deployment, mcp-development, terraform-iac, ansible-config | Dev/deploy |
| Quality | testing-validation, documentation-writer, approval-workflow | Quality/docs |
| Specialized | 9 profiles for security, cost, AI/ML, backup, etc. | Domain-specific |

## Common Operations

### Initialize Collections (First Time)

```bash
cd /home/agentic_lab
export QDRANT_URL=http://10.20.0.40:31084
python scripts/init_plans_collection.py
```

### Search Past Plans

```bash
# Via script
python /root/.claude/skills/planning-agent/scripts/query_plans.py --search "kubernetes"

# Via knowledge-mcp
# knowledge-mcp.search_plans("kubernetes deployment")
```

### Store a Plan

```bash
python /root/.claude/skills/planning-agent/scripts/store_plan.py \
  --title "My Plan" \
  --domain infrastructure \
  --file /path/to/plan.md
```

### Capture Lessons

```bash
python /root/.claude/skills/planning-agent/scripts/capture_lessons.py \
  --id <plan-uuid> \
  --outcome success \
  --worked "Good rollback plan" \
  --recommendations "Add more testing"
```

## Troubleshooting

### Skill Not Activating

1. Check skill file exists: `ls /root/.claude/skills/planning-agent/SKILL.md`
2. Verify Claude Code loaded skill (check startup logs)
3. Try explicit activation: "Please use the planning agent to..."

### Profile Not Found

1. Check profile exists: `ls /root/.claude/skills/planning-agent/references/profiles/`
2. Verify profile ID matches activation keywords

### Qdrant Connection Failed

1. Check Qdrant service:
   ```bash
   curl http://10.20.0.40:31084/health
   ```
2. Verify collections exist:
   ```bash
   curl http://10.20.0.40:31084/collections
   ```

### Neo4j Unavailable

The planning agent works in degraded mode without Neo4j:
- Relationship queries skipped
- Plans flagged as "incomplete research"
- See: `/home/agentic_lab/runbooks/troubleshooting/planning-agent-neo4j.md`

## File Locations

### Skill Files
```
/root/.claude/skills/planning-agent/
├── SKILL.md                    # Main skill definition
├── references/
│   ├── research-protocol.md    # Research workflow
│   ├── profile-combinations.md # Profile usage
│   └── profiles/               # 32 profile definitions
│       ├── research/
│       ├── infrastructure/
│       ├── networking/
│       ├── applications/
│       ├── operations/
│       ├── development/
│       ├── quality/
│       └── specialized/
└── scripts/
    ├── store_plan.py
    ├── query_plans.py
    └── capture_lessons.py
```

### Plans Repository
```
/home/agentic_lab/plans/
├── README.md
├── templates/
│   ├── infrastructure.md
│   └── operations.md
├── infrastructure/
├── operations/
└── frontend/
```

## Maintenance

### Adding a New Profile

1. Create profile file in appropriate category:
   ```
   /root/.claude/skills/planning-agent/references/profiles/{category}/{id}.md
   ```

2. Follow profile template structure (see existing profiles)

3. Update profile-combinations.md if needed

### Updating Profile Content

Profiles are pure markdown files. Edit directly and changes take effect in next Claude Code session.

### Cleaning Old Plans

Plans older than 6 months with outcome=success can be archived:

```bash
# List old plans
python query_plans.py --status archived

# Move to archive (manual)
mv /home/agentic_lab/plans/infrastructure/2025-*.md /home/agentic_lab/plans/archive/
```

## Monitoring

### Health Checks

| Component | Check |
|-----------|-------|
| Qdrant | `curl http://10.20.0.40:31084/health` |
| Neo4j | `curl http://10.20.0.40:31099/health` |
| Knowledge MCP | `curl http://10.20.0.40:31084/health` |

### Metrics to Track

- Plans created per week
- Profile activation frequency
- Plan success rate
- Average planning duration

## Related Documentation

- [Planning Agent Plan](/root/.claude/plans/harmonic-cuddling-bird.md)
- [Neo4j Troubleshooting](/home/agentic_lab/runbooks/troubleshooting/planning-agent-neo4j.md)
- [MCP Development Guide](/home/agentic_lab/docs/mcp-development-guide.md)
