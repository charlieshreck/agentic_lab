# Vikunja MCP - Task Management for Claude

## Overview

The vikunja-mcp server enables Claude to manage tasks, ideas, and planning boards in Vikunja. It provides 14 tools for project and task management.

## Location

- Server: 10.20.0.40:31097 (agentic cluster, ai-platform namespace)
- Vikunja: 10.20.0.40:31095 (agentic cluster, vikunja namespace)
- Web UI: https://vikunja.kernow.io

## MCP Tools

### Project Management

| Tool | Purpose | Example |
|------|---------|---------|
| `list_projects` | List all projects | `list_projects()` |
| `create_project` | Create new project | `create_project("My Project", "Description")` |
| `get_project` | Get project details | `get_project(project_id=1)` |

### Task Management

| Tool | Purpose | Example |
|------|---------|---------|
| `list_tasks` | List tasks in project | `list_tasks(project_id=1)` |
| `create_task` | Add task to project | `create_task(project_id=1, title="Do thing")` |
| `update_task` | Modify task | `update_task(task_id=1, done=True)` |
| `complete_task` | Mark task done | `complete_task(task_id=1)` |

### Kanban Buckets

| Tool | Purpose | Example |
|------|---------|---------|
| `list_buckets` | List kanban columns | `list_buckets(project_id=1)` |
| `create_bucket` | Add kanban column | `create_bucket(project_id=1, title="In Review")` |
| `move_task_to_bucket` | Move task between columns | `move_task_to_bucket(task_id=1, bucket_id=2)` |

### Ideas & Quick Add

| Tool | Purpose | Example |
|------|---------|---------|
| `add_idea` | Quick idea capture | `add_idea("Consider using Redis for caching")` |
| `list_ideas` | View captured ideas | `list_ideas()` |

### Plan Mode Integration

| Tool | Purpose | Example |
|------|---------|---------|
| `create_plan_board` | Create kanban for plan | See below |
| `update_plan_progress` | Move task through stages | `update_plan_progress(project_id=1, task_id=1, status="done")` |

## Usage Patterns

### Quick Idea Capture

When Claude has an idea during conversation:
```
add_idea("Refactor auth module to use JWT")
```

Ideas are stored in a dedicated "Ideas" project for later review.

### Plan Mode Board Creation

When creating implementation plans:
```python
create_plan_board(
    plan_name="User Authentication",
    steps=[
        "Research OAuth2 providers",
        "Design token flow",
        "Implement login endpoint",
        "Add refresh token logic",
        "Write integration tests"
    ],
    buckets=["Todo", "In Progress", "Done"]
)
```

This creates a kanban board with all steps in the "Todo" column.

### Tracking Plan Progress

As work progresses:
```python
# Start working on a task
update_plan_progress(project_id=2, task_id=5, status="in_progress")

# Complete the task
update_plan_progress(project_id=2, task_id=5, status="done")
```

## Direct API Access

When MCP is unavailable, use Vikunja API directly:

### Authentication
```bash
VIKUNJA_TOKEN="tk_xxx"
VIKUNJA_URL="http://10.20.0.40:31095"
```

### List Projects
```bash
curl -s "${VIKUNJA_URL}/api/v1/projects" \
  -H "Authorization: Bearer ${VIKUNJA_TOKEN}"
```

### Create Project (PUT, not POST)
```bash
curl -s -X PUT "${VIKUNJA_URL}/api/v1/projects" \
  -H "Authorization: Bearer ${VIKUNJA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"title":"My Project","description":"Description"}'
```

### Create Task (PUT, not POST)
```bash
curl -s -X PUT "${VIKUNJA_URL}/api/v1/projects/1/tasks" \
  -H "Authorization: Bearer ${VIKUNJA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"title":"Task title","description":"Details"}'
```

### Mark Task Done
```bash
curl -s -X POST "${VIKUNJA_URL}/api/v1/tasks/1" \
  -H "Authorization: Bearer ${VIKUNJA_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"done":true}'
```

## API Quirks

**Important**: Vikunja API uses non-standard HTTP methods:
- **PUT** for creating resources (projects, tasks, buckets)
- **POST** for updating existing resources

This is opposite to typical REST conventions.

## Health Check

```bash
# MCP health
curl http://10.20.0.40:31097/health

# Vikunja API
curl http://10.20.0.40:31095/api/v1/info
```

## Secrets

API token stored in Infisical:
```bash
/root/.config/infisical/secrets.sh get /apps/vikunja API_TOKEN
```

To regenerate token:
1. Login to Vikunja web UI
2. Settings → API Tokens
3. Create new token
4. Update Infisical: `/root/.config/infisical/secrets.sh set /apps/vikunja API_TOKEN "tk_new_token"`
5. Restart MCP: `kubectl rollout restart deployment/vikunja-mcp -n ai-platform`

## Troubleshooting

### MCP Not Responding
```bash
# Check pod status
KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig \
  kubectl get pods -n ai-platform -l app=vikunja-mcp

# Check logs
KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig \
  kubectl logs -n ai-platform -l app=vikunja-mcp --tail=50
```

### API Returns "Not Found"
- Ensure using PUT (not POST) for create operations
- Verify token is valid and not expired

### Task Not Moving to Bucket
- Buckets are project-specific
- Get bucket IDs first: `list_buckets(project_id=X)`

## Integration with Plan Mode

Add to CLAUDE.md for plan mode awareness:
```markdown
## Vikunja Integration

For complex plans, create a visual kanban board:
- Use `create_plan_board` when starting multi-step implementations
- Update progress with `update_plan_progress`
- Capture ideas with `add_idea`
```
