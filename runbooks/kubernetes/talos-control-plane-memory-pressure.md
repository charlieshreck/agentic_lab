# Talos Control Plane Memory Pressure

**Alert**: Memory at 85%+ on talos-cp-01
**Cluster**: prod (Talos on Ruapehu)
**Related Incident**: #166

## Root Cause

The Talos control plane node (VMID 400) is allocated a fixed amount of memory by Terraform. When pod requests and system overhead consume 85%+ of this allocation, kubelet memory pressure conditions trigger.

### Memory Breakdown (Current: 4GB → 5GB)

| Component | Memory Usage | Notes |
|-----------|--------------|-------|
| System Reserved | ~700MB | Kubelet, container runtime, OS |
| kube-apiserver | 512Mi (request) | API server for cluster operations |
| kube-controller-manager | 256Mi (request) | Controller loops |
| kube-scheduler | 64Mi (request) | Pod scheduling |
| Cilium & networking | ~200Mi | CNI plugin |
| Monitoring agents | ~150Mi | Prometheus node exporter, pulse-agent |
| **Total baseline** | **~2.2GB** | Minimal cluster overhead |

Alert threshold is 85%, so:
- 4GB allocation → Alert at 3.4GB used (too tight)
- 5GB allocation → Alert at 4.25GB used (better headroom)

## Solution

### Quick Fix (Terraform)
Increase `control_plane.memory` in `prod_homelab/infrastructure/terraform/variables.tf`:

```hcl
variable "control_plane" {
  default = {
    name   = "talos-cp-01"
    memory = 5120  # Increased from 4096 (4GB → 5GB)
    # ... other fields ...
  }
}
```

Commit and push → ArgoCD will not auto-sync this (Terraform resource). Manual `terraform apply` required:

```bash
cd /home/prod_homelab/infrastructure/terraform
terraform plan  # Verify VM ID 400 memory change
terraform apply -target=proxmox_virtual_environment_vm.control_plane
```

### Post-Apply Verification

1. **Proxmox**: VM 400 should show maxmem=5GB instead of 4GB
2. **Kubernetes Node**:
   ```bash
   kubectl describe node talos-cp-01
   # Check Capacity.memory: should remain ~3.9GB (OS doesn't see extra until reboot)
   ```
3. **Proxmox Dashboard**: Memory pressure should drop to ~68% immediately

## Host Capacity Check

Before increasing CP memory, ensure host has headroom:

```bash
# From Ruapehu (Proxmox host)
pvestat  # Should show available RAM
# Or check current allocations:
# talos-cp-01: 4GB → 5GB (add 1GB)
# talos-worker-01: 9GB
# talos-worker-02: 9GB
# talos-worker-03: 9GB
# plex: 7GB
# unifi: 2GB
# Total: 40GB → 41GB (still within 62GB host budget)
```

## Permanent Prevention

This should not recur as long as:
1. **No new system pods** added to control plane without proper resource limits
2. **Workload pods** stay off control plane (taint enforces this)
3. **Control plane memory** bumped if baseline overhead grows (monitor for multiversion apiserver, new admission webhooks, etc.)

Monitor with:
```bash
# Current memory utilization
kubectl top node talos-cp-01

# Pod requests on control plane
kubectl get pods -A -o json | \
  jq '.items[] | select(.spec.nodeName=="talos-cp-01") | .metadata.name'
```

## Related Alerts

- **#160**: Ruapehu host-level memory pressure (over-allocated VMs)
  - Fixed by reducing worker allocations in Terraform
  - Differs from this CP node-level issue

## Runbook Metadata
- **Domain**: kubernetes/infrastructure
- **Severity**: warning
- **Frequency**: First occurrence (Incident #166)
- **MTTR**: 5-10 minutes (Terraform apply + VM warm restart not needed)
