# GitOps Workflow - MANDATORY FOR ALL CHANGES

## CRITICAL RULE: Infrastructure as Code (IaC) ONLY

**ALWAYS follow this workflow. NO EXCEPTIONS.**

This repository uses GitOps principles. ALL infrastructure changes MUST be:
1. Defined in code (Terraform, Kubernetes manifests)
2. Committed to git
3. Deployed via automation (Terraform, ArgoCD)

## ArgoCD Architecture (CRITICAL)

**ArgoCD runs ONLY in the prod cluster (10.10.0.0/24)** and manages all three clusters remotely:
- prod (10.10.0.0/24) - local deployments
- agentic (10.20.0.0/24) - remote deployments via cluster destination
- monit (10.30.0.0/24) - remote deployments via cluster destination

The agentic cluster has **NO local ArgoCD**. All deployments are managed remotely from prod.

## Deployment Methods by Component

| Component | Tool | Workflow |
|-----------|------|----------|
| **Talos VM** | Terraform | `terraform plan` → `terraform apply` |
| **Talos Configuration** | Talosctl + Git | Update .tf → commit → apply → talosctl apply-config |
| **Kubernetes Resources** | ArgoCD (in prod) | Commit to git → ArgoCD auto-sync from prod cluster |
| **Secrets** | Infisical | Add to Infisical UI → InfisicalSecret CR in K8s |

## The ONLY Correct Workflow

### For Terraform (Talos VM provisioning)

```bash
cd /home/agentic_lab/infrastructure/terraform/talos-cluster

# 1. Make changes to .tf files
vim main.tf

# 2. Commit to git FIRST
git add .
git commit -m "Description of change"
git push

# 3. Plan
terraform plan -out=agentic.plan

# 4. Review plan output carefully
cat agentic.plan  # Or just review terraform plan output

# 5. Apply
terraform apply agentic.plan

# 6. Export kubeconfig if cluster changed
export KUBECONFIG=$(terraform output -raw kubeconfig_path)
export TALOSCONFIG=$(terraform output -raw talosconfig_path)
```

### For Talos Configuration

```bash
cd /home/agentic_lab/infrastructure/terraform/talos-cluster

# 1. Update Talos machine config in Terraform
vim talos-config.tf

# 2. Commit to git FIRST
git add .
git commit -m "Update Talos configuration"
git push

# 3. Generate new config
terraform apply

# 4. Apply to cluster
talosctl apply-config --nodes 10.20.0.40 \
  --file generated/talosconfig-agentic-talos.yaml
```

### For Kubernetes (Applications, Platform)

```bash
cd /home/agentic_lab

# 1. Make changes to manifests
vim kubernetes/applications/litellm/deployment.yaml

# 2. Commit to git FIRST (this is the deployment!)
git add .
git commit -m "Description of change"
git push

# 3. ArgoCD (in PROD cluster) automatically syncs within 3 minutes
# OR force sync from prod cluster:
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig \
  kubectl patch application litellm -n argocd --type merge \
  -p '{"operation": {"initiatedBy": {"username": "claude"}, "sync": {"prune": true}}}'

# 4. Verify (in agentic cluster)
KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig \
  kubectl get pods -n ai-platform
```

### Creating New ArgoCD Applications for Agentic Cluster

For new applications, you must create an ArgoCD Application manifest:

```bash
# 1. Create the application manifests
mkdir -p kubernetes/applications/my-app
vim kubernetes/applications/my-app/deployment.yaml

# 2. Create ArgoCD Application (points to agentic cluster)
cat > kubernetes/argocd-apps/my-app.yaml << 'EOF'
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/charlieshreck/agentic_lab.git
    targetRevision: main
    path: kubernetes/applications/my-app
  destination:
    server: https://10.20.0.40:6443  # Agentic cluster
    namespace: ai-platform
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
EOF

# 3. Commit and push
git add .
git commit -m "Add my-app to agentic cluster"
git push

# 4. Apply ArgoCD Application to PROD cluster (one-time)
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig \
  kubectl apply -f kubernetes/argocd-apps/my-app.yaml

# 5. ArgoCD now manages the app automatically
```

### For Secrets

```bash
# 1. Add secret to Infisical UI
#    Project: prod_homelab (or create agentic_lab project)
#    Environment: prod
#    Path: /agentic-platform/<component>
#    Examples:
#      - /agentic-platform/llm-apis (GEMINI_API_KEY, ANTHROPIC_API_KEY)
#      - /agentic-platform/telegram (TELEGRAM_BOT_TOKEN)
#      - /agentic-platform/proxmox (API credentials)

# 2. Create InfisicalSecret CR manifest
vim kubernetes/applications/<app>/infisical-secret.yaml

# 3. Commit to git
git add .
git commit -m "Add InfisicalSecret for <app>"
git push

# 4. ArgoCD auto-syncs
# Secret appears in K8s automatically

# 5. Verify
kubectl get infisicalsecret -n ai-platform
kubectl get secret <secret-name> -n ai-platform
```

## FORBIDDEN Actions

### ❌ NEVER DO THESE:

```bash
# WRONG: Manual kubectl apply
kubectl apply -f deployment.yaml

# WRONG: Manual kubectl edit
kubectl edit deployment litellm

# WRONG: Manual kubectl create
kubectl create secret generic my-secret

# WRONG: Direct terraform apply without git commit
terraform apply

# WRONG: Hardcoded secrets in manifests
echo "api_key: sk-my-key" > secret.yaml

# WRONG: Manual talosctl changes without updating Terraform
talosctl patch mc --nodes 10.20.0.40 -p '[...]'

# WRONG: Manual VM creation in Proxmox UI
# (Use Terraform instead)
```

### ✅ CORRECT Alternatives:

```bash
# RIGHT: Commit to git, let ArgoCD sync
git add . && git commit -m "Update deployment" && git push

# RIGHT: Update manifest in git
vim kubernetes/applications/litellm/deployment.yaml
git add . && git commit && git push

# RIGHT: Use InfisicalSecret CR
# Add to Infisical UI, create InfisicalSecret manifest, commit

# RIGHT: Commit terraform changes first
git add . && git commit && git push
terraform plan && terraform apply

# RIGHT: Update Talos config via Terraform
vim infrastructure/terraform/talos-cluster/talos-config.tf
git commit && git push && terraform apply
```

## Exception: Manual Configs for Credentials

**ONLY for files that cannot be in git** (kubeconfig, talosconfig):

```bash
# These are generated by Terraform and NOT committed to git
# Located in: infrastructure/terraform/talos-cluster/generated/

# Use them locally:
export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig
export TALOSCONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/talosconfig

# For MCP servers or other apps needing kubeconfig, create ConfigMap:
kubectl create configmap kubeconfig-agentic \
  --from-file=kubeconfig=$(terraform output -raw kubeconfig_path) \
  -n mcp-servers
```

**Document these in README.md** so they can be recreated.

## GitOps Principles

1. **Git is the source of truth**
   - All infrastructure defined in git
   - No manual changes outside git
   - Git history = audit trail

2. **Declarative configuration**
   - Define desired state, not steps
   - Tools reconcile actual state to desired state
   - Idempotent operations

3. **Automated deployment**
   - ArgoCD watches git repo
   - Automatically applies changes
   - Self-healing (reverts manual changes)

4. **No kubectl apply**
   - ArgoCD handles all K8s deployments
   - Manual kubectl only for debugging/verification
   - Read-only kubectl commands are fine

## Workflow Checklist

Before making ANY infrastructure change:

- [ ] Is the change defined in code? (Terraform/K8s manifest)
- [ ] Have I committed to git?
- [ ] Have I pushed to GitHub?
- [ ] Am I using the correct tool? (Terraform/ArgoCD)
- [ ] Am I avoiding manual kubectl apply?
- [ ] Am I avoiding manual talosctl patches?
- [ ] Are secrets in Infisical, not hardcoded?

If you answered NO to any question, STOP and follow the correct workflow.

## Emergency: Reverting Changes

```bash
# Kubernetes (via ArgoCD)
git revert <commit-hash>
git push
# ArgoCD auto-syncs the revert

# Terraform
git revert <commit-hash>
git push
terraform plan  # Verify revert
terraform apply

# Talos Configuration
git revert <commit-hash>
git push
terraform apply  # Regenerate configs
talosctl apply-config --nodes 10.20.0.40 --file generated/talosconfig-agentic-talos.yaml
```

## Why GitOps?

1. **Audit trail**: Every change tracked in git history
2. **Rollback**: Easy to revert via git
3. **Consistency**: Same process for all changes
4. **Disaster recovery**: Entire infrastructure in git
5. **No drift**: ArgoCD enforces desired state
6. **Learning**: Agent can analyze git history to understand changes

## Agentic Platform Specific Notes

### AI Agent Autonomy Levels

The agentic platform has different autonomy levels for changes:

1. **Manual** (GitOps required): Infrastructure, Terraform, Talos config
   - ALWAYS follow this workflow
   - Agent proposes changes, human commits

2. **Prompted** (Human approval required): Kubernetes workload changes
   - Agent proposes via Telegram
   - Human approves via inline button
   - Agent commits and pushes to git
   - ArgoCD syncs automatically

3. **Standard** (Fully automated): Proven runbooks with high success rate
   - Agent executes, commits, and pushes
   - Human notified after the fact
   - Must still follow GitOps (commit → push → sync)

**ALL autonomy levels MUST use GitOps.** Even fully automated changes are committed to git.

### MCP Server Operations

MCP servers provide read-only access by default. Write operations (kubectl, talosctl) are:
- Logged to Qdrant knowledge base
- Subject to human approval workflow
- Committed to git after approval
- Deployed via ArgoCD (never direct kubectl)

## References

- ArgoCD: Kubernetes deployment automation
- Terraform: Infrastructure provisioning
- Talosctl: Talos cluster management
- Infisical: Secrets management
- Git: Source of truth
- LangGraph: Agent orchestration (respects GitOps)
- Qdrant: Knowledge base (records all decisions)

---

**Remember**: If it's not in git, it doesn't exist. If you didn't commit first, you did it wrong.

**For the AI**: Even your most confident autonomous changes must go through git. Learn from outcomes, but always commit.

---

## Claude Code Session Requirements

When working with Claude Code (or any AI assistant):

1. **ALWAYS commit changes to git BEFORE applying to cluster**
   - Edit manifest files in the repository
   - `git add` and `git commit` with descriptive message
   - `git push` to remote

2. **NEVER use direct kubectl apply without git commit first**
   - Even for "quick fixes", commit first
   - Manual kubectl changes will be reverted by ArgoCD

3. **Wait for ArgoCD sync (or manually sync if needed)**
   - ArgoCD syncs every 3 minutes automatically
   - Use `argocd app sync <app>` for immediate sync

4. **If ArgoCD Application doesn't exist yet:**
   - Still commit manifests to git first
   - Create ArgoCD Application manifest in `kubernetes/argocd-apps/`
   - Apply the ArgoCD Application to **prod cluster** (one-time bootstrap)
   - ArgoCD then manages it automatically going forward

**The workflow is: Edit → Commit → Push → (Create ArgoCD App if new) → Sync → Verify**

Never skip the commit step, even if you're debugging or iterating quickly.
