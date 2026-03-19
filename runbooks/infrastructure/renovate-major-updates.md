# Renovate Major Update PRs

**Finding Type**: `renovate_pr_pending` (warning severity)
**Classification**: `create_rule` — requires manual review for major versions

---

## Overview

Renovate creates PRs for dependency updates. Non-major updates are auto-merged by the error-hunter.
Major updates (especially database engines) require manual review and planned migration.

> **Note**: As of 2026-03-10, Renovate is **suspended** and replaced by **Update Patrol**
> (`/home/scripts/update-patrol/`). The error-hunter skips `check_renovate()` when the
> CronJob is suspended. Any residual open Renovate PRs should be closed as stale.

---

## Triage Decision Tree

```
Is Renovate CronJob suspended?
├── YES → Close all open Renovate PRs as stale (Update Patrol handles tracking)
└── NO → Evaluate each update:
    ├── patch/minor → Auto-merge (error-hunter handles this)
    └── major → Follow upgrade procedure below
```

---

## Major Update Evaluation

### Step 1: Check what's changing

Look at the PR diff. Key risk levels:

| Package | Risk | Why |
|---------|------|-----|
| `postgres` major | **CRITICAL** | Data directory format changes — requires `pg_dump`/restore |
| `redis` major | Medium | Generally backward-compatible RDB/AOF format, but test first |
| App images (vikunja, outline, etc.) | Medium | May have DB schema migrations |
| Tool images (backup jobs) | Low | Stateless, just update the tag |

### Step 2: Never merge bundled major+database updates

The `kubernetes-apps` group should exclude `postgres` and `redis` (see `renovate.json`).
If a PR bundles database images with app images, it's a Renovate config bug — close and handle separately.

---

## PostgreSQL Major Version Upgrade

PostgreSQL data directories are **not forward compatible** between major versions.
Simply changing the image tag will crash the pod.

### Procedure (postgres 16 → 18 example)

1. **Schedule downtime** — all apps using this postgres instance will be down

2. **Dump the data** (while running on old version):
   ```bash
   kubectl exec -n ai-platform postgresql-0 -- \
     pg_dumpall -U langgraph > /tmp/pgdump-$(date +%Y%m%d).sql
   # Copy dump out
   kubectl cp ai-platform/postgresql-0:/tmp/pgdump-$(date +%Y%m%d).sql ./pgdump.sql
   ```

3. **Delete the PVC** (after confirming backup):
   ```bash
   # Verify backup is good first!
   wc -l pgdump.sql
   head -5 pgdump.sql

   # Scale down all apps that use postgres
   # Then delete the StatefulSet and PVC
   kubectl delete statefulset postgresql -n ai-platform
   kubectl delete pvc postgresql-data-postgresql-0 -n ai-platform
   ```

4. **Update the image tag** in git:
   ```
   # agentic_lab/kubernetes/applications/postgresql/statefulset.yaml
   image: postgres:18-alpine
   ```

5. **Commit and let ArgoCD recreate** the StatefulSet with fresh PVC

6. **Restore the dump**:
   ```bash
   kubectl exec -i -n ai-platform postgresql-0 -- psql -U langgraph < pgdump.sql
   ```

7. **Verify** all dependent apps are healthy

### Current PostgreSQL State (2026-03-19)
- Running: `postgres:16-alpine` in `ai-platform` namespace
- Databases: `langgraph` (primary) + any databases added by init jobs
- Storage: 10Gi `local-path` PVC on agentic cluster

---

## Redis Major Version Upgrade

Redis 8+ is backward-compatible with RDB/AOF data from Redis 7.
However, verify the running Redis config before upgrading.

### Procedure

1. Check what data Redis holds (is it critical or ephemeral?):
   ```bash
   kubectl exec -n ai-platform redis-0 -- redis-cli INFO keyspace
   ```

2. If ephemeral (caches, sessions): update image tag directly, let ArgoCD sync.

3. If persistent data needed: dump first:
   ```bash
   kubectl exec -n ai-platform redis-0 -- redis-cli BGSAVE
   # then copy /data/dump.rdb
   ```

4. Update `image: redis:8.6-alpine` in statefulset.yaml, commit, ArgoCD syncs.

5. Verify connectivity:
   ```bash
   kubectl exec -n ai-platform redis-0 -- redis-cli ping
   ```

---

## App Image Major Upgrades (Vikunja, etc.)

### vikunja/vikunja 0.24.6 → 2.1.0

This is a significant version jump with a new versioning scheme (0.x → 2.x).

1. **Check changelog** for breaking changes and required migrations:
   - v2.0.0: Check `CHANGELOG.md` for DB schema changes
   - Vikunja auto-runs migrations on startup

2. **Backup Vikunja data** before upgrading:
   ```bash
   # Vikunja data is stored in postgresql (ai-platform/postgresql)
   kubectl exec -n ai-platform postgresql-0 -- \
     pg_dump -U langgraph vikunja > vikunja-backup.sql
   ```

3. Update image tag, commit, let ArgoCD sync.

4. Check pod logs on startup for migration errors:
   ```bash
   kubectl logs -n ai-platform -l app=vikunja --tail=50
   ```

---

## Closing a Stale Renovate PR

Since Renovate is suspended, open PRs are stale and should be closed:

1. Navigate to the PR on GitHub
2. Close without merging, with comment:
   > "Renovate is suspended (replaced by Update Patrol). This major update requires
   > a planned migration — see runbook: runbooks/infrastructure/renovate-major-updates.md.
   > Closing as stale; individual upgrades will be tracked via Update Patrol."

Or via GitHub API (requires PAT with `pull_requests:write`):
```bash
GITHUB_TOKEN=$(/root/.config/infisical/secrets.sh get /external/github TOKEN)
curl -X PATCH \
  "https://api.github.com/repos/charlieshreck/agentic_lab/pulls/3" \
  -H "Authorization: Bearer $GITHUB_TOKEN" \
  -d '{"state":"closed"}'
```

---

## Update Patrol Policy for Major Updates

The Update Patrol registry at `/home/scripts/update-patrol/registry.yaml` uses:
- `policy: auto` — patch/minor auto-applied
- `policy: review` — major versions flagged for manual review
- `policy: pin` — skip entirely

Postgres and Redis should be set to `policy: pin` since upgrades require migrations.

---

## Related

- Update Patrol registry: `/home/scripts/update-patrol/registry.yaml`
- Backup operations: `runbooks/infrastructure/agentic-backup-operations.md`
- Error-hunter finding: `renovate_pr_pending` (check_renovate in error-hunter.yaml)
