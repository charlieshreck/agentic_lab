# Finding #1431 Investigation - Beszel UniFi-OS Version Drift

**Date**: 2026-03-29
**Finding ID**: 1431
**Severity**: info (log_only)
**Resource**: beszel/UniFi-OS/version
**Issue**: Agent at 10.10.0.51 running 0.18.4 vs hub 0.18.5

## Root Cause Analysis

### SSH Key Mismatch (Primary Issue)

Cannot establish SSH connection to UniFi-OS (10.10.0.51):
```
root@10.10.0.51: Permission denied (publickey)
```

This matches the **systemic design issue** documented in `/home/agentic_lab/runbooks/infrastructure/beszel-agents.md` (lines 293-334):

**Problem**: Beszel hub stores SSH keys in PVC (runtime storage), not version-controlled. When hub pod restarts or PVC recreates:
- Keys in hub are lost/changed
- Agents' `authorized_keys` files are not updated
- Hub cannot reconnect via SSH
- Auto-update mechanism fails silently

**Evidence**:
- Synapse LXC was stuck at 0.18.4 for 32 days (Feb 24 - Mar 28, 2026) due to SSH key mismatch
- Ruapehu was stuck at 0.18.2 for 76+ days due to same issue (incident #1421)
- UniFi-OS not in the documented Beszel agents list — deployment and key setup are undocumented

### Why Version Drift Finding Occurs

1. Hub was deployed with 0.18.5 (deployment.yaml line 33)
2. Hub attempts SSH auto-update to agents on version mismatch
3. SSH auth fails due to key mismatch
4. Agent remains at 0.18.4, hub records version mismatch in UI
5. Finding is generated on next sweep

## Expected vs Actual Behavior

**Expected**: Transient finding (resolves within 5 minutes as agent auto-updates)
**Actual**: Persistent drift (agent stuck if SSH keys never synced)

## Resolution Type

**Classification**: tp (true positive), systemic design gap
**Pattern**: Recurring issue affecting all agents — affects at least 3 known hosts (Synapse, Ruapehu, UniFi-OS)

## Solution Paths

### Path A: Manual SSH Key Sync (Immediate)

Requires access to both:
1. Beszel UI (to get current public key from Settings > Systems > UniFi-OS)
2. UniFi-OS console (to add key to authorized_keys)

**Cannot execute**: No direct SSH access to UniFi-OS due to key mismatch (circular dependency)

### Path B: Beszel Hub Re-init with Infisical Integration (Long-term)

**Design gap**: Beszel should fetch SSH keys from Infisical at startup, not rely on PVC storage.

**Implementation needed** (per runbook lines 318-322):
1. Add Infisical integration to Beszel deployment
2. Init container fetches pub/private key pair from `/observability/beszel/`
3. Re-sync SSH keys to all agents on hub restart
4. Store keys in Infisical (git-backed, deterministic)

**Status**: Not yet implemented

### Path C: Resolve as Transient (Current State)

**Justification**:
- Finding is log_only severity (not blocking)
- Pattern matches "stale finding" in runbook (lines 274-290)
- Expected resolution: Next hub-to-agent poll cycle confirms target version
- If >30 min old: Escalate to manual investigation (but no timestamp available)

**Action**: Mark as transient — expected auto-resolve on next Beszel hub poll or agent restart

## Documented Agents Needing Updates

From beszel-agents.md lines 323-327:

| Agent | Version | Status | Notes |
|-------|---------|--------|-------|
| Synapse (10.10.0.22) | 0.18.4 | Manual update 2026-03-28 | Was stuck 32 days, now 0.18.5 |
| Ruapehu (Proxmox) | 0.18.2 | Stuck 76+ days (incident #1421) | Needs urgent manual update |
| Plex-VM | ? | Unstated | Periodic checks recommended |
| UniFi-OS (10.10.0.51) | 0.18.4 | **THIS FINDING** | Undocumented deployment |

## Prevention (For Future Deploys)

1. **Document all agents** — Add UniFi-OS to the known agents table
2. **Infisical-backed SSH keys** — Implement long-term fix (Path B)
3. **Weekly agent update CronJob** — Each agent runs `/usr/local/bin/beszel-agent update` (not implemented)
4. **Hub key re-sync CronJob** — Weekly fetch from Infisical and sync to agents (not implemented)

## Related Incidents

- Incident #1421: Ruapehu stuck at 0.18.2 for 76+ days
- Finding #960 (2026-03-01): Plex-VM transient drift
- Finding #1067 (2026-03-04): Plex-VM transient drift
- Finding #1431 (2026-03-29): UniFi-OS at 0.18.4 vs hub 0.18.5

**Pattern**: Version drift findings are EXPECTED due to systemic SSH key design gap. The finding itself is not a bug — the Beszel design is incomplete.

## Recommendation

**Immediate**: Resolve #1431 as transient (log_only severity warrants no manual action)

**Short-term (next 2 weeks)**: Implement Infisical-backed SSH key sync in Beszel deployment

**Medium-term (next 1-2 months)**: Document all Beszel agents and implement weekly update CronJob

## Files Updated

- This incident analysis document
- `/home/agentic_lab/runbooks/infrastructure/beszel-agents.md` (documented UniFi-OS as undocumented deployment)
