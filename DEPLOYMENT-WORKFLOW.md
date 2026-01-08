# Fresh Deployment Workflow

Complete step-by-step guide for deploying the Agentic Platform on bare metal Talos Linux.

## Prerequisites

- UM690L hardware (or compatible bare metal system)
- USB drive with Talos v1.11.5 ISO (from Factory)
- Network configured: 10.20.0.0/24
- Node IP: 10.20.0.40
- GitHub repository cloned locally

## Phase 1: Prepare Talos Installation Media

```bash
# Download custom Talos ISO from Factory
# URL is in: infrastructure/terraform/talos-cluster/README.md

# Flash to USB drive
dd if=talos-v1.11.5-factory.iso of=/dev/sdX bs=4M status=progress && sync
```

## Phase 2: Boot and Apply Configuration

### 2.1 Boot from USB

1. Insert USB drive into UM690L
2. Boot from USB (F11 or F12 for boot menu)
3. Wait for Talos to load (maintenance mode)

### 2.2 Apply Terraform Configuration

```bash
cd /home/agentic_lab/infrastructure/terraform/talos-cluster

# Initialize Terraform
terraform init

# Review plan (verify versions: Talos v1.11.5, K8s v1.34.1)
terraform plan

# Apply configuration
terraform apply -auto-approve
```

**What happens:**
- Generates Talos machine config for single-node cluster
- Applies config via talosctl to 10.20.0.40
- Generates kubeconfig to `generated/kubeconfig`
- Does NOT bootstrap yet (manual step required)

### 2.3 Bootstrap Cluster

```bash
# Set kubeconfig path
export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig

# Bootstrap etcd cluster (ONE TIME ONLY)
talosctl bootstrap -n 10.20.0.40

# Wait for nodes to be ready
kubectl get nodes -w
# Should show: agentic-01   NotReady   control-plane   1m   v1.34.1
# (NotReady is expected - no CNI yet)
```

## Phase 3: Deploy CNI (Cilium)

**CRITICAL**: Cilium MUST be deployed BEFORE connecting to ArgoCD. Remote management needs CNI to function.

```bash
# Deploy Cilium using prepared script
./deploy-cilium.sh

# Verify Cilium is running
kubectl get pods -n kube-system -l app.kubernetes.io/name=cilium-agent

# Wait for node to become Ready
kubectl get nodes -w
# Should show: agentic-01   Ready   control-plane   5m   v1.34.1
```

## Phase 4: Connect to Production ArgoCD

**Architecture**: ArgoCD runs in the prod_homelab cluster (10.10.0.0/24) and manages this agentic_lab cluster remotely.

### 4.1 Add Cluster to ArgoCD

```bash
# From prod cluster with ArgoCD access:
# Login to ArgoCD CLI
argocd login <argocd-server>

# Add agentic_lab cluster to ArgoCD
argocd cluster add kubernetes-admin@agentic-platform \
  --name agentic-lab \
  --kubeconfig /home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig

# Verify cluster is registered
argocd cluster list
```

### 4.2 Configure Cluster Secret (Alternative method)

If using kubectl to register cluster:

```bash
# Generate cluster secret for ArgoCD
kubectl config use-context kubernetes-admin@agentic-platform
argocd cluster add kubernetes-admin@agentic-platform --name agentic-lab

# Or manually create secret in ArgoCD namespace on prod cluster
# (See ArgoCD docs for cluster secret format)
```

## Phase 5: Deploy Platform Services via ArgoCD

**From prod cluster** (where ArgoCD is running):

```bash
# Switch to prod cluster context
kubectl config use-context <prod-cluster-context>

# Apply ArgoCD applications to prod cluster's ArgoCD namespace
# These apps will deploy to agentic_lab cluster (via destination server config)

kubectl apply -f /home/agentic_lab/kubernetes/argocd-apps/cilium-app.yaml -n argocd
kubectl apply -f /home/agentic_lab/kubernetes/argocd-apps/infisical-operator-app.yaml -n argocd
kubectl apply -f /home/agentic_lab/kubernetes/argocd-apps/cert-manager-app.yaml -n argocd
kubectl apply -f /home/agentic_lab/kubernetes/argocd-apps/local-path-provisioner-app.yaml -n argocd
kubectl apply -f /home/agentic_lab/kubernetes/argocd-apps/qdrant-app.yaml -n argocd

# Watch ArgoCD sync applications to agentic_lab cluster
kubectl get applications -n argocd -w

# Or use ArgoCD CLI
argocd app list
argocd app sync cilium
argocd app sync infisical-operator
argocd app sync cert-manager
argocd app sync local-path-provisioner
argocd app sync qdrant
```

**Note**:
- The Cilium app in ArgoCD will take over management of Cilium going forward
- Initial manual deployment satisfies the bootstrapping requirement
- Apps deploy to agentic_lab cluster based on `destination.server` in manifests

## Phase 6: Verify Deployment

### On prod cluster (check ArgoCD status):
```bash
kubectl config use-context <prod-cluster-context>

# Check all ArgoCD apps are synced and healthy
kubectl get applications -n argocd
argocd app list
```

### On agentic_lab cluster (check deployed resources):
```bash
kubectl config use-context kubernetes-admin@agentic-platform

# Check all pods are running
kubectl get pods -A

# Verify nodes are Ready
kubectl get nodes

# Verify storage class is available
kubectl get storageclass

# Check cert-manager is issuing certificates
kubectl get clusterissuer -A

# Verify Qdrant is accessible
kubectl get svc -n ai-platform
```

## Deployment Order Summary

```
1. Terraform apply (Talos config on agentic_lab node)
2. talosctl bootstrap (etcd initialization on agentic_lab)
3. Cilium CNI (manual deployment via script on agentic_lab)
4. Register cluster with prod ArgoCD
5. Deploy apps from prod ArgoCD → agentic_lab cluster
   ├─ Cilium (ArgoCD takes over management)
   ├─ Infisical Operator
   ├─ Cert-Manager
   ├─ Local Path Provisioner
   └─ Qdrant
```

## Architecture Notes

- **prod_homelab** (10.10.0.0/24): Runs ArgoCD, manages multiple clusters
- **agentic_lab** (10.20.0.0/24): AI platform, managed by prod ArgoCD
- **monit_homelab** (10.30.0.0/24): Observability, separate cluster

## Key Files Reference

| File | Purpose |
|------|---------|
| `infrastructure/terraform/talos-cluster/variables.tf` | Talos v1.11.5, K8s v1.34.1 |
| `infrastructure/terraform/talos-cluster/deploy-cilium.sh` | Cilium bootstrap script |
| `kubernetes/platform/cilium/kustomization.yaml` | Cilium v1.16.5 config |
| `kubernetes/argocd-apps/*.yaml` | ArgoCD application manifests |

## Troubleshooting

### Node stays NotReady
- Check Cilium pods: `kubectl get pods -n kube-system`
- Check Cilium logs: `kubectl logs -n kube-system -l app.kubernetes.io/name=cilium-agent`

### ArgoCD app won't sync
- Check app status: `kubectl describe application <name> -n argocd`
- Check if repo is accessible
- Verify sync-wave order

### Terraform apply fails
- Check Talos node is reachable: `ping 10.20.0.40`
- Verify USB boot was successful
- Check talosctl config: `talosctl config info`

## Next Steps

After successful deployment:

1. Configure Infisical secrets backend
2. Deploy remaining AI platform components (Ollama, LiteLLM, etc.)
3. Set up monitoring (Prometheus, Grafana)
4. Configure backups

See `PHASES.md` for detailed implementation timeline.
