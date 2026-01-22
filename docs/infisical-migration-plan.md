# Infisical Migration Plan

> **Goal**: Migrate from ad-hoc Infisical structure to canonical domain-aligned structure.
> **Target Date**: TBD
> **Risk Level**: Medium (requires coordinated updates across all clusters)

---

## Executive Summary

| Metric | Count |
|--------|-------|
| Total InfisicalSecret CRDs | 72 |
| Agentic cluster | 39 |
| Prod cluster | 32 |
| Monit cluster | 1 |
| Paths requiring migration | ~25 |
| Paths already correct | ~15 |

---

## Path Migration Map

### Legend
- **KEEP**: Path already matches new structure or is close enough
- **MIGRATE**: Path needs to change to new structure
- **DELETE**: Path is duplicate/obsolete after migration
- **MERGE**: Multiple old paths merge into one new path

---

### /infrastructure (Physical/Virtual Infrastructure)

| Old Path | New Path | Action | Consumers |
|----------|----------|--------|-----------|
| `/infrastructure/proxmox` | `/infrastructure/proxmox-ruapehu` | MIGRATE | mcp-proxmox, homepage-proxmox |
| `/monitoring/proxmox` | `/infrastructure/proxmox-carrick` | MIGRATE | homepage-proxmox-carrick |
| `/infrastructure/opnsense` | `/infrastructure/opnsense` | KEEP | mcp-opnsense, homepage-opnsense |
| `/infrastructure/adguard` | `/infrastructure/adguard` | KEEP | mcp-adguard, homepage-adguard |
| `/apps/truenas/truenas-hdd` | `/infrastructure/truenas-hdd` | MIGRATE | mcp-truenas-hdd, homepage-truenas-hdd |
| `/apps/truenas/truenas-media` | `/infrastructure/truenas-media` | MIGRATE | mcp-truenas-media, homepage-truenas-media |
| `/` (cloudflare secrets at root) | `/infrastructure/cloudflare` | MIGRATE | mcp-cloudflare, cloudflare-api-token, cloudflare-api |
| `/kubernetes` (tunnel token) | `/infrastructure/cloudflare` | MERGE | cloudflared-tunnel |
| `/agentic-platform/infisical` | `/infrastructure/infisical` | MIGRATE | infisical-universal-auth-sync, mcp-infisical |
| `/mcp/infrastructure` | DELETE | DELETE | infrastructure-mcp-secrets (update to reference individual paths) |

### /observability (Monitoring & Alerting)

| Old Path | New Path | Action | Consumers |
|----------|----------|--------|-----------|
| `/agentic-platform/keep` | `/observability/keep` | MIGRATE | keep-api-key-sync, mcp-keep |
| `/monitoring/grafana` | `/observability/grafana` | MIGRATE | mcp-monitoring-grafana, homepage-grafana |
| `/monitoring/coroot` | `/observability/coroot` | MIGRATE | coroot-agent-apikey |
| `/monitoring/argocd` | `/platform/argocd` | MIGRATE | homepage-argocd |
| `/monitoring/beszel` | `/observability/beszel` | MIGRATE | homepage-beszel |
| `/mcp/observability` | DELETE | DELETE | observability-mcp-secrets (update to reference individual paths) |

### /knowledge (Data & Knowledge Systems)

| Old Path | New Path | Action | Consumers |
|----------|----------|--------|-----------|
| `/agentic-platform/neo4j` | `/knowledge/neo4j` | MIGRATE | neo4j-infisical |
| `/agentic-platform/outline` | `/knowledge/outline` | MIGRATE | outline-infisical |
| `/agentic-platform/outline-mcp` | DELETE | MERGE into `/knowledge/outline` | mcp-outline |
| `/apps/vikunja` | `/knowledge/vikunja` | MIGRATE | mcp-vikunja |
| `/agentic-platform/postgresql` | `/knowledge/postgresql` | MIGRATE | postgresql-infisical |
| `/mcp/knowledge` | DELETE | DELETE | knowledge-mcp-secrets (update to reference individual paths) |

### /home (Smart Home & Network)

| Old Path | New Path | Action | Consumers |
|----------|----------|--------|-----------|
| `/apps/homeassistant` | `/home/homeassistant` | MIGRATE | mcp-homeassistant, homepage-homeassistant, matter-hub-secrets |
| `/apps/unifi` | `/home/unifi` | MIGRATE | mcp-unifi, homepage-unifi |
| `/apps/mqtt` | `/home/mqtt` | MIGRATE | mosquitto-credentials |

### /media (Media Management)

| Old Path | New Path | Action | Consumers |
|----------|----------|--------|-----------|
| `/media/plex` | `/media/plex` | KEEP | mcp-plex |
| `/media/sonarr` | `/media/sonarr` | KEEP | mcp-sonarr, homepage-sonarr, sonarr-credentials |
| `/media/radarr` | `/media/radarr` | KEEP | mcp-radarr, homepage-radarr, radarr-credentials |
| `/media/prowlarr` | `/media/prowlarr` | KEEP | mcp-prowlarr, homepage-prowlarr, prowlarr-credentials |
| `/media/overseerr` | `/media/overseerr` | KEEP | mcp-overseerr, homepage-overseerr |
| `/media/tautulli` | `/media/tautulli` | KEEP | mcp-tautulli, homepage-tautulli, tautulli-credentials |
| `/media/transmission` | `/media/transmission` | KEEP | mcp-transmission, homepage-transmission, transmission-credentials |
| `/media/sabnzbd` | `/media/sabnzbd` | KEEP | mcp-sabnzbd, homepage-sabnzbd |
| `/media/notifiarr` | `/media/notifiarr` | KEEP | notifiarr-api |
| `/agentic-platform/plex` | MERGE | MERGE into `/media/plex` | plex-mcp-ssh-infisical |

### /external (External APIs)

| Old Path | New Path | Action | Consumers |
|----------|----------|--------|-----------|
| `/agentic-platform/github` | `/external/github` | MIGRATE | mcp-github |
| `/agentic-platform/openrouter` | `/external/openrouter` | MIGRATE | openrouter-credentials |
| `/agentic-platform/Gemini` | `/external/gemini` | MIGRATE | gemini-credentials |
| `/agentic-platform/gemini` | MERGE | MERGE into `/external/gemini` | gemini-oauth-credentials-sync |

### /platform (Cross-Cutting Services)

| Old Path | New Path | Action | Consumers |
|----------|----------|--------|-----------|
| `/monitoring/argocd` | `/platform/argocd` | MIGRATE | homepage-argocd |
| `/agentic-platform/matrix` | `/platform/matrix` | MIGRATE | matrix-bot-credentials |
| `/agentic-platform/mcp-config-sync` | `/platform/mcp-config-sync` | MIGRATE | mcp-config-sync-kubeconfig, mcp-config-sync-secrets |
| `/agentic-platform/claude` | `/platform/claude` | MIGRATE | claude-credentials, claude-validator-credentials |

### /backups (Backup Infrastructure)

| Old Path | New Path | Action | Consumers |
|----------|----------|--------|-----------|
| `/backups/garage` | `/backups/garage` | KEEP | backup-s3-infisical |
| `/backups` (velero) | `/backups/velero` | MIGRATE | velero-minio-credentials, velero-garage-credentials |
| `/infrastructure` (renovate) | `/platform/renovate` | MIGRATE | renovate-credentials |

### Paths to Delete (Orphaned/Duplicate)

| Path | Reason |
|------|--------|
| `/apps/glasskeep` | Check if still needed |
| `/apps/karakeep` | Check if still needed |
| `/apps/truenas` (empty folder) | Reorganized to /infrastructure |
| `/agentic-platform/*` (entire folder) | All migrated to domain folders |
| `/mcp/*` (entire folder) | Duplicates removed |
| `/monitoring/*` (entire folder) | All migrated to /observability or /platform |

---

## Consumer Update Matrix

### Agentic Cluster (ai-platform namespace)

| InfisicalSecret | Current Path | New Path | File Location |
|-----------------|--------------|----------|---------------|
| `backup-s3-infisical` | `/backups/garage` | `/backups/garage` | KEEP |
| `claude-credentials` | `/agentic-platform/claude` | `/platform/claude` | kubernetes/applications/*/infisical-secrets.yaml |
| `gemini-credentials` | `/agentic-platform/Gemini` | `/external/gemini` | kubernetes/applications/litellm/infisical-secrets.yaml |
| `gemini-oauth-credentials-sync` | `/agentic-platform/gemini` | `/external/gemini` | kubernetes/applications/*/infisical-secrets.yaml |
| `infisical-universal-auth-sync` | `/agentic-platform/infisical` | `/infrastructure/infisical` | kubernetes/applications/mcp-servers/infisical-secrets.yaml |
| `infrastructure-mcp-secrets` | `/mcp/infrastructure` | (multiple paths) | mcp-servers/kubernetes/domains/infrastructure.yaml |
| `keep-api-key-sync` | `/agentic-platform/keep` | `/observability/keep` | kubernetes/applications/keep/infisical-secret.yaml |
| `knowledge-mcp-secrets` | `/mcp/knowledge` | (multiple paths) | mcp-servers/kubernetes/domains/knowledge.yaml |
| `matrix-bot-credentials` | `/agentic-platform/matrix` | `/platform/matrix` | kubernetes/applications/matrix-bot/infisical-secrets.yaml |
| `mcp-adguard` | `/infrastructure/adguard` | `/infrastructure/adguard` | KEEP |
| `mcp-cloudflare` | `/` | `/infrastructure/cloudflare` | kubernetes/applications/mcp-servers/infisical-secrets.yaml |
| `mcp-config-sync-*` | `/agentic-platform/mcp-config-sync` | `/platform/mcp-config-sync` | kubernetes/applications/mcp-config-sync/infisical-secrets.yaml |
| `mcp-github` | `/agentic-platform/github` | `/external/github` | kubernetes/applications/mcp-servers/infisical-secrets.yaml |
| `mcp-homeassistant` | `/apps/homeassistant` | `/home/homeassistant` | kubernetes/applications/mcp-servers/infisical-secrets.yaml |
| `mcp-infisical` | `/agentic-platform/infisical` | `/infrastructure/infisical` | kubernetes/applications/mcp-servers/infisical-secrets.yaml |
| `mcp-keep` | `/agentic-platform/keep` | `/observability/keep` | kubernetes/applications/mcp-servers/infisical-secrets.yaml |
| `mcp-monitoring-grafana` | `/monitoring/grafana` | `/observability/grafana` | kubernetes/applications/mcp-servers/infisical-secrets.yaml |
| `mcp-opnsense` | `/infrastructure/opnsense` | `/infrastructure/opnsense` | KEEP |
| `mcp-outline` | `/agentic-platform/outline-mcp` | `/knowledge/outline` | kubernetes/applications/mcp-servers/infisical-secrets.yaml |
| `mcp-overseerr` | `/media/overseerr` | `/media/overseerr` | KEEP |
| `mcp-plex` | `/media/plex` | `/media/plex` | KEEP |
| `mcp-prowlarr` | `/media/prowlarr` | `/media/prowlarr` | KEEP |
| `mcp-proxmox` | `/infrastructure/proxmox` | `/infrastructure/proxmox-ruapehu` | kubernetes/applications/mcp-servers/infisical-secrets.yaml |
| `mcp-radarr` | `/media/radarr` | `/media/radarr` | KEEP |
| `mcp-sabnzbd` | `/media/sabnzbd` | `/media/sabnzbd` | KEEP |
| `mcp-sonarr` | `/media/sonarr` | `/media/sonarr` | KEEP |
| `mcp-tautulli` | `/media/tautulli` | `/media/tautulli` | KEEP |
| `mcp-transmission` | `/media/transmission` | `/media/transmission` | KEEP |
| `mcp-truenas-hdd` | `/apps/truenas/truenas-hdd` | `/infrastructure/truenas-hdd` | kubernetes/applications/mcp-servers/infisical-secrets.yaml |
| `mcp-truenas-media` | `/apps/truenas/truenas-media` | `/infrastructure/truenas-media` | kubernetes/applications/mcp-servers/infisical-secrets.yaml |
| `mcp-unifi` | `/apps/unifi` | `/home/unifi` | kubernetes/applications/mcp-servers/infisical-secrets.yaml |
| `mcp-vikunja` | `/apps/vikunja` | `/knowledge/vikunja` | kubernetes/applications/mcp-servers/infisical-secrets.yaml |
| `neo4j-infisical` | `/agentic-platform/neo4j` | `/knowledge/neo4j` | kubernetes/applications/neo4j/secret.yaml |
| `observability-mcp-secrets` | `/mcp/observability` | (multiple paths) | mcp-servers/kubernetes/domains/observability.yaml |
| `openrouter-credentials` | `/agentic-platform/openrouter` | `/external/openrouter` | kubernetes/applications/litellm/infisical-secrets.yaml |
| `outline-infisical` | `/agentic-platform/outline` | `/knowledge/outline` | kubernetes/applications/outline/infisical-secret.yaml |
| `plex-mcp-ssh-infisical` | `/agentic-platform/plex` | `/media/plex` | kubernetes/applications/mcp-servers/plex-mcp.yaml |
| `postgresql-infisical` | `/agentic-platform/postgresql` | `/knowledge/postgresql` | kubernetes/applications/postgresql/secret.yaml |

### Prod Cluster

| InfisicalSecret | Current Path | New Path | File Location |
|-----------------|--------------|----------|---------------|
| `homepage-adguard` | `/infrastructure/adguard` | `/infrastructure/adguard` | KEEP |
| `homepage-argocd` | `/monitoring/argocd` | `/platform/argocd` | kubernetes/applications/apps/homepage/infisical-secrets.yaml |
| `homepage-beszel` | `/monitoring/beszel` | `/observability/beszel` | kubernetes/applications/apps/homepage/infisical-secrets.yaml |
| `homepage-grafana` | `/monitoring/grafana` | `/observability/grafana` | kubernetes/applications/apps/homepage/infisical-secrets.yaml |
| `homepage-homeassistant` | `/apps/homeassistant` | `/home/homeassistant` | kubernetes/applications/apps/homepage/infisical-secrets.yaml |
| `homepage-opnsense` | `/infrastructure/opnsense` | `/infrastructure/opnsense` | KEEP |
| `homepage-overseerr` | `/media/overseerr` | `/media/overseerr` | KEEP |
| `homepage-prowlarr` | `/media/prowlarr` | `/media/prowlarr` | KEEP |
| `homepage-proxmox` | `/infrastructure/proxmox` | `/infrastructure/proxmox-ruapehu` | kubernetes/applications/apps/homepage/infisical-secrets.yaml |
| `homepage-proxmox-carrick` | `/monitoring/proxmox` | `/infrastructure/proxmox-carrick` | kubernetes/applications/apps/homepage/infisical-secrets.yaml |
| `homepage-radarr` | `/media/radarr` | `/media/radarr` | KEEP |
| `homepage-sabnzbd` | `/media/sabnzbd` | `/media/sabnzbd` | KEEP |
| `homepage-sonarr` | `/media/sonarr` | `/media/sonarr` | KEEP |
| `homepage-tautulli` | `/media/tautulli` | `/media/tautulli` | KEEP |
| `homepage-transmission` | `/media/transmission` | `/media/transmission` | KEEP |
| `homepage-truenas-hdd` | `/apps/truenas/truenas-hdd` | `/infrastructure/truenas-hdd` | kubernetes/applications/apps/homepage/infisical-secrets.yaml |
| `homepage-truenas-media` | `/apps/truenas/truenas-media` | `/infrastructure/truenas-media` | kubernetes/applications/apps/homepage/infisical-secrets.yaml |
| `homepage-unifi` | `/apps/unifi` | `/home/unifi` | kubernetes/applications/apps/homepage/infisical-secrets.yaml |
| `cloudflare-api-token` | `/` | `/infrastructure/cloudflare` | kubernetes/platform/cert-manager/resources/cloudflare-api-token-secret.yaml |
| `cloudflared-tunnel` | `/kubernetes` | `/infrastructure/cloudflare` | kubernetes/platform/cloudflared/*.yaml |
| `cloudflare-api` | `/` | `/infrastructure/cloudflare` | kubernetes/platform/cloudflare-tunnel-controller/*.yaml |
| `coroot-agent-apikey` | `/monitoring/coroot` | `/observability/coroot` | kubernetes/platform/coroot-agent/*.yaml |
| `notifiarr-api` | `/media/notifiarr` | `/media/notifiarr` | KEEP |
| `mosquitto-credentials` | `/apps/mqtt` | `/home/mqtt` | kubernetes/applications/apps/mosquitto/*.yaml |
| `renovate-credentials` | `/infrastructure` | `/platform/renovate` | kubernetes/applications/apps/renovate/*.yaml |
| Various media credentials | `/media/*` | `/media/*` | KEEP |

### Monit Cluster

| InfisicalSecret | Current Path | New Path | File Location |
|-----------------|--------------|----------|---------------|
| `velero-garage-credentials` | `/backups` | `/backups/velero` | kubernetes/velero/*.yaml |

---

## Migration Phases

### Phase 0: Preparation (No Service Impact)
**Duration**: 1-2 hours
**Risk**: None

1. Create new folder structure in Infisical
2. Copy all secrets to new paths (don't delete old yet)
3. Verify all secrets copied correctly
4. Document any secrets that need key name changes

```bash
# Create new folders
/root/.config/infisical/secrets.sh mkdir / infrastructure
/root/.config/infisical/secrets.sh mkdir /infrastructure proxmox-ruapehu
/root/.config/infisical/secrets.sh mkdir /infrastructure proxmox-carrick
/root/.config/infisical/secrets.sh mkdir /infrastructure truenas-hdd
/root/.config/infisical/secrets.sh mkdir /infrastructure truenas-media
/root/.config/infisical/secrets.sh mkdir /infrastructure cloudflare
# ... etc for all paths

# Copy secrets (example)
OLD=$(/root/.config/infisical/secrets.sh get /infrastructure/proxmox TOKEN_ID)
/root/.config/infisical/secrets.sh set /infrastructure/proxmox-ruapehu TOKEN_ID "$OLD"
# ... etc
```

### Phase 1: Update Domain MCPs (Low Risk)
**Duration**: 1 hour
**Risk**: Low (MCPs will restart, brief tool unavailability)

Update domain MCP InfisicalSecret CRDs to reference new paths:

1. `infrastructure-mcp` → Update to fetch from multiple `/infrastructure/*` paths
2. `observability-mcp` → Update to fetch from `/observability/*` paths
3. `knowledge-mcp` → Update to fetch from `/knowledge/*` paths
4. `home-mcp` → Update to fetch from `/home/*` paths
5. `media-mcp` → Already correct, no changes needed
6. `external-mcp` → Update to fetch from `/external/*` paths

Commit, push, let ArgoCD sync.

### Phase 2: Update Agentic Cluster Apps (Medium Risk)
**Duration**: 2-3 hours
**Risk**: Medium (apps may restart)

Update all InfisicalSecret CRDs in `agentic_lab/kubernetes/applications/`:

1. Update paths in YAML files
2. Commit and push
3. Let ArgoCD sync
4. Verify secrets are syncing correctly

### Phase 3: Update Prod Cluster Apps (Medium Risk)
**Duration**: 2-3 hours
**Risk**: Medium (Homepage will restart)

Update all InfisicalSecret CRDs in `prod_homelab/kubernetes/applications/`:

1. Focus on Homepage first (most consumers)
2. Update cloudflare/cert-manager
3. Update remaining apps
4. Verify all services healthy

### Phase 4: Update Monit Cluster (Low Risk)
**Duration**: 30 minutes
**Risk**: Low (only Velero)

Update Velero credentials in monit cluster.

### Phase 5: Cleanup (Low Risk)
**Duration**: 1 hour
**Risk**: Low (deleting unused paths)

1. Verify no InfisicalSecret CRDs reference old paths
2. Delete old Infisical paths:
   - `/agentic-platform/*`
   - `/mcp/*`
   - `/monitoring/*`
   - `/apps/*`
   - `/kubernetes`
   - Root-level cloudflare secrets
3. Remove old individual MCP manifests from kustomization

### Phase 6: Documentation & Validation
**Duration**: 1 hour

1. Update CLAUDE.md files with new paths
2. Update any runbooks referencing Infisical paths
3. Run full validation of all services
4. Update knowledge base

---

## Rollback Plan

If migration fails at any phase:

1. **Immediate**: Old paths still exist, revert InfisicalSecret CRD changes
2. **Git revert**: `git revert <commit>` and push
3. **ArgoCD sync**: Force sync to apply reverted manifests
4. **Verify**: Check all services healthy

Old secrets are NOT deleted until Phase 5, so rollback is safe until then.

---

## Validation Checklist

After each phase, verify:

- [ ] All InfisicalSecret CRDs show `Synced` status
- [ ] Kubernetes secrets exist with correct data
- [ ] Domain MCPs respond on `/health` endpoints
- [ ] Claude Code can invoke MCP tools
- [ ] Homepage dashboard loads all widgets
- [ ] No errors in Infisical operator logs

```bash
# Check InfisicalSecret status
kubectl get infisicalsecret -A

# Check MCP health
curl http://infrastructure-mcp.agentic.kernow.io/health
curl http://observability-mcp.agentic.kernow.io/health
curl http://knowledge-mcp.agentic.kernow.io/health
curl http://home-mcp.agentic.kernow.io/health
curl http://media-mcp.agentic.kernow.io/health
curl http://external-mcp.agentic.kernow.io/health

# Check Infisical operator logs
kubectl logs -n infisical-operator-system -l app=infisical-operator --tail=50
```

---

## Notes

- Migration should be done during low-usage period
- Keep terminal open with `kubectl get pods -A -w` to monitor
- Have Infisical web UI open for quick verification
- Backup current Infisical state before starting (export if possible)
