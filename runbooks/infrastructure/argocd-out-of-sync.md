# ArgoCDOutOfSync Runbook

**Alert**: `ArgoCDOutOfSync` (from alerting-pipeline)
**Severity**: warning
**Source**: alerting-pipeline → KAO incident → estate finding

## Description

Fires when an ArgoCD application has `sync_status != Synced`. This means git state does not match
the live cluster. Health status can still be Healthy (synced objects are working, but git has changes
not yet applied).

## FIRST: Check Current State (Mandatory)

Before doing anything else, verify the ArgoCD app is **actually** OutOfSync right now:

```
mcp__infrastructure__argocd_get_applications
```

Look for the app name and check `sync_status`. If it shows `Synced` → **zombie incident pattern**
(see below). If it shows `OutOfSync` → investigate root cause.

---

## Case 1: App Currently Synced — Zombie Incident Pattern

**Symptoms:**
- ArgoCD shows `Synced` and `Healthy`
- Estate finding references a KAO incident in `investigating` status
- Incident has a `resolved_at` timestamp but `status` is still `"investigating"`
- Previous patrol session committed a fix but never called the resolve API

**Root Cause:**
A previous patrol session resolved the underlying issue (committed fix, confirmed sync) but did NOT
call the estate incident resolve endpoint. The incident stayed stuck in `"investigating"`, and the
next sweep generated a new estate finding from the zombie.

**Fix:**

1. Confirm ArgoCD is Synced+Healthy (already done in FIRST step)
2. Close the zombie KAO incident:
   ```bash
   curl -s -X POST http://10.10.0.22:3456/webhook/screen-resolve \
     -H 'Content-Type: application/json' \
     -d '{"type":"incident","id":<INCIDENT_ID>,"summary":"Zombie closed - ArgoCD Synced+Healthy. Underlying fix was <commit>. Incident had resolved_at but status stuck in investigating."}'
   ```
3. Resolve the finding as false positive:
   ```bash
   curl -s -X POST http://10.10.0.22:3456/webhook/screen-resolve \
     -H 'Content-Type: application/json' \
     -d '{"type":"finding","id":<FINDING_ID>,"summary":"...","resolution_type":"fp"}'
   ```

**Critical Rule:** Whenever patrol resolves an ArgoCD OutOfSync finding, **always** close the KAO
incident too (not just the estate finding). Failing to do so creates a zombie that generates new
findings on future sweeps.

**History:**
| Date | Incident | App | Cause |
|------|----------|-----|-------|
| 2026-02-24 | #224 | prometheus-rules | Invalid PromQL, fix applied 2026-03-02 (b17e8ae), zombie closed 2026-03-03 |
| 2026-02-26 | #208 | litellm@ai-platform | Coroot alert self-healed, incident stuck in investigating |

---

## Case 2: App Actually OutOfSync — Investigate Root Cause

**Step 1: Describe the ArgoCD Application**
```
mcp__infrastructure__kubectl_describe(resource_type=application, name=<app>, namespace=argocd, cluster=prod)
```
Look at:
- `Sync Status` → which resources differ
- `Operation State` → last sync attempt details
- `Error` → any sync error messages

**Step 2: Read the Git Manifest**
Check the manifest path from the ArgoCD app definition:
```bash
cat /home/<repo>/kubernetes/<path>/<resource>.yaml
```
Look for YAML syntax errors, invalid expressions, or schema violations.

**Step 3: Identify Resource Type**

| Resource Type | Common Causes | Fix |
|---------------|---------------|-----|
| `PrometheusRule` | Invalid PromQL (syntax/semantics) | Fix expression, commit |
| `ConfigMap` | Content drift from live edits | Recommit correct config |
| `CRD` | Schema changed upstream | Update API version |
| `Deployment` | Image tag drift | Update image spec |
| `ignoreDifferences` needed | ArgoCD syncs runtime fields (status, etc.) | Add ignoreDifferences |

**Step 4: Fix and Commit (GitOps — Never kubectl apply)**

```bash
# Example: fix a PrometheusRule PromQL error
nano /home/monit_homelab/kubernetes/platform/prometheus-rules/homelab-rules.yaml
git -C /home/monit_homelab add kubernetes/platform/prometheus-rules/homelab-rules.yaml
git -C /home/monit_homelab commit -m "fix: correct invalid PromQL in <rule-name>"
git -C /home/monit_homelab push origin main
```

**Step 5: Wait and Verify**

ArgoCD auto-syncs within ~3 minutes. Verify:
```
mcp__infrastructure__argocd_get_applications → prometheus-rules shows Synced+Healthy
```

---

## PromQL Operator Precedence (prometheus-rules specific)

**Lesson from Incident #224 (2026-02-24):**

The `*` operator has higher precedence than `>` in PromQL. Without parentheses:
```promql
# WRONG — parsed as: metric > (0 * on(pod,ns) group_left() vector)
kube_pod_container_status_last_terminated_reason{reason="OOMKilled"} > 0 * on(pod, namespace) group_left() vector(1)
```

`0 * on(pod, namespace) group_left() vector` is invalid because `on()`/`group_left()` require
vector-to-vector operations, not scalar-to-vector.

```promql
# CORRECT — parentheses force right grouping
(kube_pod_container_status_last_terminated_reason{reason="OOMKilled"} > 0) * on(pod, namespace) group_left() (kube_pod_status_phase{phase="Running"} == 1)
```

**Rule:** When using `on()`/`group_left()` after a comparison, **always parenthesize the comparison**:
`(metric > threshold) * on(...) group_left() other_vector`

---

## Resolution Checklist

When closing an ArgoCDOutOfSync finding, always complete ALL of these:

- [ ] Verify current ArgoCD state (Synced? OutOfSync?)
- [ ] If OutOfSync: identify and fix the root cause (GitOps commit)
- [ ] Wait for ArgoCD sync, confirm Synced+Healthy
- [ ] Resolve the **estate finding** via `screen-resolve` (type: finding)
- [ ] **ALSO close the KAO incident** via `screen-resolve` (type: incident)
- [ ] Log event to knowledge base (`mcp__knowledge__log_event`)

---

## History

| Date | App | Root Cause | Fix |
|------|-----|-----------|-----|
| 2026-02-24 | prometheus-rules | HomelabPodOOMKilled: invalid PromQL operator precedence (`> 0 *` parsed wrong) | Added parentheses, commit b17e8ae (2026-03-02) |
| 2026-03-03 | prometheus-rules | Finding #994 from zombie incident #224 (patrol didn't close incident in DB) | Closed zombie, resolved as FP |
