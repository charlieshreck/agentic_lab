# Plans Repository

This directory contains all generated plans from the planning-agent skill.

## Structure

```
plans/
├── README.md                 # This file
├── templates/                # Plan templates
│   ├── infrastructure.md
│   └── operations.md
├── infrastructure/           # Infrastructure change plans
├── operations/               # Operational procedure plans
└── frontend/                 # UI/Frontend plans
```

## Plan Lifecycle

```
1. Draft     → Plan created by planning-agent
2. Approved  → User approved the plan
3. Executed  → Plan implemented
4. Archived  → Plan completed with lessons captured
```

## Plan Format

Every plan follows a standard structure:

```markdown
# Plan: {Title}

## Metadata
- **ID**: {uuid}
- **Created**: {timestamp}
- **Profiles**: [list of profiles used]
- **Status**: draft | approved | executed | archived
- **Outcome**: pending | success | partial | failed

## Context Snapshot
{Infrastructure state at planning time}

## Research Summary
{Internal and external sources consulted}

## The Plan
{Actual implementation steps}

## Risk Assessment
{Risk evaluation and mitigation}

## Execution Notes
{Filled during/after execution}

## Lessons Learned
{Captured after completion}
```

## Naming Convention

```
{date}-{short-description}.md
Example: 2026-01-13-neo4j-deployment.md
```

## Storage

Plans are stored in two places:
1. **Git** (this directory) - Version controlled, authoritative
2. **Qdrant** (plans collection) - Searchable via knowledge-mcp

## Usage

### Create Plan
The planning-agent skill creates plans in this directory.

### Search Plans
```python
# Via knowledge-mcp
knowledge-mcp.search_plans("{query}")
```

### Link Plans to Entities (Neo4j)
```cypher
MATCH (p:Plan {id: "{plan-id}"})
MATCH (s:Service {name: "{service}"})
CREATE (p)-[:AFFECTS]->(s)
```

## Related

- Planning Agent Skill: `/root/.claude/skills/planning-agent/`
- Plan templates: `templates/`
- Knowledge base: Qdrant via knowledge-mcp
