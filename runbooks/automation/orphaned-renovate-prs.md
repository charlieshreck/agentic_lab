# Orphaned Renovate PRs

## Overview

Renovate was suspended in March 2026 (replaced by update-patrol). Open Renovate PRs
that were not merged before suspension remain open indefinitely. This runbook covers
how to handle `renovate_pr_pending` findings for these orphaned PRs.

## Background

- **Renovate suspended**: `suspend: true` in the Renovate CronJob (not deleted)
- **Replaced by**: `/home/scripts/update-patrol/` — daily Claude-driven update sweep
- **Repos affected**: monit_homelab, prod_homelab, agentic_lab, mcp-servers
- **Finding type**: `renovate_pr_pending` — fired when a Renovate PR sits open > threshold

## Investigation Steps

### 1. Get the PR diff
```bash
# Use MCP: mcp__external__github_get_pr_diff
# owner: charlieshreck, repo: <repo>, pr_number: <N>
```

### 2. Check current file versions
```bash
grep -n "image:" /home/<repo>/kubernetes/path/to/deployment.yaml
```

### 3. Classify the PR

| Condition | Action |
|-----------|--------|
| Current file version ≥ PR target version | **Stale** — close PR, nothing to do |
| Current file version < PR target version AND patch/minor update | Consider merging via update-patrol |
| Current file version < PR target version AND major update | **Needs review** — escalate for human decision |

## Resolution: Stale PR (Most Common)

When the codebase has already advanced past the PR's proposed version:

1. **Verify**: Confirm current file version > PR's proposed version
2. **Close PR**: Navigate to GitHub PR and close with comment:
   ```
   Closing — codebase is already at [current version], which supersedes this PR's
   target of [pr version]. Renovate has been replaced by update-patrol.
   ```
3. **Resolve finding** with `resolution_type: fp` (false positive — already resolved by other means)

## Resolution: Major Version Update Still Pending

If a Renovate PR proposes a major version update that hasn't been applied:

1. **Check if risky**: Major versions often have breaking changes
   - postgres 16→18, redis 7→8: DB major versions — verify compatibility first
   - traefik v2→v3: breaking API/config changes — check migration guide
2. **Check update-patrol registry**: Does `/home/scripts/update-patrol/registry.yaml` track this service?
   - If yes: update-patrol will handle it on the next patrol run
   - If no: Add the service to the registry
3. **Close the Renovate PR** with note that update-patrol is handling it
4. **Escalate** if the update is high-risk (stateful workloads, DB schema changes)

## Known Orphaned PRs (2026-03-22)

| Repo | PR | Proposed | Current | Status |
|------|----|----------|---------|--------|
| monit_homelab | #3 | reflector 7.1.288→10.0.16 | 10.0.21 | STALE — close |
| agentic_lab | #4 | reflector 7.1.288→10.0.16, traefik v2.11→v3.6 | reflector 10.0.21, traefik v3.6.11 | STALE — close |
| agentic_lab | #3 | postgres 16→18, redis 7→8, vikunja 0.24.6→2.1.0 | postgres 16, redis 7.4, vikunja 2.2.0 | PARTIAL — vikunja stale; postgres/redis major pending review |

**agentic_lab PR #3 note**: postgres 16 and redis 7.4 are still at the old versions. These are
major version updates requiring careful review (data migrations, compatibility). Add to
update-patrol registry rather than merging blindly.

## Patrol Rule

When `renovate_pr_pending` fires:
1. Always check current file version vs PR target version first
2. If current ≥ target: resolve as `fp`, note stale PR, request manual close
3. If current < target + major: escalate for human review
4. If current < target + patch/minor: feed to update-patrol for next sweep

## Preventing Future Orphan Buildup

If Renovate is ever re-enabled, ensure it can auto-close its own stale PRs:
```json
// renovate.json
{
  "automergeStrategy": "squash",
  "prCreation": "not-pending"
}
```

If Renovate remains suspended, periodically audit open PRs (monthly):
```bash
# Check all repos for open Renovate PRs
# mcp__external__github_list_prs for each repo, filter by author:renovate[bot]
```
