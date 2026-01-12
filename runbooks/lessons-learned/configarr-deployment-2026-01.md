# Lessons Learned: Configarr Deployment

**Date**: 2026-01-12
**Project**: TRaSH Guides Sync for Sonarr/Radarr
**Outcome**: Successful

## Context

Deployed Configarr as a Kubernetes CronJob to automatically sync TRaSH Guides custom formats and quality profiles to Sonarr and Radarr, replacing the need for Notifiarr's paid TRaSH Guides integration.

## What Went Well

1. **Reused existing secrets** - Sonarr/Radarr API keys were already in Infisical, no new secrets needed
2. **Clean separation** - CronJob pattern keeps sync isolated from the arr apps
3. **GitOps workflow** - All manifests committed before deployment
4. **Quick iteration** - ArgoCD auto-sync allowed rapid fix deployment

## Issues Encountered

### 1. Config Mount Path (Fixed in 2 minutes)

**Problem**: Configarr failed with "Config file not found"
```
Error: Config file in location "/app/config/config.yml" does not exists.
```

**Cause**: Mounted config at `/app/config.yml` instead of `/app/config/config.yml`

**Fix**: Updated volumeMount path:
```yaml
volumeMounts:
- name: config
  mountPath: /app/config/config.yml  # NOT /app/config.yml
  subPath: config.yml
```

**Lesson**: Always check container documentation for expected paths. Don't assume `/app/<filename>` - many apps expect subdirectories.

### 2. Permission Denied for Repos Directory (Fixed in 3 minutes)

**Problem**: Configarr failed cloning repositories
```
Error: EACCES: permission denied, mkdir '/app/repos/recyclarr-config'
```

**Cause**: Running as non-root user (1000) with restricted security context, but `/app/repos` inside container image is owned by root.

**Fix**: Added emptyDir volume for writable workspace:
```yaml
volumeMounts:
- name: repos
  mountPath: /app/repos
volumes:
- name: repos
  emptyDir: {}
```

**Lesson**: When running containers as non-root with `readOnlyRootFilesystem: false`, still check if the app needs to write to specific directories. EmptyDir volumes solve this cleanly for ephemeral data.

### 3. ArgoCD Application Bootstrap

**Problem**: New ArgoCD Application wasn't automatically discovered

**Cause**: No app-of-apps pattern for prod_homelab applications - each app was manually applied

**Fix**: Applied ArgoCD Application manifest directly:
```bash
kubectl apply -f kubernetes/argocd-apps/applications/configarr-app.yaml
```

**Lesson**: Document the app bootstrap process. Consider implementing ApplicationSet for auto-discovery of new apps in the `argocd-apps/applications/` directory.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| CronJob over Deployment | Sync only needs to run periodically, not continuously |
| Daily at midnight | TRaSH Guides don't change frequently; daily is sufficient |
| Both 1080p and 4K profiles | Flexibility to choose per-show/movie without redeploying |
| TRaSH defaults only | Battle-tested scoring, avoid premature customization |
| emptyDir for repos | Ephemeral data, no persistence needed between runs |

## Configuration Patterns Discovered

### Configarr Config Structure
```yaml
sonarr:
  <instance-name>:        # Arbitrary name (e.g., "main", "4k")
    base_url: http://...
    api_key: !env VAR      # Environment variable reference
    include:
      - template: <name>   # From recyclarr/config-templates
    custom_formats: []     # Optional overrides
```

### Environment Variable Injection
Configarr supports `!env VAR_NAME` in YAML for secrets - cleaner than templating.

## Metrics

| Metric | Value |
|--------|-------|
| Time to working deployment | ~25 minutes |
| Commits for fixes | 2 |
| Custom Formats synced (Sonarr) | 33 |
| Custom Formats synced (Radarr) | 38 |
| Quality Profiles created | 4 |

## Future Improvements

1. **Add Anime profiles** - Include anime-specific TRaSH profiles for anime content
2. **Readarr/Lidarr support** - Configarr supports these experimentally
3. **Alerting** - Add notification on job failure (integrate with existing alerting)
4. **Resource monitoring** - Track job duration over time

## References

- [Configarr Documentation](https://configarr.de)
- [TRaSH Guides](https://trash-guides.info/)
- [Deployment PR/Commit](https://github.com/charlieshreck/prod_homelab/commit/a3c58c3)
- Runbook: `/home/agentic_lab/runbooks/media/configarr.md`
