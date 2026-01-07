# Fresh Deployment Checklist - Dual-Drive Storage Configuration

**Last Updated**: 2026-01-07
**Status**: Ready for fresh Talos v1.11.5 deployment

---

## Overview

This checklist guides you through a fresh Talos cluster deployment with proper dual-drive storage configuration.

**Hardware**: UM690L with dual NVMe drives
- **256GB drive (/dev/nvme1n1)**: OS installation
- **1TB drive (/dev/nvme0n1)**: Persistent storage at `/var/mnt/storage`

**Software Stack**:
- Talos Linux v1.11.5 (with AMD GPU extensions)
- Kubernetes v1.34.1
- Network: 10.20.0.40/24

---

## Pre-Deployment: Prepare USB Boot Media

### 1. Download Talos Factory ISO

```bash
# On your workstation
wget https://factory.talos.dev/image/d9d97f8dca41cb2d47f2b5b6a34ea45725381bfd0b9b6a34b686418ef6682591/v1.11.5/metal-amd64.iso

# This Factory schematic includes:
# - AMD GPU driver (amdgpu)
# - AMD microcode
# - iSCSI tools
# - util-linux tools
```

### 2. Flash to USB Drive

**Windows**:
- Use Rufus (https://rufus.ie/)
- Select ISO
- Partition scheme: MBR
- Click START

**Linux**:
```bash
# Find USB device
lsblk

# Flash ISO (replace /dev/sdX with your USB device)
sudo dd if=metal-amd64.iso of=/dev/sdX bs=4M status=progress && sync
```

### 3. Boot UM690L from USB

1. Insert USB into UM690L
2. Power on and press **F2** or **DEL** to enter BIOS
3. In BIOS:
   - Navigate to **Security → Secure Boot**
   - Set to **Disabled**
   - Navigate to **Boot**
   - Move USB to first position
   - **Save and Exit** (F10)
4. Machine boots into Talos maintenance mode
5. Wait ~30 seconds for network initialization

---

## Phase 1: Clean Up Previous Deployment (If Exists)

### ⚠️ CRITICAL: Backup Current State

If you have an existing deployment and want to preserve any data:

```bash
# SSH to your management server (10.10.0.175)
ssh root@10.10.0.175
cd /home/agentic_lab/infrastructure/terraform/talos-cluster

# Backup terraform state
cp terraform.tfstate terraform.tfstate.backup.$(date +%Y%m%d_%H%M%S)

# Backup generated configs
tar -czf generated-backup-$(date +%Y%m%d_%H%M%S).tar.gz generated/
```

### Clean Slate Option 1: Destroy Existing Infrastructure

```bash
cd /home/agentic_lab/infrastructure/terraform/talos-cluster

# Destroy existing cluster (this will fail if node is not reachable, which is fine)
terraform destroy -auto-approve || true

# Clean generated files
rm -rf generated/*
```

### Clean Slate Option 2: Start Fresh

```bash
cd /home/agentic_lab/infrastructure/terraform/talos-cluster

# Move old state aside
mv terraform.tfstate terraform.tfstate.old
mv terraform.tfstate.backup terraform.tfstate.backup.old 2>/dev/null || true

# Clean generated files
rm -rf generated/*

# Terraform will create new state on next apply
```

---

## Phase 2: Verify Hardware Configuration

### 1. Get Node IP

Once UM690L boots from USB, it will get a DHCP address. Check your router/DHCP server for the assigned IP, or use:

```bash
# From your network
nmap -sn 10.20.0.0/24 | grep -B 2 "UM690L\|Minisforum"
```

### 2. Verify Disk Configuration

**⚠️ CRITICAL STEP - Always verify before deploying!**

```bash
# Replace <dhcp-ip> with the DHCP address from step 1
export DHCP_IP="10.20.0.xxx"  # Update this!

# Check disks
talosctl -n $DHCP_IP disks --insecure

# Expected output:
# DEV            SIZE    MODEL                      SERIAL
# /dev/nvme0n1   1.0 TB  [1TB Model Name]          [Serial1]
# /dev/nvme1n1   256 GB  [256GB Model Name]        [Serial2]
```

**VERIFY**:
- ✅ `/dev/nvme1n1` = **256GB** (will be OS disk)
- ✅ `/dev/nvme0n1` = **1TB** (will be data disk)

If drives are reversed, update `terraform.tfvars` accordingly!

### 3. Verify Network Interface

```bash
# Check network interfaces
talosctl -n $DHCP_IP get links --insecure

# Expected output should show eth0 (primary interface)
```

---

## Phase 3: Configure Terraform Variables

### 1. Navigate to Terraform Directory

```bash
cd /home/agentic_lab/infrastructure/terraform/talos-cluster
```

### 2. Create/Update terraform.tfvars

```bash
# Copy example if starting fresh
cp terraform.tfvars.example terraform.tfvars

# Edit with correct values
nano terraform.tfvars
```

**Critical variables to verify**:

```hcl
# Network (should match your environment)
node_ip           = "10.20.0.40"
network_gateway   = "10.20.0.1"
network_cidr      = 24
network_interface = "eth0"

# Cluster info
cluster_name    = "agentic-platform"
node_hostname   = "agentic-01"
talos_version   = "v1.11.5"
kubernetes_version = "v1.34.1"

# ⚠️ CRITICAL: Verify these match your hardware!
install_disk    = "/dev/nvme1n1"   # 256GB OS drive
disk_min_size   = 200

storage_disk          = "/dev/nvme0n1"  # 1TB data drive
storage_disk_min_size = 900
```

### 3. Verify Configuration Files

All configuration files should already be committed:

```bash
# Verify files are ready
ls -l main.tf variables.tf outputs.tf terraform.tfvars

# Check git status (should be clean)
cd /home/agentic_lab
git status
```

---

## Phase 4: Deploy Talos Cluster

### 1. Initialize Terraform

```bash
cd /home/agentic_lab/infrastructure/terraform/talos-cluster

# Initialize (downloads providers)
terraform init
```

### 2. Validate Configuration

```bash
# Validate syntax
terraform validate

# Should output: Success! The configuration is valid.
```

### 3. Review Terraform Plan

```bash
# Generate plan
terraform plan -out=deployment.plan

# CRITICAL CHECKS in plan output:
# ✅ install_disk = /dev/nvme1n1 (256GB)
# ✅ storage_disk = /dev/nvme0n1 (1TB)
# ✅ machine.disks configuration present
# ✅ kubelet.extraMounts configuration present
# ✅ node_ip = 10.20.0.40
```

### 4. Apply Configuration

```bash
# Apply the plan
terraform apply deployment.plan

# What happens:
# 1. Generates machine secrets (PKI)
# 2. Generates machine configuration with storage setup
# 3. Applies config to node (node downloads OS image ~200MB)
# 4. Node installs Talos to /dev/nvme1n1
# 5. Node formats /dev/nvme0n1 as XFS
# 6. Node mounts 1TB drive at /var/mnt/storage
# 7. Node reboots automatically
# 8. Kubernetes bootstraps
# 9. Kubeconfig generated

# Wait ~10-15 minutes for complete installation
```

### 5. Monitor Installation Progress

```bash
# Wait for node to come up at static IP
ping 10.20.0.40

# Once responding, check version
talosctl -n 10.20.0.40 version

# Check services
talosctl -n 10.20.0.40 services
```

---

## Phase 5: Verify Deployment

### 1. Export Configurations

```bash
# Export kubeconfig and talosconfig
export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig
export TALOSCONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/talosconfig

# Optional: Add to ~/.bashrc for persistence
echo 'export KUBECONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/kubeconfig' >> ~/.bashrc
echo 'export TALOSCONFIG=/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/talosconfig' >> ~/.bashrc
```

### 2. Verify Talos Health

```bash
# Check cluster health
talosctl health --nodes 10.20.0.40

# Expected output:
# ✓ API
# ✓ etcd
# ✓ kubelet

# Check all services
talosctl -n 10.20.0.40 services

# All services should show "Healthy" or "Running"
```

### 3. Verify Storage Configuration

**Critical verification - ensure storage is properly mounted!**

```bash
# 1. Check disks
talosctl -n 10.20.0.40 disks

# Expected:
# /dev/nvme0n1 - USER (data disk)
# /dev/nvme1n1 - SYSTEM (OS disk)

# 2. Verify mount point exists
talosctl -n 10.20.0.40 ls /var/mnt/storage

# Should show directory (may be empty)

# 3. Check disk is mounted
talosctl -n 10.20.0.40 mounts | grep storage

# Expected output:
# /dev/nvme0n1p1 on /var/mnt/storage type xfs (rw,relatime)

# 4. Check disk usage
talosctl -n 10.20.0.40 df | grep storage

# Expected: ~1TB available

# 5. Test write permissions
talosctl -n 10.20.0.40 bash -c "touch /var/mnt/storage/test.txt && ls -l /var/mnt/storage/test.txt"

# Should succeed and show file
```

### 4. Verify Kubernetes Cluster

```bash
# Check nodes
kubectl get nodes

# Expected output:
# NAME         STATUS     ROLES           AGE   VERSION
# agentic-01   NotReady   control-plane   2m    v1.34.1
# (NotReady is normal - no CNI installed yet)

# Check system pods
kubectl get pods -A

# Expected: kube-system pods running (CoreDNS will be Pending - normal)

# Check storage configuration output
cd /home/agentic_lab/infrastructure/terraform/talos-cluster
terraform output storage_configuration

# Verify correct disk assignments
```

### 5. Verify AMD GPU

```bash
# Check GPU device
talosctl -n 10.20.0.40 ls /dev/dri

# Expected: card0, renderD128

# Check amdgpu module loaded
talosctl -n 10.20.0.40 get kernelmodules | grep amdgpu

# Expected: amdgpu module loaded
```

---

## Phase 6: Deploy CNI and Core Platform

### 1. Deploy Cilium CNI

```bash
cd /home/agentic_lab

# Option 1: Direct deployment (for testing)
kubectl apply -f kubernetes/platform/cilium/cilium-quick-install.yaml

# Wait for Cilium pods
kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=cilium-agent -n kube-system --timeout=300s

# Verify nodes are Ready
kubectl get nodes
# Should show: agentic-01   Ready   control-plane
```

### 2. Deploy ArgoCD (GitOps)

```bash
cd /home/agentic_lab

# Deploy ArgoCD
kubectl apply -k kubernetes/bootstrap/

# Wait for ArgoCD to be ready
kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=argocd-server -n argocd --timeout=300s

# Get ArgoCD password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
echo

# Port forward to access UI
kubectl port-forward svc/argocd-server -n argocd 8080:443 &

# Open: https://localhost:8080
# Username: admin
# Password: (from command above)
```

### 3. Deploy Local Path Provisioner

```bash
# Deploy Local Path Provisioner
kubectl apply -f kubernetes/platform/local-path-provisioner/local-path-storage.yaml

# Wait for deployment
kubectl wait --for=condition=Available deployment/local-path-provisioner -n local-path-storage --timeout=120s

# Check provisioner logs
kubectl logs -n local-path-storage deployment/local-path-provisioner --tail=50

# Should show no errors
```

---

## Phase 7: Test Storage Provisioning

### 1. Create Test PVC

```bash
# Create test PVC
kubectl apply -f - <<EOF
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: test-storage
  namespace: default
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: local-path
  resources:
    requests:
      storage: 1Gi
EOF

# Wait for PVC to bind
kubectl wait --for=condition=Bound pvc/test-storage --timeout=60s

# Check PVC status
kubectl get pvc test-storage
# Should show: Bound
```

### 2. Verify PV Location

```bash
# Check PV path
PV_NAME=$(kubectl get pvc test-storage -o jsonpath='{.spec.volumeName}')
kubectl get pv $PV_NAME -o yaml | grep path

# Should show: /var/mnt/storage/local-path-provisioner/pvc-xxxxx

# Verify on node
talosctl -n 10.20.0.40 ls /var/mnt/storage/local-path-provisioner

# Should show: pvc-xxxxx directory
```

### 3. Test Pod Write/Read

```bash
# Create test pod
kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: test-storage-pod
  namespace: default
spec:
  containers:
  - name: test
    image: busybox
    command: ["/bin/sh", "-c"]
    args:
      - |
        echo "Storage test successful" > /data/test.txt
        cat /data/test.txt
        sleep 3600
    volumeMounts:
    - name: data
      mountPath: /data
  volumes:
  - name: data
    persistentVolumeClaim:
      claimName: test-storage
EOF

# Wait for pod
kubectl wait --for=condition=Ready pod/test-storage-pod --timeout=60s

# Check logs
kubectl logs test-storage-pod
# Expected: Storage test successful

# Verify data on node
talosctl -n 10.20.0.40 cat /var/mnt/storage/local-path-provisioner/pvc-*/test.txt
# Expected: Storage test successful
```

### 4. Test Persistence (Reboot Test)

```bash
# Note: Only run if you want to test reboot persistence

# Reboot node
talosctl -n 10.20.0.40 reboot

# Wait 3-5 minutes for reboot
# ...

# Check node is back
kubectl get nodes
# Should show Ready

# Check pod restarted
kubectl get pod test-storage-pod

# Verify data persisted
kubectl logs test-storage-pod
# Expected: Storage test successful
```

### 5. Cleanup Test Resources

```bash
# Delete test resources
kubectl delete pod test-storage-pod
kubectl delete pvc test-storage

# Verify cleanup
talosctl -n 10.20.0.40 ls /var/mnt/storage/local-path-provisioner
# Directory should be empty or gone
```

---

## Phase 8: Update Status and Documentation

### 1. Update CURRENT_STATUS.md

```bash
cd /home/agentic_lab

# Edit CURRENT_STATUS.md
nano CURRENT_STATUS.md

# Update with:
# - Deployment date
# - Talos v1.11.5 version
# - Kubernetes v1.34.1
# - Dual-drive storage configuration
# - Storage verification results
```

### 2. Commit Deployment Status

```bash
cd /home/agentic_lab

git add CURRENT_STATUS.md
git commit -m "Update status: Fresh Talos v1.11.5 deployment with dual-drive storage

Cluster Details:
- Node: agentic-01 at 10.20.0.40
- Talos: v1.11.5 with Factory schematic (AMD GPU)
- Kubernetes: v1.34.1
- Storage: Dual NVMe (256GB OS + 1TB data)
- Status: Healthy, storage verified, ready for Phase 2

Verified:
- /dev/nvme1n1 (256GB): OS installation
- /dev/nvme0n1 (1TB): Mounted at /var/mnt/storage
- Local Path Provisioner: Working
- PVC provisioning: Successful
- Data persistence: Confirmed

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

git push origin main
```

---

## Troubleshooting

### Issue: Node not responding after terraform apply

**Symptom**: Can't ping 10.20.0.40 after apply

**Solution**:
- Wait 10-15 minutes - node is downloading image and installing
- Check USB boot LED is active
- Node will reboot automatically when done
- If >20 minutes, reboot UM690L and check BIOS boot order

### Issue: Wrong disk sizes shown

**Symptom**: `talosctl disks` shows different sizes than expected

**Solution**:
- Verify actual hardware configuration
- Update terraform.tfvars with correct device paths
- Check if drives are swapped (/dev/nvme0n1 vs /dev/nvme1n1)
- Run `terraform plan` again to verify changes

### Issue: Storage mount not appearing

**Symptom**: `/var/mnt/storage` doesn't exist after deployment

**Solution**:
```bash
# Check Talos logs
talosctl -n 10.20.0.40 logs controller-runtime | grep -i disk

# Check machine config
talosctl -n 10.20.0.40 get mc -o yaml | grep -A10 disks

# Verify terraform applied storage config
terraform output storage_configuration

# If config missing, reapply
terraform apply -auto-approve
```

### Issue: PVC stuck in Pending

**Symptom**: Test PVC never binds

**Solution**:
```bash
# Check provisioner logs
kubectl logs -n local-path-storage deployment/local-path-provisioner

# Check ConfigMap path
kubectl get configmap -n local-path-storage local-path-config -o yaml | grep paths

# Should show: /var/mnt/storage/local-path-provisioner

# If wrong path, fix and restart:
kubectl apply -f kubernetes/platform/local-path-provisioner/local-path-storage.yaml
kubectl rollout restart deployment/local-path-provisioner -n local-path-storage
```

### Issue: Data lost after reboot

**Symptom**: Data doesn't survive node reboot

**Cause**: Mount at `/mnt/storage` instead of `/var/mnt/storage`

**Solution**:
- Verify mount point: `talosctl -n 10.20.0.40 mounts | grep storage`
- Should show `/var/mnt/storage` not `/mnt/storage`
- Talos only persists `/var` directory
- Redeploy with correct path if needed

---

## Next Steps After Successful Deployment

Once cluster is healthy and storage verified:

1. **Phase 2**: Deploy core platform services
   - Infisical (secrets management)
   - cert-manager (TLS certificates)
   - MinIO (backups)

2. **Phase 3**: Deploy AI workloads
   - Ollama (local LLM with AMD GPU)
   - LiteLLM (inference router)

3. **Phase 4**: Deploy data layer
   - Qdrant (vector database)
   - PostgreSQL (relational data)
   - Redis (caching)

4. **Phase 5-8**: See PHASES.md for complete roadmap

---

## Summary

**✅ Deployment Complete Checklist**:

- [ ] USB boot media created with Talos v1.11.5 Factory ISO
- [ ] UM690L booted from USB
- [ ] Disk configuration verified (256GB + 1TB)
- [ ] terraform.tfvars updated with correct paths
- [ ] Terraform apply successful
- [ ] Node responding at 10.20.0.40
- [ ] Talos health checks passing
- [ ] Storage mounted at /var/mnt/storage
- [ ] Disk usage shows ~1TB available
- [ ] Kubernetes cluster Ready
- [ ] AMD GPU detected
- [ ] Cilium CNI deployed
- [ ] ArgoCD deployed
- [ ] Local Path Provisioner deployed
- [ ] Test PVC binding successful
- [ ] Pod write/read operations working
- [ ] Data persistence verified (optional reboot test)
- [ ] CURRENT_STATUS.md updated
- [ ] Status committed to git

**Storage Configuration**:
- OS Disk: /dev/nvme1n1 (256GB) → Talos installation
- Data Disk: /dev/nvme0n1 (1TB) → /var/mnt/storage → PVCs

**Ready for Phase 2**: Core platform services deployment

---

**For questions or issues**: See BARE_METAL_INSTALL.md (479 lines) for detailed troubleshooting.
