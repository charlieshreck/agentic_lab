# SealedSecrets Guide

## Overview

SealedSecrets enables encrypting Kubernetes secrets so they can be safely stored in git. Only the SealedSecrets controller in the target cluster can decrypt them.

**Key Principle**: SealedSecrets are for storing encrypted secrets in git, not for initial provisioning.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SealedSecrets Flow                           │
├─────────────────────────────────────────────────────────────────┤
│  1. kubeseal encrypts secret with cluster's public key          │
│  2. SealedSecret manifest committed to git                      │
│  3. ArgoCD/GitOps syncs SealedSecret to cluster                 │
│  4. SealedSecrets controller decrypts → creates real Secret     │
└─────────────────────────────────────────────────────────────────┘
```

## Cluster Deployment Status

| Cluster | Network | Method | Status |
|---------|---------|--------|--------|
| agentic | 10.20.0.0/24 | ArgoCD Helm | Deployed |
| prod | 10.10.0.0/24 | ArgoCD Helm | Deployed |
| monit | 10.30.0.0/24 | ArgoCD Helm | Deployed |

**Note**: All clusters use the same ArgoCD pattern - ArgoCD apps in prod cluster deploy to remote clusters.

## Common Operations

### Fetch Cluster's Public Key

```bash
# Agentic cluster
export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig
kubeseal --fetch-cert --controller-name=sealed-secrets-controller \
  --controller-namespace=kube-system > /tmp/agentic-sealed-secrets.pub

# Prod cluster
export KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig
kubeseal --fetch-cert --controller-name=sealed-secrets-controller \
  --controller-namespace=kube-system > /tmp/prod-sealed-secrets.pub

# Monit cluster (construct kubeconfig from ArgoCD cluster secret)
# First extract credentials from prod ArgoCD
KUBECONFIG=/home/prod_homelab/infrastructure/terraform/generated/kubeconfig
CREDS=$(kubectl get secret monitoring-talos-cluster -n argocd -o jsonpath='{.data.config}' | base64 -d)
BEARER=$(echo "$CREDS" | jq -r '.bearerToken')
CA_DATA=$(echo "$CREDS" | jq -r '.tlsClientConfig.caData')

cat > /tmp/monit-kubeconfig.yaml << EOF
apiVersion: v1
kind: Config
clusters:
- cluster:
    certificate-authority-data: $CA_DATA
    server: https://10.30.0.20:6443
  name: monitoring-talos
contexts:
- context:
    cluster: monitoring-talos
    user: argocd-manager
  name: monitoring
current-context: monitoring
users:
- name: argocd-manager
  user:
    token: $BEARER
EOF

KUBECONFIG=/tmp/monit-kubeconfig.yaml kubeseal --fetch-cert \
  --controller-name=sealed-secrets-controller \
  --controller-namespace=kube-system > /tmp/monit-sealed-secrets.pub
```

### Seal a Secret

```bash
# Create plaintext secret and seal it
cat <<EOF | kubeseal --format=yaml --cert=/tmp/<cluster>-sealed-secrets.pub
apiVersion: v1
kind: Secret
metadata:
  name: my-secret
  namespace: my-namespace
type: Opaque
stringData:
  key1: "value1"
  key2: "value2"
EOF
```

### Verify SealedSecret

```bash
# Check SealedSecret exists
kubectl get sealedsecret -n <namespace>

# Check unsealed secret was created
kubectl get secret <name> -n <namespace>

# View decrypted value
kubectl get secret <name> -n <namespace> -o jsonpath='{.data.<key>}' | base64 -d
```

### Backup Sealing Keys

**Critical for disaster recovery!**

```bash
# Backup the controller's keypair
kubectl get secret -n kube-system \
  -l sealedsecrets.bitnami.com/sealed-secrets-key \
  -o yaml > sealed-secrets-key-backup.yaml

# Store securely (Infisical, 1Password, etc.) - NOT in git!
```

### Restore Sealing Keys

```bash
# On a fresh cluster, before deploying controller:
kubectl create namespace kube-system  # if not exists
kubectl apply -f sealed-secrets-key-backup.yaml

# Then deploy controller - it will use existing key
```

## Fresh Deployment / IaC Bootstrap

### Problem

SealedSecrets controller generates a unique keypair on first boot. Existing SealedSecrets won't decrypt on a fresh cluster without the original key.

### Solution: Two-Phase Bootstrap

#### Phase A: Initial Terraform Deploy

For Terraform-managed clusters (monit):

```hcl
# terraform.tfvars (gitignored - source of truth for fresh deploy)
infisical_client_id     = "your-client-id"
infisical_client_secret = "your-client-secret"

# infisical.tf - uses variable for initial deploy
variable "infisical_client_id" {
  type      = string
  sensitive = true
}

variable "infisical_client_secret" {
  type      = string
  sensitive = true
}

resource "kubernetes_secret" "universal_auth_credentials" {
  metadata {
    name      = "universal-auth-credentials"
    namespace = "infisical-operator-system"
  }
  data = {
    clientId     = var.infisical_client_id
    clientSecret = var.infisical_client_secret
  }
  depends_on = [helm_release.sealed_secrets]
}
```

For ArgoCD-managed clusters (prod):

```bash
# Fresh deploy: manually create secret before ArgoCD syncs
kubectl create secret generic universal-auth-credentials \
  --namespace infisical-operator-system \
  --from-literal=clientId="<ID>" \
  --from-literal=clientSecret="<SECRET>"
```

#### Phase B: Post-Deploy Sealing

After cluster is running:

1. Fetch new cluster's sealing key
2. Re-seal the bootstrap credentials
3. Update terraform/manifests to use SealedSecret
4. Commit to git (now encrypted)

```bash
# Fetch new cluster's cert
kubeseal --fetch-cert > /tmp/new-cluster.pub

# Re-seal credentials
cat <<EOF | kubeseal --format=yaml --cert=/tmp/new-cluster.pub > sealed-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: universal-auth-credentials
  namespace: infisical-operator-system
stringData:
  clientId: "..."
  clientSecret: "..."
EOF
```

### Deployment Flows

```
Fresh Deploy Flow:
┌─────────────────────────────────────────────────────────────────┐
│  1. terraform apply (uses terraform.tfvars for bootstrap)       │
│     - SealedSecrets controller deployed                         │
│     - Bootstrap secret created from variables                   │
│     - Infisical operator starts                                 │
├─────────────────────────────────────────────────────────────────┤
│  2. Post-deploy (manual or CI/CD):                              │
│     - Fetch new cluster's public key                            │
│     - Re-seal bootstrap credentials                             │
│     - Update terraform to use kubectl_manifest for SealedSecret │
│     - terraform apply (replaces variable-based secret)          │
│     - Git commit (now has encrypted sealed secret)              │
├─────────────────────────────────────────────────────────────────┤
│  3. Steady State:                                               │
│     - terraform.tfvars can be cleared (backup stored securely)  │
│     - All secrets encrypted in git                              │
│     - Full GitOps - no manual steps for redeploy                │
└─────────────────────────────────────────────────────────────────┘

Redeploy Flow (cluster rebuilt):
┌─────────────────────────────────────────────────────────────────┐
│  Option A: Restore sealing key from backup                      │
│  - kubectl apply -f sealed-secrets-key-backup.yaml              │
│  - Deploy controller                                            │
│  - Existing SealedSecrets decrypt automatically                 │
├─────────────────────────────────────────────────────────────────┤
│  Option B: Re-seal with new key (key rotation)                  │
│  - Deploy controller (generates new key)                        │
│  - Re-seal all secrets with new public key                      │
│  - Update manifests and commit                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Infisical Bootstrap Credentials

Each cluster has Infisical operator for runtime secrets. The operator needs bootstrap credentials (chicken-and-egg problem):

| Cluster | Secret Path | Location |
|---------|-------------|----------|
| agentic | `/agentic-platform/infisical` | SealedSecret in kubernetes/platform/infisical/ |
| prod | `/prod-homelab/infisical` | SealedSecret in kubernetes/platform/infisical/ |
| monit | Infisical machine identity | SealedSecret via Terraform |

### Retrieving Credentials

```bash
# From Infisical CLI
/root/.config/infisical/secrets.sh get /agentic-platform/infisical CLIENT_ID
/root/.config/infisical/secrets.sh get /agentic-platform/infisical CLIENT_SECRET

# From machine identity file (agentic)
cat /root/.config/infisical/machine-identity.json
```

## Security Best Practices

1. **Cluster-Specific Keys**: Each cluster has unique sealing keys - secrets cannot be copied between clusters
2. **Key Backup**: Always backup sealing keys after deployment (store in Infisical or 1Password)
3. **Credential Rotation**: Rotate Infisical machine identity if credentials were ever exposed in git
4. **terraform.tfvars**: Keep as backup for disaster recovery, store securely outside git
5. **Never Commit Plaintext**: Use `kubeseal` to encrypt before committing

## Troubleshooting

### SealedSecret Not Decrypting

```bash
# Check controller logs
kubectl logs -n kube-system -l app.kubernetes.io/name=sealed-secrets

# Common issues:
# - Wrong namespace in SealedSecret
# - Secret sealed with different cluster's key
# - Controller not running
```

### Controller Not Starting

```bash
# Check pod status
kubectl get pods -n kube-system -l app.kubernetes.io/name=sealed-secrets

# Check events
kubectl describe pod -n kube-system -l app.kubernetes.io/name=sealed-secrets
```

### Re-sealing After Key Rotation

If the sealing key was rotated (or lost and regenerated):

```bash
# 1. Get all secrets that need re-sealing
kubectl get sealedsecrets -A

# 2. For each secret, get the original values and re-seal
kubeseal --fetch-cert > /tmp/new-key.pub
# ... seal each secret with new key
```

## Related Documentation

- [Infisical Setup](/home/prod_homelab/docs/INFISICAL-SETUP.md)
- [GitOps Workflow](/home/prod_homelab/GITOPS-WORKFLOW.md)
- [SealedSecrets Official Docs](https://sealed-secrets.netlify.app/)
