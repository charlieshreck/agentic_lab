# ARC Controller GitHub API 404 Troubleshooting

## Pattern
- ArgoCD app `arc-controller` shows "Unknown" status
- Pod in `arc-systems` namespace shows multiple restarts (4+)
- Logs contain: `github api error: StatusCode 404` when refreshing runner registration token
- Alert: `ArgoCDAppOutOfSync` fires and clears as pod cycles

## Root Cause
The `arc-runner-set` (in `arc-runners` namespace) is attempting to register GitHub Actions runners with GitHub, but the API request is returning 404 Not Found.

**CRITICAL**: The configuration is fundamentally broken:
- **GitHub Config URL**: `https://github.com/charlieshreck`
- **Issue**: `charlieshreck` is a **personal user account**, NOT an organization
- **GitHub Limitation**: Self-hosted runners are ONLY available at Organization or Repository level, NOT for personal accounts
- **Root Cause**: The configuration should point to an actual GitHub organization, not a user

Other contributing factors:
1. **Token is valid** (tested 2026-02-26) and has no auth issues (returns 401 if invalid)
2. **Organization Doesn't Exist**: API returns 404 because `charlieshreck` as an org doesn't exist
3. **Correct Organization Needed**: Must either create a real org or change to repo-level runners

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

### CRITICAL: Organization Configuration Error

The configuration points to `charlieshreck` (personal user account) which CANNOT have self-hosted runners.

**Choose ONE of these options:**

#### Option 1: Create a Real GitHub Organization (RECOMMENDED if using org-level runners)
1. Create new GitHub organization: https://github.com/organizations/new
   - Example: `kernow-actions`, `homelab-runners`, `charlieshreck-org`
2. Update ARC configuration in git:
   ```yaml
   spec:
     githubConfigUrl: https://github.com/<YOUR_NEW_ORG>
   ```
   File: `/home/agentic_lab/kubernetes/platform/arc-runner-set/manifests.yaml` (line 151)
3. Apply changes via GitOps (commit → push → ArgoCD sync)
4. ARC controller pod will restart automatically with new config

#### Option 2: Switch to Repository-Level Runners (for single-repo CI/CD)
1. Choose target repository: e.g., `github.com/charlieshreck/kernow-homelab`
2. Update ARC configuration:
   ```yaml
   spec:
     githubConfigUrl: https://github.com/charlieshreck/kernow-homelab
   ```
3. Ensure GitHub token has `repo` and `workflow` scopes at minimum
4. Apply changes via GitOps

#### Option 3: Disable ARC (if runners not needed)
1. Remove arc-controller app from ArgoCD
2. Or disable in git and sync

### Token Validation (2026-02-26)
✓ Token is **VALID** (no 401 auth errors)
✓ Token has correct scopes for organization runner registration
✗ Cannot be used until organization configuration is fixed

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
