# Talos Control Plane IPv6 Liveness Probe Failures (Incident #514)

**Status**: RESOLVED (2026-03-25)
**Clusters affected**: monit (single-node Talos on Pihanga)
**Root cause**: Kubernetes control plane components default to IPv6 dual-stack binding, but probes fail when services only listen on IPv4 localhost (127.0.0.1)

---

## Symptoms

Cascading pod restarts in kube-system namespace:
- `kube-controller-manager-talos-monitor`: ~40+ restarts
- `kube-scheduler-talos-monitor`: ~40+ restarts
- `cilium-operator-*`: ~100+ restarts (cascading from kubelet instability)
- `cert-manager-*`: ~25+ restarts

Restart cycle every 5-10 minutes, preventing cluster stabilization.

---

## Root Cause

Kubernetes liveness probes for control plane components (kube-controller-manager, kube-scheduler) default to binding on dual-stack addresses. When probes attempt to connect to `[::1]:port` (IPv6 localhost), they fail on clusters where kubelet probe connections are restricted or IPv6 is unavailable.

Example probe failure:
```
Liveness probe failed: Get "http://[::1]:10257/livez": dial tcp [::1]:10257: ...
```

Each failed probe triggers a container restart. High restart rates cause cascading failures across dependent workloads.

---

## Solution

Modify Talos machine configuration to:
1. Bind control plane components explicitly to IPv4 localhost (`127.0.0.1`)
2. Disable IPv6 DualStack feature gate
3. Set service cluster IP range explicitly (IPv4 only)

### Implementation

Edit `/home/monit_homelab/terraform/talos-single-node/main.tf`:

```hcl
data "talos_machine_configuration" "monitoring_node" {
  # ... existing config ...

  config_patches = [
    yamlencode({
      cluster = {
        allowSchedulingOnControlPlanes = true

        apiServer = {
          extraArgs = {
            service-cluster-ip-range = "10.96.0.0/12"
            bind-address            = "0.0.0.0"
          }
          certSANs = [
            "10.10.0.30",
            "talos-monitor"
          ]
        }

        controllerManager = {
          extraArgs = {
            bind-address = "127.0.0.1"
            feature-gates = "IPv6DualStack=false"
          }
        }

        scheduler = {
          extraArgs = {
            bind-address = "127.0.0.1"
            feature-gates = "IPv6DualStack=false"
          }
        }

        network = {
          cni = {
            name = "none"  # Cilium will be installed via Helm
          }
        }

        proxy = {
          disabled = true  # Cilium replaces kube-proxy
        }

        discovery = {
          enabled = true
          registries = {
            kubernetes = { disabled = false }
            service = { disabled = false }
          }
        }
      }

      machine = {
        kernel = {
          modules = [
            { name = "virtio_balloon" }
          ]
        }
        # ... rest of machine config ...
      }
    })
  ]
}
```

### Deployment

```bash
cd /home/monit_homelab/terraform/talos-single-node/

# Review changes
terraform plan

# Apply configuration to Talos VM
terraform apply -auto-approve

# Verify pod stabilization (wait 2-5 minutes)
export KUBECONFIG=/home/monit_homelab/kubeconfig
kubectl get pods -n kube-system -o custom-columns=NAME:.metadata.name,RESTARTS:.status.containerStatuses[0].restartCount,AGE:.metadata.creationTimestamp
```

---

## Verification

### Immediate (post-apply)
- kube-apiserver restarts drop to 0
- kube-controller-manager and kube-scheduler stabilize (no new restarts for 5+ minutes)
- No "liveness probe failed" events in `kubectl get events`

### Long-term (24+ hours)
- All control plane pods running without restarts
- Cilium and cert-manager restart counts stabilize
- Cluster health check passes: `talosctl --nodes 10.10.0.30 health`

---

## Why This Approach

1. **Explicit IPv4 binding**: Services listen only on IPv4 localhost, eliminating probe failures
2. **IPv6DualStack=false**: Disables dual-stack in controller-manager and scheduler, preventing IPv6 address resolution attempts
3. **Service cluster IP range**: Specifies IPv4-only range (10.96.0.0/12) to prevent IPv6 cluster IP assignment
4. **API server bind-address**: Set to 0.0.0.0 (listen on all interfaces) but service discovery uses IPv4 endpoints

---

## References

- **Incident**: #514 (HomelabPodCrashLooping)
- **Talos docs**: [Machine configuration](https://www.talos.dev/v1.11/reference/configuration/)
- **Kubernetes control plane**: [kubeadm configuration reference](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/control-plane-flags/)
- **IPv6 dual-stack**: [Kubernetes IPv6 documentation](https://kubernetes.io/docs/concepts/services-networking/dual-stack/)

---

## Timeline

- **2026-02-23**: Incident #159 observed (memory alert false positive)
- **2026-03-19**: Incident #514 reported (cascading pod restarts)
- **2026-03-24**: Root cause identified (IPv6 liveness probe failures)
- **2026-03-25**: Fix deployed via Terraform; kube-apiserver stabilized to 0 restarts
