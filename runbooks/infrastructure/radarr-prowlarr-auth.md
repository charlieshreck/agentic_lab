---
title: Radarr-Prowlarr Authentication Issues
description: Troubleshooting Radarr unable to connect to Prowlarr (401 Unauthorized)
domain: media
severity: warning
---

# Radarr-Prowlarr Authentication Issues

## Symptom
RadarrHealthCheck alert fires indicating "All RSS-capable indexers are temporarily unavailable". Radarr logs show:
```
[Warn] Newznab: NZBgeek (Prowlarr) HTTP request failed: [401:Unauthorized]
[GET] http://prowlarr.media.svc.cluster.local:9696/2/api?t=caps&apikey=...
```

## Root Cause
API key mismatch between:
- **Infisical secret** (`/media/prowlarr/API_KEY`) - Source of truth
- **Prowlarr's actual key** in `config.xml` - Running configuration
- **Radarr's Prowlarr settings** - Using the Infisical key

This happens when:
1. Prowlarr's pod was running with a different/stale API key than what's in Infisical
2. The InfisicalSecret mount wasn't properly synced to the pod
3. Radarr is trying to authenticate using the Infisical key that doesn't match Prowlarr's actual config

## Solution

### Option 1: Update Infisical and Restart (Recommended - GitOps)
Source of truth approach: sync Infisical secret to Prowlarr pod.

```bash
# 1. Get the working API key from Prowlarr's config
kubectl exec -n media deployment/prowlarr -- \
  grep -oP '(?<=<ApiKey>)[^<]+' /config/config.xml

# 2. Update Infisical with the correct key
/root/.config/infisical/secrets.sh set /media/prowlarr API_KEY "<actual-key>"

# 3. Restart Prowlarr pod to regenerate config with updated secret
kubectl rollout restart deployment/prowlarr -n media

# 4. Restart Radarr pod to re-read Prowlarr connection settings
kubectl rollout restart deployment/radarr -n media
```

### Option 2: Manually Sync in Prowlarr UI (Quick but Not GitOps)
1. Port-forward to Prowlarr: `kubectl port-forward -n media svc/prowlarr 9696:9696`
2. Access `http://localhost:9696/settings/indexers`
3. Copy the API key shown at the bottom of the page
4. Update Infisical: `secrets.sh set /media/prowlarr API_KEY "<new-key>"`
5. Document the change in a commit

## Verification

After applying the fix:

```bash
# Check Radarr logs for successful Prowlarr authentication
kubectl logs -n media deployment/radarr --tail=50 | grep -E "(Prowlarr|401|indexer)"

# Should see:
# - NO 401 Unauthorized errors
# - Successful "Caps updated" messages
# - List of available indexers
```

## Prevention

1. **Treat Infisical as source of truth** for all API keys
2. **Never manually regenerate API keys** in Prowlarr UI - let InfisicalSecret manage it
3. **Add monitoring** to detect API key divergence between Infisical and running pods
4. **Document pod restart dependencies**:
   - Prowlarr pod restart → May affect Radarr/Sonarr
   - Radarr pod restart → No impact on others

## Related Files
- Prowlarr deployment: `/home/prod_homelab/kubernetes/applications/media/prowlarr/`
- Radarr deployment: `/home/prod_homelab/kubernetes/applications/media/radarr/`
- Infisical secrets: `/media/prowlarr/API_KEY`
- ConfigMap: `/home/prod_homelab/kubernetes/applications/media/configarr/configmap.yaml`

## Incident History
- **2026-03-14 21:30 UTC**: Incident #478 - API key mismatch resolved via Infisical update + pod restart
