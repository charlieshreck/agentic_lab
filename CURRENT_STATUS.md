# Current Status - Agentic Lab Project

**Last Updated**: 2025-12-31
**Status**: Ready for Talos installation
**Next Session**: Continue with bare metal deployment

---

## What Has Been Completed

### 1. Repository Setup ✅

- **GitHub Repository**: https://github.com/charlieshreck/agentic_lab
- **SSH Key Added**: Server can push to GitHub
- **Commits**:
  - `2fb8118` - Initial repository structure
  - `9366ad8` - Bare metal Talos configuration

### 2. Documentation Created ✅

All documentation is complete and committed:

- **CLAUDE.md** - Complete project overview and architecture
- **README.md** - Quick start guide
- **BARE_METAL_INSTALL.md** - 479-line detailed installation guide
- **GITOPS-WORKFLOW.md** - Mandatory GitOps rules
- **PHASES.md** - 8-phase implementation roadmap
- **ENVIRONMENT_VARIABLES.md** - Secrets management guide
- **CURRENT_STATUS.md** - This file (status tracking)

### 3. Talos Configuration Generated ✅

**Location**: `/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/`

**Files Ready**:
- ✅ `controlplane-final.yaml` - Complete machine config with AMD GPU
- ✅ `talosconfig` - Talos CLI credentials
- ✅ `INSTALLATION_STEPS.md` - Step-by-step installation guide
- ✅ `README.txt` - Quick reference

**Factory Schematic Created**:
- **ID**: `d9d97f8dca41cb2d47f2b5b6a34ea45725381bfd0b9b6a34b686418ef6682591`
- **Extensions**: AMD GPU driver, AMD microcode, iSCSI tools, util-linux tools
- **Kernel Args**: Optimized for Radeon 680M GPU

### 4. Network Configuration ✅

- **IP Address**: 10.20.0.109/24
- **Gateway**: 10.20.0.1
- **DNS**: 1.1.1.1, 8.8.8.8
- **Hostname**: agentic-01
- **Network**: Isolated from prod (10.10.0.0/24) and monitoring (10.30.0.0/24)

---

## What's Ready to Deploy

### Hardware Target

- **Device**: UM690L
- **CPU**: AMD Ryzen 9 6900HX (8C/16T)
- **RAM**: 32GB DDR5
- **Storage**: 1.5TB NVMe (/dev/nvme0n1)
- **GPU**: AMD Radeon 680M (RDNA2) - configured for Ollama

### Installation Files

**IMPORTANT**: These files are in the `generated/` directory on the server (10.10.0.175).
They are **NOT committed to git** (gitignored for security - contain credentials).

**Location**: `/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/`

```
generated/
├── INSTALLATION_STEPS.md      # Complete guide with troubleshooting
├── README.txt                  # Quick reference
├── controlplane-final.yaml     # Machine configuration (12KB) - CREDENTIALS
├── talosconfig                 # CLI credentials (copied to ~/.talos/config) - CREDENTIALS
├── controlplane.yaml           # Base config (not used, keep for reference)
├── controlplane-patch.yaml     # Patch file (merged into final)
└── worker.yaml                 # For future expansion (not needed now)
```

**If you need to regenerate these files**:
```bash
cd /home/agentic_lab/infrastructure/terraform/talos-cluster
rm -rf generated/*
talosctl gen config agentic-platform https://10.20.0.109:6443 --output-dir generated/
# Then apply the patch as documented in git commit 9366ad8
```

### Factory ISO Download Link

**IMPORTANT**: Copy this URL to download the ISO on your Windows laptop:

```
https://factory.talos.dev/image/d9d97f8dca41cb2d47f2b5b6a34ea45725381bfd0b9b6a34b686418ef6682591/v1.8.1/metal-amd64.iso
```

**File Size**: ~200MB
**Tool**: Use Rufus (https://rufus.ie/) to flash to USB drive (8GB+)

---

## Tomorrow's Installation Steps

### Prerequisites Before You Start

1. **USB Drive**: 8GB+ for Talos ISO
2. **Rufus**: Download from https://rufus.ie/ on Windows laptop
3. **Network Access**: Ensure UM690L can reach 10.20.0.1 gateway
4. **Monitor/Keyboard**: For UM690L BIOS configuration

---

### Step-by-Step Installation

#### 1. Download Factory ISO (Windows Laptop)

Open this URL in browser:
```
https://factory.talos.dev/image/d9d97f8dca41cb2d47f2b5b6a34ea45725381bfd0b9b6a34b686418ef6682591/v1.8.1/metal-amd64.iso
```

Save to: `C:\Users\Mrlon\Downloads\talos-factory-amd.iso`

#### 2. Flash ISO to USB (Windows Laptop)

1. Open **Rufus**
2. Select downloaded ISO
3. Select USB drive
4. Partition scheme: **MBR**
5. Click **START**
6. Wait for completion

#### 3. Boot UM690L from USB

1. Insert USB into UM690L
2. Power on, press **F2** or **DEL** to enter BIOS
3. In BIOS:
   - Navigate to **Security → Secure Boot**
   - Set to **Disabled**
   - Navigate to **Boot**
   - Move USB to first position
   - **Save and Exit** (F10)
4. UM690L boots into Talos maintenance mode
5. Wait ~30 seconds for network initialization

#### 4. Apply Configuration (From Server 10.10.0.175)

SSH to the server (10.10.0.175) and run:

```bash
# Navigate to config directory
cd /home/agentic_lab/infrastructure/terraform/talos-cluster/generated/

# Verify talosconfig is in place
cat ~/.talos/config | grep agentic-platform
# Should show: context: agentic-platform

# Apply the configuration
talosctl apply-config --insecure \
  --nodes 10.20.0.109 \
  --file controlplane-final.yaml

# Expected output:
# Applied configuration to node 10.20.0.109
```

**What happens next**:
- Node downloads Factory image (~200MB)
- Installs Talos to /dev/nvme0n1
- Configures network (10.20.0.109)
- Reboots automatically
- **Wait 10-15 minutes**

#### 5. Verify Node is Back Online

```bash
# Wait for reboot, then check connectivity
ping 10.20.0.109
# Should respond after ~10 minutes

# Check Talos is responding
talosctl --nodes 10.20.0.109 version
# Should show Talos v1.8.1
```

#### 6. Bootstrap Kubernetes Cluster

```bash
# Bootstrap etcd (only run once!)
talosctl bootstrap --nodes 10.20.0.109

# Wait 2-3 minutes for Kubernetes to initialize
```

#### 7. Retrieve Kubeconfig

```bash
# Get kubeconfig
talosctl kubeconfig ~/.kube/agentic-cluster --force

# Set as active kubeconfig
export KUBECONFIG=~/.kube/agentic-cluster

# Verify cluster
kubectl get nodes
# Expected output:
# NAME         STATUS   ROLES           AGE   VERSION
# agentic-01   Ready    control-plane   2m    v1.31.1
```

#### 8. Verify Cluster Health

```bash
# Check Talos health
talosctl health --nodes 10.20.0.109
# Expected:
# [✓] API
# [✓] etcd
# [✓] kubelet

# Check system pods
kubectl get pods -A
# Should see kube-system pods running
# Note: CoreDNS will be Pending (waiting for CNI - this is normal)
```

#### 9. Remove USB Drive (Optional)

Once cluster is healthy:

```bash
# Shutdown node
talosctl shutdown --nodes 10.20.0.109

# Remove USB drive
# Power on UM690L
# Will boot from NVMe at 10.20.0.109
```

---

## After Successful Installation

### Verify AMD GPU

```bash
# Check AMD GPU kernel module loaded
talosctl --nodes 10.20.0.109 get kernelmodules | grep amdgpu
# Should show: amdgpu module loaded

# Check GPU device
talosctl --nodes 10.20.0.109 ls /dev/dri
# Should show: card0, renderD128
```

### Commit Installation Status

```bash
cd /home/agentic_lab

# Update this status file
vim CURRENT_STATUS.md
# Update "What Has Been Completed" section with cluster installation

# Commit
git add CURRENT_STATUS.md
git commit -m "Update status: Talos cluster successfully deployed

Cluster Details:
- Node: agentic-01 at 10.20.0.109
- Talos: v1.8.1 with Factory schematic (AMD GPU)
- Kubernetes: v1.31.1
- Status: Healthy, ready for Phase 2

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

git push
```

### Next: Phase 2 - Core Services

Once cluster is healthy, proceed to deploy ArgoCD:

See **PHASES.md** Phase 2 for instructions.

Quick preview:
```bash
# Deploy ArgoCD
cd /home/agentic_lab
kubectl apply -k kubernetes/bootstrap/

# Note: You'll need to create the bootstrap manifests first
# This will be done in Phase 2
```

---

## Troubleshooting Common Issues

### Issue: Node not responding after apply-config

**Symptom**: Can't ping 10.20.0.109 after applying config

**Solution**:
- Wait 10-15 minutes - node is installing to disk
- Check USB boot LED is active (downloading image)
- Node will reboot automatically when done

### Issue: Bootstrap fails with "already bootstrapped"

**Symptom**: `error: already bootstrapped`

**Solution**:
- Skip bootstrap step
- Proceed directly to kubeconfig retrieval
- This means a previous attempt partially succeeded

### Issue: Kubeconfig retrieval fails

**Symptom**: `error: connection refused`

**Solution**:
```bash
# Check node is actually running Kubernetes
talosctl --nodes 10.20.0.109 service kubelet

# If not running, bootstrap again
talosctl bootstrap --nodes 10.20.0.109

# Wait 3 minutes, then retry kubeconfig
```

### Issue: CoreDNS pods stuck in Pending

**Symptom**: `kubectl get pods -n kube-system` shows CoreDNS Pending

**Solution**:
- **This is expected!** No CNI installed yet
- Will be resolved in Phase 2 when Cilium is deployed via ArgoCD

### Issue: Can't reach cluster from server

**Symptom**: `kubectl` commands timeout

**Solution**:
```bash
# Verify kubeconfig is set
echo $KUBECONFIG
# Should be: /root/.kube/agentic-cluster

# Check kubeconfig contents
kubectl config view
# Should show server: https://10.20.0.109:6443

# Test direct connectivity
curl -k https://10.20.0.109:6443/version
# Should return Kubernetes version JSON
```

---

## Important File Locations

### On Server (10.10.0.175)

- **Repository**: `/home/agentic_lab/`
- **Talos Config**: `~/.talos/config`
- **Kubeconfig**: `~/.kube/agentic-cluster`
- **Generated Files**: `/home/agentic_lab/infrastructure/terraform/talos-cluster/generated/`

### On Windows Laptop (10.10.0.122)

- **ISO Download**: `C:\Users\Mrlon\Downloads\talos-factory-amd.iso`
- **WinSCP Access**: 10.10.0.175 (to copy files if needed)

---

## Environment Variables to Set

After installation, add to `~/.bashrc` or set for each session:

```bash
# Talos configuration
export TALOSCONFIG=~/.talos/config

# Kubernetes configuration
export KUBECONFIG=~/.kube/agentic-cluster

# Optional: Add to shell profile
echo 'export TALOSCONFIG=~/.talos/config' >> ~/.bashrc
echo 'export KUBECONFIG=~/.kube/agentic-cluster' >> ~/.bashrc
```

---

## Quick Reference Commands

### Talos Commands

```bash
# Check node health
talosctl health --nodes 10.20.0.109

# View node version
talosctl --nodes 10.20.0.109 version

# Check service status
talosctl --nodes 10.20.0.109 service

# View logs
talosctl --nodes 10.20.0.109 logs kubelet

# Dashboard (interactive)
talosctl dashboard --nodes 10.20.0.109
```

### Kubernetes Commands

```bash
# Get nodes
kubectl get nodes

# Get all pods
kubectl get pods -A

# Get system pods
kubectl get pods -n kube-system

# Describe node
kubectl describe node agentic-01

# Check cluster info
kubectl cluster-info
```

---

## What to Check Tomorrow Morning

Before starting installation:

1. **Server Access**: Can you SSH to 10.10.0.175?
2. **Git Status**: `cd /home/agentic_lab && git status` should be clean
3. **Files Ready**: `ls generated/` should show all config files
4. **ISO Downloaded**: Check ISO is on Windows laptop
5. **USB Ready**: Have 8GB+ USB drive available
6. **Rufus Downloaded**: Have Rufus installed on Windows

---

## Project Architecture Reminder

### Network Layout

```
10.20.0.0/24 - Agentic Platform (NEW - THIS PROJECT)
├── 10.20.0.1    - Gateway
├── 10.20.0.109  - Talos cluster (UM690L)
└── Future expansion

Related Networks:
- 10.10.0.0/24 - Production cluster (prod_homelab)
- 10.30.0.0/24 - Monitoring cluster (monit_homelab)
```

### Platform Components (Future Phases)

- **Phase 2**: ArgoCD, Infisical, cert-manager, storage
- **Phase 3**: Ollama (with AMD GPU), LiteLLM
- **Phase 4**: Qdrant vector database, Redis, PostgreSQL
- **Phase 5**: MCP servers (Home Assistant, arr suite, infrastructure)
- **Phase 6**: LangGraph orchestrator, Telegram service
- **Phase 7**: Go live in verbose mode
- **Phase 8**: Progressive autonomy

---

## Support Resources

### Documentation

- **Talos Docs**: https://www.talos.dev/
- **Factory**: https://factory.talos.dev/
- **This Project**: See `docs/` directory (14 architecture files)

### Detailed Guides

- **Installation**: `generated/INSTALLATION_STEPS.md`
- **Bare Metal**: `BARE_METAL_INSTALL.md`
- **Phases**: `PHASES.md`
- **GitOps**: `GITOPS-WORKFLOW.md`

### GitHub Repository

- **URL**: https://github.com/charlieshreck/agentic_lab
- **Branches**: main
- **Latest Commit**: 9366ad8 (bare metal configuration)

---

## Session Summary

### What We Accomplished Today

1. ✅ Created complete repository structure
2. ✅ Generated Talos configuration with AMD GPU support
3. ✅ Created Factory schematic for UM690L
4. ✅ Prepared all installation files
5. ✅ Committed everything to GitHub
6. ✅ Documented status for tomorrow

### What's Next Tomorrow

1. Download Factory ISO (~5 minutes)
2. Flash USB drive (~10 minutes)
3. Boot UM690L and apply config (~15 minutes)
4. Wait for installation (~10 minutes)
5. Bootstrap cluster (~5 minutes)
6. Verify deployment (~5 minutes)

**Total Time**: ~50 minutes

---

## Contact Points if Issues Arise

If you encounter problems tomorrow:

1. **Read generated/INSTALLATION_STEPS.md** - Has troubleshooting section
2. **Check this file** - CURRENT_STATUS.md
3. **Review git log**: `git log --oneline` to see what was done
4. **Talos docs**: https://www.talos.dev/v1.8/introduction/getting-started/

---

**Status**: All files ready, documentation complete, ready to install tomorrow

**Next Step**: Download ISO and flash USB

**Good luck! The installation should be straightforward following INSTALLATION_STEPS.md**
