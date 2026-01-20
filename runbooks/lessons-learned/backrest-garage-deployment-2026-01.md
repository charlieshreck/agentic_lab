# Lessons Learned: Backrest & Garage Deployment (January 2026)

## Overview

This document captures lessons learned during the backup infrastructure redesign, including Garage S3 deployment, Backrest configuration, and Velero migration.

## Key Discoveries

### 1. Agentic Cluster Has Its Own Traefik LoadBalancer

**Discovery**: The agentic cluster has a fully functional Traefik LoadBalancer at **10.20.0.90**, assigned via Cilium LB IPAM.

**Why It Was Missed**:
- Initial documentation focused on the Caddy + AdGuard pattern for agentic services
- Traefik LB wasn't documented in domain-routing.md
- Assumption that only prod cluster had a Traefik LB

**Impact**:
- Backrest was initially deployed with NodePort only
- Required adding an Ingress resource to use the LB
- Several other services could benefit from this pattern

**Resolution**:
- Created new "Agentic Traefik Pattern" as **PREFERRED** for agentic internal services
- Updated domain-routing.md with comprehensive DNS rewrite reference
- Created new runbook: `new-app-agentic-traefik.md`

**Traefik LB Details**:
```yaml
Namespace:  traefik
Service:    traefik
Type:       LoadBalancer
IP:         10.20.0.90
Ports:      80 (web), 443 (websecure), 8080 (admin)
Assignment: Cilium LB IPAM (label: io.cilium/lb-ipam-ips=traefik)
```

### 2. Garage Layout Configuration Required Post-Install

**Discovery**: Garage requires explicit layout configuration after deployment before it becomes operational.

**Symptoms**:
- S3 API returns errors about "layout not ready"
- Cannot create buckets or perform operations
- Container appears running but not functional

**Resolution**:
```bash
# Get node ID
NODE_ID=$(curl -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://10.20.0.103:30190/v1/status | jq -r '.node')

# Assign storage capacity
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  http://10.20.0.103:30190/v1/layout \
  -d "{\"node_id\": \"$NODE_ID\", \"zone\": \"dc1\", \"capacity\": 10000000000000}"

# Apply layout
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://10.20.0.103:30190/v1/layout/apply \
  -d '{"version": 1}'
```

**Documentation**: Added to `garage-operations.md` troubleshooting section.

### 3. TrueNAS SCALE App Shell Access Can Be Unreliable

**Discovery**: OCI exec errors can occur when trying to access TrueNAS SCALE app shells via the UI.

**Workaround**: Use the Admin API directly instead of shell access:
- Admin API at port 30190 provides full management capabilities
- Can perform all configuration via REST calls
- More reliable than container shell access

### 4. Four Distinct Routing Patterns for kernow.io

**Discovery**: The homelab uses four routing patterns, not just two:

| Pattern | DNS Target | Proxy | Use Case |
|---------|-----------|-------|----------|
| Dual-Ingress (Prod) | auto via wildcard | Traefik + CF | Prod apps with internal + external access |
| **Agentic Traefik** | **10.20.0.90** | **Traefik** | **Agentic internal services (PREFERRED)** |
| External Bridge | via Cloudflare | CF Tunnel | Agentic apps needing internet access |
| Caddy + AdGuard | 10.10.0.1 | Caddy | Custom proxy needs, legacy |

**Key Insight**: The Agentic Traefik pattern was undocumented and is simpler than Caddy for standard services.

### 5. DNS Rewrites Already Configured for Traefik LB

**Discovery**: Many AdGuard DNS rewrites already point to 10.20.0.90:
- backrest.kernow.io → 10.20.0.90
- keep.kernow.io → 10.20.0.90
- vikunja.kernow.io → 10.20.0.90
- matrix.kernow.io → 10.20.0.90
- outline.kernow.io → 10.20.0.90
- fumadocs.kernow.io → 10.20.0.90
- langgraph.kernow.io → 10.20.0.90

**Implication**: These services need Traefik Ingress resources, not just NodePort services.

### 6. Backrest SSH Configuration Details

**Discovery**: Backrest connects to backup targets via SSH using keys mounted from Kubernetes secrets.

**Key Files**:
- SSH config: `/root/.ssh/config` (mounted from secret)
- SSH key: `/root/.ssh/id_ed25519` (mounted from secret)
- Public key stored in Infisical: `/backups/backrest`

**Adding New Backup Target**:
1. Install SSH key on target: `echo '<public_key>' >> /root/.ssh/authorized_keys`
2. Update SSH config secret with new host entry
3. Commit and sync via ArgoCD
4. Create backup plan in Backrest UI

### 7. MinIO Licensing Changes

**Discovery**: MinIO licensing changed, making it problematic for homelab use.

**Resolution**: Replaced MinIO with Garage:
- Lighter weight (single binary)
- No licensing concerns
- S3-compatible for Velero and restic
- Runs well on TrueNAS SCALE

### 8. Kubernetes VMs Don't Need File-Level Backups

**Discovery**: Talos Kubernetes VMs (400-403) do NOT need file-level backups because:
- Talos OS is immutable - rebuilt from machine configs stored in git
- No persistent state on nodes
- PVC data is backed up by Velero separately
- Cluster can be rebuilt from Terraform + Talos configs

**What DOES Need Backup**: K8s workloads = manifests (in git) + PVC data (Velero)

## Process Improvements

### 1. Always Check for Existing LoadBalancers

Before creating new routing patterns, verify what infrastructure already exists:
```bash
kubectl get svc -A | grep LoadBalancer
```

### 2. Document All Routing Patterns

When adding new services, explicitly document which routing pattern is used and why.

### 3. Use Helper Scripts for Submodule Commits

Always use `/home/scripts/git-commit-submodule.sh` to avoid:
- Committing in wrong directory (parent vs submodule)
- Forgetting to update parent submodule reference
- Push failures from incorrect working directory

### 4. Verify DNS Before Adding Ingress

Check existing DNS rewrites before adding new services:
```bash
# Via MCP
adguard-mcp: adguard_list_rewrites()

# Or via AdGuard UI
https://adguard.kernow.io → Filters → DNS rewrites
```

## Artifacts Created

### New Runbooks
- `/home/agentic_lab/runbooks/infrastructure/new-app-agentic-traefik.md`
- `/home/agentic_lab/runbooks/infrastructure/garage-operations.md`
- `/home/agentic_lab/runbooks/infrastructure/backup-overview.md`

### Updated Documentation
- `/home/agentic_lab/docs/knowledge-base/domain-routing.md`
- `/home/agentic_lab/runbooks/infrastructure/backrest-operations.md`

### Infrastructure Changes
- Added Traefik Ingress to Backrest deployment
- Migrated Velero from MinIO to Garage
- Configured 4 Backrest backup plans

## Checklist for Future Deployments

### New Agentic Service (Internal Only)
- [ ] Deploy to agentic cluster
- [ ] Create ClusterIP or NodePort service
- [ ] Add Traefik Ingress (ingressClassName: traefik)
- [ ] Add AdGuard DNS rewrite → 10.20.0.90
- [ ] Commit via git-commit-submodule.sh
- [ ] Sync ArgoCD
- [ ] Verify via `curl https://<service>.kernow.io`

### New Backup Target for Backrest
- [ ] Install SSH public key on target host
- [ ] Update SSH config secret in Kubernetes
- [ ] Commit and sync
- [ ] Create backup plan in Backrest UI
- [ ] Run initial backup manually
- [ ] Verify snapshot appears in UI

## Related Resources

- Plan file: `/root/.claude/plans/cheerful-sparking-lake.md`
- Backup overview: `/home/agentic_lab/runbooks/infrastructure/backup-overview.md`
- Domain routing: `/home/agentic_lab/docs/knowledge-base/domain-routing.md`
- Infisical secrets: `/backups/garage`, `/backups/backrest`
