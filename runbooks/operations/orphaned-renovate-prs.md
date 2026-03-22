# Orphaned Renovate PRs

## Context

Renovate was suspended on 2026-03-10 and replaced by Update Patrol for managing dependency updates.
Renovate is NOT deleted (`suspend: true` in cronjob.yaml) but will not open new PRs.

Two orphaned Renovate PRs remain open on `charlieshreck/agentic_lab` as of 2026-03-22:

| PR | Title | Status |
|----|-------|--------|
| #4 | chore(deps): Update kubernetes-platform (major) | CLOSE — fully superseded |
| #3 | chore(deps): Update kubernetes-apps (major) | CLOSE — partially superseded; DB upgrades need planning |

## PR #4 — kubernetes-platform (CLOSE AS STALE)

Both components already updated beyond the PR's proposed versions:

| Component | PR Proposed | Current in Repo | Who Updated |
|-----------|-------------|-----------------|-------------|
| traefik | v3.6 | v3.6.11 | Update Patrol |
| kubernetes-reflector | 10.0.16 | 10.0.21 | Update Patrol |

**Action**: Close PR #4. No changes needed.

## PR #3 — kubernetes-apps (CLOSE AS STALE — DO NOT MERGE)

| Component | PR Proposed | Current in Repo | Notes |
|-----------|-------------|-----------------|-------|
| vikunja | 2.1.0 | 2.2.0 | Already updated by Update Patrol |
| postgres | 18-alpine | 16-alpine | ⚠️ BLOCKED — requires pg_upgrade |
| redis | 8.6-alpine / 8-alpine | 7.4-alpine / 7-alpine | Needs careful review |

**⚠️ DO NOT MERGE PR #3.** PostgreSQL 16→18 is a 2-major-version jump and requires:
1. `pg_upgrade` or dump/restore (cannot simply swap image tags)
2. Must upgrade one major version at a time: 16→17→18
3. Downtime window required

Redis 7→8 also needs a separate planned upgrade.

**Action**: Close PR #3. Postgres and Redis upgrades must be handled as separate planned migrations.

## Closing PRs

Use the GitHub web UI (GitHub PAT in Infisical `/external/github/TOKEN` is read-only):

```
https://github.com/charlieshreck/agentic_lab/pull/4  → Close with comment (stale/superseded)
https://github.com/charlieshreck/agentic_lab/pull/3  → Close with comment (stale/superseded; DB upgrades need planning)
```

## Patrol Rule

When `renovate_pr_pending` findings appear:
1. Check if Renovate is still suspended (`kubectl get cronjob renovate -n renovate -o yaml | grep suspend`)
2. If suspended: check if the proposed versions are already exceeded in the manifests → resolve as fp
3. If not suspended: verify against Update Patrol policy (`registry.yaml`):
   - `policy: auto` → Renovate PR is redundant, close it
   - `policy: review` → Renovate PR needs human review before merging
4. NEVER auto-merge PRs that touch postgres or redis major versions without migration planning

## Related

- Update Patrol registry: `/home/scripts/update-patrol/registry.yaml`
- Postgres upgrade notes: see `postgresql` entry in registry (policy: review, critical migration notes)
- Redis upgrade notes: see `redis` entry in registry (policy: review)
