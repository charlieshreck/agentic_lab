# Kernow Homelab Ecosystem Audit

**Date:** 2026-01-15
**Auditor:** Claude Code
**Vision:** Forever learning, forever maturing, self-maintaining ecosystem

---

## Executive Summary

The Kernow Homelab has solid foundations but critical gaps in the learning feedback loop. The infrastructure (MCP servers, LLMs, vector DB, knowledge graph) is built, but the nervous system (alerts → decisions → outcomes → learning) isn't fully connected.

**Overall Progress: ~60%** toward self-maintaining ecosystem

---

## Vision vs Reality Scorecard

| Phase | Description | Status | Completion |
|-------|-------------|--------|------------|
| **1-2** | Infrastructure (Talos, K8s, Storage) | ✅ Complete | 100% |
| **3** | Inference Layer (LiteLLM, Gemini, Ollama) | ✅ Complete | 95% |
| **4** | Vector Knowledge Base (Qdrant) | ⚠️ Partial | 40% |
| **5** | MCP Servers (20 integrations) | ✅ Complete | 100% |
| **6** | Orchestration + Human-in-Loop | ⚠️ Partial | 35% |
| **7** | Go Live - Alert Routing | ⚠️ Partial | 50% |
| **8** | Progressive Autonomy | ❌ Not Started | 0% |

---

## Detailed Findings

### 1. Infrastructure ✅ (Excellent)

**Working:**
- Talos v1.11.5 cluster on bare metal (UM690L)
- 3 isolated networks (prod 10.10.0.0/24, agentic 10.20.0.0/24, monit 10.30.0.0/24)
- 20 MCP servers all healthy and operational
- 30 deployments running in ai-platform namespace
- Neo4j knowledge graph: 110 hosts, 20 VMs, 352 services

**Issues:**
- Node 10.10.0.42 at 93.54% memory
- cilium-operator rollout stuck
- Some pods in monit cluster not ready

---

### 2. Knowledge Base ⚠️ (Needs Attention)

**Qdrant Collections Status:**

| Collection | Points | Status |
|------------|--------|--------|
| runbooks | 23 | ✅ Good |
| entities | 127 | ✅ Good |
| device_types | 13 | ✅ Good |
| documentation | 7 | ⚠️ Sparse |
| decisions | 1 | ❌ Empty |
| validations | 0 | ❌ Empty |
| capability_gaps | 0 | ❌ Empty |
| skill_gaps | 0 | ❌ Empty |
| user_feedback | 0 | ❌ Empty |
| agent_events | 0 | ❌ Empty |

**Critical Gap:** Learning collections are empty. System cannot learn.

---

### 3. Runbooks ✅ (Strong)

- 23 runbooks indexed, 95% complete
- Categories: automation(4), infrastructure(14), lessons-learned(3), media(1), troubleshooting(1)

**Missing:**
- Proxmox VM management
- TrueNAS storage operations
- Talos node management
- Disaster recovery procedures

---

### 4. Alerting Pipeline ✅ (Fixed 2026-01-15)

**Current State:**
- AlertManager routing to alerting-pipeline webhook ✅
- alerting-pipeline receiving and processing alerts ✅
- Alerts forwarding to LangGraph for AI triage ✅
- End-to-end chain operational

**Verified Working:**
```
AlertManager (monit:10.30.0.20)
    → alerting-pipeline (agentic:31102/alert)
    → LangGraph/Claude-Agent
```

**Recent Alerts Processed:**
- KubeDeploymentReplicasMismatch, KubePodNotReady, KubeJobFailed
- NodeMemoryHighUtilization, KubeSchedulerDown, TargetDown

---

### 5. Matrix/Element ⚠️ (Deployed but Disconnected)

- Conduit server: Running
- Matrix bot: Running
- **Not receiving alerts** - wiring incomplete

---

### 6. AI Integration ⚠️ (Mostly Working)

| Component | Status |
|-----------|--------|
| LiteLLM | ✅ Running |
| Ollama | ✅ Available |
| Claude-Agent | ✅ Running (3 replicas) |
| Claude-Validator | ⚠️ Daily jobs failing |
| LangGraph | ✅ Running |

**Constraints:** Claude API limits, Gemini free tier, local LLM fallback

---

### 7. Self-Maintenance ❌ (Not Implemented)

**Missing:**
- Network Discovery CronJob not running
- Graph Sync Job not running
- Decision Logger not implemented
- Outcome Tracker not implemented
- Autonomy Progression not implemented

---

## Prioritized Roadmap

### 🔴 CRITICAL (This Week)

1. ~~**Fix AlertManager Routing**~~ - ✅ DONE (2026-01-15)
2. **Fix Node Memory** - 10.10.0.42 at 93.54%
3. **Fix Claude Validator** - Daily jobs failing

### 🟠 HIGH (This Month)

4. **Complete Alert → Matrix Chain** - End-to-end notification
5. **Implement Decision Logging** - Record all agent decisions
6. **Enable Network Discovery** - Auto-populate entities
7. **Create DR Runbook** - Disaster recovery procedures

### 🟡 MEDIUM (This Quarter)

8. **Implement Outcome Tracking** - Correlate actions with results
9. **Build Feedback Loop** - Learn from approvals/rejections
10. **Progressive Autonomy** - Trust levels for runbooks
11. **Index All Documentation** - Populate Qdrant

### 🟢 FUTURE (This Year)

12. **MCP Auto-Generation** - Detect and fill capability gaps
13. **Runbook Auto-Generation** - Patterns become procedures
14. **Skill Auto-Generation** - Repeated queries become commands

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────┐
│                 INFRASTRUCTURE                   │
│  ✅ Talos  ✅ K8s  ✅ Storage  ✅ Secrets        │
└─────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────┐
│                 MCP SERVERS (20)                 │
│  ✅ All deployed and healthy                    │
└─────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────┐
│                 KNOWLEDGE BASE                   │
│  ✅ Qdrant  ✅ Neo4j  ⚠️ Collections sparse     │
└─────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────┐
│                 INFERENCE LAYER                  │
│  ✅ LiteLLM  ✅ Gemini  ✅ Ollama  ⚠️ Validator │
└─────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────┐
│            ORCHESTRATION (LangGraph)             │
│  ✅ Deployed  ✅ Receiving alerts from AM      │
└─────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────┐
│           HUMAN-IN-THE-LOOP (Matrix)            │
│  ⚠️ Running  ⚠️ Needs verification            │
└─────────────────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────┐
│              LEARNING FEEDBACK LOOP              │
│  ❌ NOT IMPLEMENTED - Critical gap              │
└─────────────────────────────────────────────────┘
```

---

## Key Metrics at Audit Time

- **Deployments in ai-platform:** 30
- **MCP Servers:** 20 (all healthy)
- **Active Alerts:** 30+
- **Runbooks Indexed:** 23
- **Entities Tracked:** 127
- **Decisions Logged:** 1
- **Feedback Collected:** 0

---

## Path to Self-Maintenance

1. Wire up alerting (AlertManager → Pipeline → Matrix → User)
2. Implement decision logging (Every action recorded)
3. Track outcomes (Did the action fix the problem?)
4. Build feedback loop (Approvals update confidence)
5. Enable progressive autonomy (Runbooks graduate)

**Estimated effort to Phase 7:** 2-3 focused weekends
**Estimated effort to Phase 8:** 1-2 months after Phase 7

---

## References

- `/home/agentic_lab/PHASES.md` - Original 8-phase roadmap
- `/home/agentic_lab/CLAUDE.md` - Architecture documentation
- Vikunja Project: "Ecosystem Roadmap 2026" - Task tracking
- Knowledge Base: `search_documentation("ecosystem audit")`

---

*Generated by Claude Code audit on 2026-01-15*
