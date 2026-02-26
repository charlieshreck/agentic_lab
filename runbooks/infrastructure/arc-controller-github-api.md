# ARC Controller GitHub API 404 Troubleshooting

## Pattern
- ArgoCD app `arc-controller` shows "Unknown" status
- Pod in `arc-systems` namespace shows multiple restarts (4+)
- Logs contain: `github api error: StatusCode 404` when refreshing runner registration token
- Alert: `ArgoCDAppOutOfSync` fires and clears as pod cycles

## Root Cause
The `arc-runner-set` (in `arc-runners` namespace) is attempting to register GitHub Actions runners with the GitHub organization, but the API request is returning 404 Not Found. This typically indicates:

1. **Invalid/Expired Token**: GitHub token in Infisical `/platform/arc` is no longer valid
2. **Missing Permissions**: Token lacks `admin:org_hook` and `public_repo` scopes required for runner registration
3. **Organization Issue**: Organization `charlieshreck` doesn't have self-hosted runner permission
4. **API Changes**: GitHub has made breaking changes to the runner registration API

## Investigation Steps

### 1. Verify Secret Exists
```bash
kubectl get secret -n arc-runners arc-github-token
# Should show: arc-github-token, Opaque, github_token key
```

### 2. Check Pod Logs
```bash
kubectl logs -n arc-systems deployment/arc-controller-gha-rs-controller --tail=100
# Look for: "failed to get runner registration token"
# Extract RequestID and note the GitHub error message
```

### 3. Verify GitHub Token Validity
```bash
# 1. Get the token from Infisical (if you have access):
/root/.config/infisical/secrets.sh get /platform/arc GITHUB_TOKEN

# 2. Test token by checking GitHub API:
curl -H "Authorization: token YOUR_TOKEN" \
  https://api.github.com/orgs/charlieshreck/actions/runners/registration-token \
  -X POST

# Expected: 200 OK with token in response
# Actual: 404 means org doesn't exist or token lacks permissions
# Actual: 401 means token is invalid/expired
```

### 4. Check Runner Scale Set Status
```bash
# View the ARC runner set (may require elevated permissions):
kubectl describe autoscalingrunnerset -n arc-runners arc-runner-set

# Look for conditions and status annotations
```

## Resolution

### If Token is Expired:
1. Generate a new GitHub Personal Access Token with scopes:
   - `admin:org_hook`
   - `public_repo` (or broader if required)
2. Update Infisical secret at `/platform/arc`:
   ```bash
   /root/.config/infisical/secrets.sh set /platform/arc GITHUB_TOKEN "<new_token>"
   ```
3. Restart arc-controller pod:
   ```bash
   kubectl rollout restart deployment -n arc-systems arc-controller-gha-rs-controller
   ```

### If Organization Doesn't Support Runners:
1. Verify organization exists on GitHub: https://github.com/charlieshreck
2. Check if org has self-hosted runner license/permission
3. If using GitHub Free: upgrade to GitHub Pro or Business

### If Token Lacks Permissions:
1. Generate new token with correct scopes (see above)
2. Update Infisical and restart pod (see above)

## Verification
After fix:
```bash
# Check pod is Running without crashes
kubectl get pod -n arc-systems -l app.kubernetes.io/name=gha-rs-controller

# Check ArgoCD app status transitions to Healthy
argocd app get arc-controller

# Check controller logs for successful reconciliation
kubectl logs -n arc-systems deployment/arc-controller-gha-rs-controller --tail=20
# Should see: "Creating a new runner scale set" and no 404 errors
```

## Notes
- Pod may take 1-2 minutes to fully recover after token refresh
- Arc-runner pods will be created in `arc-runners` namespace once registration succeeds
- Monitor Prometheus metric `actions_controller_autoscaling_runner_set_registered` for success
