# Outline ↔ Silver Bullet Sync

Bidirectional sync between Outline collections and Silver Bullet notes pages.

## Overview

Each Outline collection gets a corresponding Silver Bullet notes page for quick thoughts. Claude reads both sources when developing plans.

```
Outline                     Silver Bullet
├── Media (collection)  ←→  outline/Media.md (notes page)
├── Infrastructure      ←→  outline/Infrastructure.md
├── Kernow MCPs        ←→  outline/Kernow MCPs.md
└── ...                 ←→  outline/...
```

**Use case:**
1. Structured documentation lives in Outline collections
2. Quick notes and thoughts go in Silver Bullet pages
3. Claude reads both when planning

---

## Architecture

### Outline → Silver Bullet (Real-time)

Outline sends webhook events when collections change. Knowledge-mcp receives these and creates/updates Silver Bullet pages.

```
Outline → webhook POST → knowledge-mcp → Silver Bullet API
```

**Webhook endpoint:** `POST /webhooks/outline`

**Triggered events:**
- `collections.create` - New collection → new SB page
- `collections.update` - Collection renamed → (logged, no action yet)
- `collections.delete` - Collection deleted → (logged, no action yet)

### Silver Bullet → Outline (Periodic)

CronJob runs every 5 minutes to check for new pages in Silver Bullet's `outline/` folder and create corresponding Outline collections.

```
CronJob (*/5 * * * *) → GET /webhooks/silverbullet → knowledge-mcp → Outline API
```

**Webhook endpoint:** `GET/POST /webhooks/silverbullet`

---

## Configuration

### Outline Webhook (Already Configured)

| Field | Value |
|-------|-------|
| Name | `Silver Bullet Sync` |
| URL | `https://knowledge-mcp.agentic.kernow.io/webhooks/outline` |
| Events | `collections.create`, `collections.update`, `collections.delete` |

### CronJob

Located at: `/home/mcp-servers/kubernetes/domains/silverbullet-sync-cronjob.yaml`

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: silverbullet-outline-sync
  namespace: ai-platform
spec:
  schedule: "*/5 * * * *"  # Every 5 minutes
  concurrencyPolicy: Forbid
```

---

## MCP Tools

| Tool | Purpose |
|------|---------|
| `sync_outline_to_silverbullet` | Create SB pages for all Outline collections |
| `sync_silverbullet_to_outline` | Create Outline collections for SB pages in `outline/` |
| `sync_collections_bidirectional` | Run both syncs |
| `silverbullet_list_pages` | List all SB pages |
| `silverbullet_read_page` | Read page content |
| `silverbullet_write_page` | Write/update page |
| `silverbullet_search` | Search across pages |

---

## Silver Bullet API Notes

### Authentication

Silver Bullet uses form-based auth with cookie sessions:
- Login: `POST /.auth` with `username` and `password`
- Returns JWT cookie: `auth_<hostname>=<token>`

### Required Headers

All API calls to `/.fs` require:
```
X-Sync-Mode: true
Cookie: auth_<hostname>=<jwt_token>
```

Without `X-Sync-Mode: true`, requests get redirected to the login page.

### File System Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/.fs` | GET | List all files (JSON) |
| `/.fs/<path>` | GET | Read file content |
| `/.fs/<path>` | PUT | Write file content |
| `/.fs/<path>` | DELETE | Delete file |

---

## Quick Notes Features

Silver Bullet supports rich note-taking:

| Feature | Syntax | Example |
|---------|--------|---------|
| Wiki Links | `[[Page Name]]` | `[[Infrastructure Plans]]` |
| Tags | `#tag` | `#todo`, `#idea`, `#question` |
| Tasks | `- [ ] Task` | `- [ ] Add GPU node` |
| Queries | `{query: ...}` | `{query: tag = "idea"}` |

**Example notes page:**
```markdown
# Infrastructure Plans

Quick notes for infrastructure improvements.

## Ideas
- [ ] Add GPU node for local inference #idea
- [ ] Migrate to Talos 1.9 #todo

## Questions
- How to handle multi-cluster ArgoCD? #question

## Links
- [[Kernow MCPs]] - related MCP docs
- [[Media]] - Plex infrastructure
```

---

## Verification

### Check webhook is working

```bash
# Watch logs for webhook events
kubectl logs -n ai-platform -l app=knowledge-mcp -f | grep -i webhook

# Check CronJob status
kubectl get cronjob silverbullet-outline-sync -n ai-platform

# View recent sync jobs
kubectl get jobs -n ai-platform | grep silverbullet
```

### Manual sync

```bash
# Trigger Outline → SB sync
curl -X POST https://knowledge-mcp.agentic.kernow.io/webhooks/outline \
  -H "Content-Type: application/json" \
  -d '{"event": "collections.create", "payload": {}}'

# Trigger SB → Outline sync
curl https://knowledge-mcp.agentic.kernow.io/webhooks/silverbullet
```

### Via MCP

```python
# Run bidirectional sync
sync_collections_bidirectional()

# List synced pages
silverbullet_list_pages(prefix="outline/")
```

---

## Troubleshooting

### Webhook not triggering

1. Check Outline webhook configuration in Settings → Webhooks
2. Verify URL is `https://knowledge-mcp.agentic.kernow.io/webhooks/outline`
3. Check knowledge-mcp logs for errors

### Auth failures (307 redirects)

Silver Bullet returns 307 redirects when:
- Cookie is missing or expired
- `X-Sync-Mode: true` header is missing

Fix: Restart knowledge-mcp to refresh auth session:
```bash
kubectl rollout restart deployment/knowledge-mcp -n ai-platform
```

### Pages not syncing

1. Check if SILVERBULLET_USER env var is set correctly
2. Verify Silver Bullet is accessible from knowledge-mcp:
   ```bash
   kubectl exec -n ai-platform deployment/knowledge-mcp -- \
     curl -s http://silverbullet.ai-platform.svc.cluster.local:3000/.ping
   ```

---

## Files

| File | Purpose |
|------|---------|
| `mcp-servers/domains/knowledge/src/knowledge_mcp/tools/silverbullet.py` | Sync logic and MCP tools |
| `mcp-servers/domains/knowledge/src/knowledge_mcp/server.py` | Webhook endpoints |
| `mcp-servers/kubernetes/domains/silverbullet-sync-cronjob.yaml` | Periodic sync job |
| `mcp-servers/kubernetes/domains/knowledge.yaml` | Knowledge-mcp deployment |

---

## Future Improvements

- [ ] Handle collection renames (update SB page name)
- [ ] Handle collection deletes (archive SB page)
- [ ] Add Silver Bullet file watcher for true real-time SB→Outline sync
- [ ] Sync document content (not just collections)
