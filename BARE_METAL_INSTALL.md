# Bare Metal Talos Installation Guide

**Complete guide for deploying Talos Linux on UM690L bare metal hardware**

---

## Overview

This guide walks through installing Talos OS directly on the UM690L hardware (no Proxmox, no VMs). The process involves:

1. Downloading and preparing Talos ISO
2. Booting UM690L from USB
3. Configuring network and verifying connectivity
4. Using Terraform to provision and bootstrap the cluster
5. Deploying Kubernetes workloads

**Timeline**: ~30-45 minutes

---

## Prerequisites

### Hardware
- ✅ UM690L (AMD Ryzen 9 6900HX, 32GB RAM, 1.5TB NVMe)
- ✅ USB drive (8GB+ for Talos ISO)
- ✅ Monitor + keyboard for BIOS configuration (or remote console)
- ✅ Network cable connected to your router/switch

### Software (on your workstation)
- Terraform >= 1.5.0
- talosctl >= 1.8.0
- kubectl >= 1.28.0

### Network Requirements
- Static IP available: 10.20.0.109 (or adjust in terraform.tfvars)
- Gateway: 10.20.0.1
- Internet connectivity for pulling container images

---

## Step 1: Download Talos ISO

From your workstation:

```bash
# Download Talos v1.8.1 metal ISO
wget https://github.com/siderolabs/talos/releases/download/v1.8.1/metal-amd64.iso

# Verify download
ls -lh metal-amd64.iso
# Should be ~150-200MB
```

**Alternative**: Download from browser: https://github.com/siderolabs/talos/releases

---

## Step 2: Flash ISO to USB Drive

### On Linux/macOS:

```bash
# Find USB device
lsblk
# Look for your USB drive (e.g., /dev/sdb, /dev/sdc)

# Flash ISO (CAREFUL: This erases the USB drive!)
sudo dd if=metal-amd64.iso of=/dev/sdX bs=4M status=progress && sync

# Replace /dev/sdX with your actual USB device (e.g., /dev/sdb)
# DO NOT use a partition number (e.g., /dev/sdb1)
```

### On Windows:

Use [Rufus](https://rufus.ie/) or [balenaEtcher](https://www.balena.io/etcher/):
1. Select Talos ISO
2. Select USB drive
3. Click "Flash"

---

## Step 3: Prepare UM690L Hardware

### BIOS Configuration

1. **Boot UM690L and enter BIOS**:
   - Press `F2` or `DEL` repeatedly during boot

2. **Disable Secure Boot**:
   - Navigate to `Security` → `Secure Boot`
   - Set to `Disabled`

3. **Set Boot Order**:
   - Navigate to `Boot`
   - Move USB to first position
   - Save and exit (F10)

4. **Optional**: Enable CPU virtualization (should be enabled by default)
   - `Advanced` → `CPU Configuration`
   - Enable `SVM Mode` (AMD virtualization)

---

## Step 4: Boot Talos from USB

1. **Insert USB drive** into UM690L

2. **Power on** the UM690L

3. **Talos will boot** into maintenance mode:
   - You'll see Talos logo and boot messages
   - System will obtain DHCP IP automatically
   - No login prompt (Talos is controlled via API only)

4. **Note the IP address**:
   - Talos will display its IP on the console
   - Or check your router's DHCP leases
   - Example: `192.168.1.100` (temporary DHCP IP)

---

## Step 5: Verify Connectivity

From your workstation:

```bash
# Test connectivity
ping <talos-dhcp-ip>

# Install talosctl if not already installed
# macOS:
brew install siderolabs/tap/talosctl

# Linux:
curl -sL https://talos.dev/install | sh

# Windows:
# Download from https://github.com/siderolabs/talos/releases

# Verify talosctl works
talosctl version --client
```

---

## Step 6: Inspect Hardware

Before running Terraform, gather hardware information:

```bash
# Set temporary endpoint (use DHCP IP from Step 4)
export TALOS_TEMP_IP=<dhcp-ip>

# Check network interfaces
talosctl -n $TALOS_TEMP_IP get links --insecure

# Look for physical interfaces:
# - eth0: First NIC (use this for node_ip)
# - eth1: Second NIC (optional, unused for single-node)

# Check disks
talosctl -n $TALOS_TEMP_IP disks --insecure

# Look for NVMe drive:
# /dev/nvme0n1: 1.5TB NVMe (use this for install_disk)

# Check system info
talosctl -n $TALOS_TEMP_IP dmesg --insecure | grep -i nvme
talosctl -n $TALOS_TEMP_IP dmesg --insecure | grep -i amd
```

**Note**: The `--insecure` flag is required because the machine hasn't been configured yet.

---

## Step 7: Configure Terraform Variables

```bash
cd /home/agentic_lab/infrastructure/terraform/talos-cluster

# Copy example file
cp terraform.tfvars.example terraform.tfvars

# Edit with discovered values
vim terraform.tfvars
```

**Update these variables based on Step 6**:

```hcl
# Network Configuration
node_ip           = "10.20.0.109"      # Your desired static IP
network_gateway   = "10.20.0.1"        # Your router/gateway
network_cidr      = 24
network_interface = "eth0"             # From 'get links' output
dns_servers       = ["1.1.1.1", "8.8.8.8"]

# Disk Configuration
install_disk    = "/dev/nvme0n1"       # From 'disks' output
disk_min_size   = 400                  # UM690L has 1.5TB

# Leave other values at defaults unless you have specific requirements
```

---

## Step 8: Run Terraform

```bash
# Initialize Terraform (downloads providers)
terraform init

# Validate configuration
terraform validate

# Preview changes
terraform plan

# Review the plan carefully - you should see:
# - talos_machine_secrets.this (create)
# - talos_machine_configuration_apply.this (create)
# - talos_machine_bootstrap.this (create)
# - local_file.kubeconfig (create)
# - local_file.talosconfig (create)

# Apply configuration
terraform apply

# Type 'yes' when prompted
```

**What happens during `terraform apply`:**

1. **Generates machine secrets** (PKI for Talos cluster)
2. **Generates machine configuration** (YAML with network, disk, cluster settings)
3. **Applies configuration to node** via Talos API (uses DHCP IP temporarily)
4. **Talos installs itself to disk** (/dev/nvme0n1)
5. **Node reboots** with permanent configuration
6. **Node comes up with static IP** (10.20.0.109)
7. **Kubernetes bootstraps** (control plane starts)
8. **Kubeconfig generated** to `generated/kubeconfig`

**Duration**: ~10-15 minutes

**During the apply**:
- Watch the UM690L console for progress
- Node will reboot during installation
- After reboot, it should come up at 10.20.0.109

---

## Step 9: Verify Cluster

After Terraform completes successfully:

```bash
# Export kubeconfig
export KUBECONFIG=$(terraform output -raw kubeconfig_path)
export TALOSCONFIG=$(terraform output -raw talosconfig_path)

# Verify Talos health
talosctl health --nodes 10.20.0.109

# Output should show:
# [✓] API
# [✓] etcd
# [✓] kubelet

# Check Kubernetes nodes
kubectl get nodes

# Output should show:
# NAME         STATUS     ROLES           AGE   VERSION
# agentic-01   NotReady   control-plane   2m    v1.31.1

# NotReady is expected - need to install CNI (Cilium)

# Check system pods
kubectl get pods -A

# Should see:
# - kube-system: apiserver, controller-manager, scheduler
# - Note: CoreDNS will be Pending (waiting for CNI)
```

---

## Step 10: Remove USB Drive

Once the cluster is healthy:

1. **Power off** the UM690L:
   ```bash
   talosctl shutdown --nodes 10.20.0.109
   ```

2. **Remove USB drive**

3. **Power on** UM690L
   - Should boot directly from NVMe now
   - Will come up at 10.20.0.109

---

## Step 11: Deploy CNI and Core Platform

Now that the bare metal cluster is running, proceed to deploy the platform:

```bash
cd /home/agentic_lab

# Deploy ArgoCD and core services
kubectl apply -k kubernetes/bootstrap/

# Wait for ArgoCD to be ready
kubectl wait --for=condition=available --timeout=300s \
  deployment/argocd-server -n argocd

# Get ArgoCD admin password
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d

# Port forward to access UI
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Open browser: https://localhost:8080
# Username: admin
# Password: (from command above)
```

---

## Troubleshooting

### Node won't boot from USB

**Symptoms**: BIOS can't find bootable USB

**Solutions**:
- Re-flash USB with different tool (Rufus vs balenaEtcher)
- Try different USB port
- Verify Secure Boot is disabled in BIOS
- Use MBR partition table instead of GPT in Rufus

### Can't reach Talos at DHCP IP

**Symptoms**: `ping <dhcp-ip>` times out

**Solutions**:
```bash
# Check router DHCP leases for UM690L MAC address
# Verify network cable is connected
# Try different network port on UM690L (eth0 vs eth1)
# Disable firewall on your workstation temporarily
```

### Terraform apply fails at configuration apply

**Symptoms**: `Error: failed to apply config`

**Solutions**:
```bash
# Verify node is reachable
ping <dhcp-ip>

# Try manual configuration apply
talosctl apply-config --insecure \
  --nodes <dhcp-ip> \
  --file generated/machine-config.yaml

# Check Talos logs
talosctl -n <dhcp-ip> logs --insecure
```

### Node gets DHCP IP instead of static IP after reboot

**Symptoms**: Node comes up at wrong IP after installation

**Solutions**:
- Verify `node_ip` in terraform.tfvars is correct
- Check `network_interface` matches actual interface name
- Verify `network_gateway` is correct for your network
- Re-run `terraform apply` to reapply configuration

### Disk not found during installation

**Symptoms**: `Error: no suitable disks found`

**Solutions**:
```bash
# Check available disks
talosctl -n <dhcp-ip> disks --insecure

# Verify install_disk path in terraform.tfvars
# Common paths:
# - NVMe: /dev/nvme0n1
# - SATA: /dev/sda

# Update terraform.tfvars and re-apply
```

### CoreDNS pods stuck in Pending

**Symptoms**: `kubectl get pods -n kube-system` shows CoreDNS Pending

**Explanation**: Expected! CNI (Cilium) not installed yet

**Solution**: Proceed to Step 11 to deploy ArgoCD which will install Cilium

---

## Post-Installation

### Enable GPU Support for Ollama

The AMD Radeon 680M iGPU is automatically detected by Talos. To verify:

```bash
# Check kernel modules
talosctl -n 10.20.0.109 get kernelmodules | grep amdgpu

# Check GPU in system
talosctl -n 10.20.0.109 ls /dev/dri
# Should show: card0, renderD128
```

Ollama will use the GPU automatically when deployed (Phase 3).

### Backup Critical Files

```bash
# Backup generated configs
cp -r infrastructure/terraform/talos-cluster/generated ~/talos-backup/

# Includes:
# - kubeconfig (for kubectl access)
# - talosconfig (for talosctl access)
# - machine-config.yaml (for disaster recovery)
```

### Next Steps

See [PHASES.md](./PHASES.md):
- **Phase 1**: ✅ Complete (Talos cluster running)
- **Phase 2**: Deploy ArgoCD and core services
- **Phase 3**: Deploy inference layer (Ollama, LiteLLM)
- Continue through phases 4-8...

---

## Disaster Recovery

If you need to reinstall from scratch:

1. **Boot from USB again** (same process as Step 4)
2. **Run `terraform destroy`** (optional, if previous state exists)
3. **Re-run `terraform apply`**
4. **Restore from backup** if needed:
   ```bash
   # Kubeconfig and talosconfig are regenerated by Terraform
   # To use backed up configs:
   export KUBECONFIG=~/talos-backup/kubeconfig
   export TALOSCONFIG=~/talos-backup/talosconfig
   ```

---

## Reference Links

- Talos Documentation: https://www.talos.dev/
- Talos Releases: https://github.com/siderolabs/talos/releases
- Terraform Talos Provider: https://registry.terraform.io/providers/siderolabs/talos/latest/docs
- UM690L Specs: https://www.minisforum.com/page/um690/overview.html

---

**Installation complete! Your bare metal Talos cluster is ready for the AI platform deployment.**
