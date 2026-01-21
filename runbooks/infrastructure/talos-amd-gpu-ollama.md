# Talos AMD GPU Support for Ollama

## Overview

This runbook documents how to enable AMD GPU acceleration for Ollama on a Talos Linux bare metal cluster. The setup uses Talos system extensions for GPU drivers and the Ollama ROCm image for AMD GPU inference.

## Hardware

- **Node**: UM690L bare metal
- **CPU**: AMD Ryzen 9 6900HX (8C/16T)
- **GPU**: AMD Radeon 680M (RDNA2 integrated, gfx1035)
- **VRAM**: 2GB shared memory
- **Network**: 10.20.0.40 (agentic cluster)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Talos Linux v1.11.5                       │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              System Extensions                       │    │
│  │  • amdgpu (kernel module)                           │    │
│  │  • amd-ucode (microcode updates)                    │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              /dev/dri/                               │    │
│  │  • card0 (GPU device)                               │    │
│  │  • renderD128 (render node)                         │    │
│  └─────────────────────────────────────────────────────┘    │
│                           │                                  │
│                           ▼                                  │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Kubernetes Pod                          │    │
│  │  ┌───────────────────────────────────────────────┐  │    │
│  │  │  Ollama (ollama/ollama:0.5.4-rocm)            │  │    │
│  │  │  • HSA_OVERRIDE_GFX_VERSION=10.3.0            │  │    │
│  │  │  • /dev/dri mounted as hostPath               │  │    │
│  │  │  • privileged: true                           │  │    │
│  │  └───────────────────────────────────────────────┘  │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

- Talos Linux v1.11.x or later
- AMD GPU with RDNA/RDNA2/RDNA3 architecture
- Access to Talos Factory for custom images

## Step 1: Generate Talos Factory Image with GPU Extensions

### 1.1 Create Schematic

Visit [Talos Factory](https://factory.talos.dev/) and create a schematic with:

**System Extensions:**
- `siderolabs/amdgpu` - AMD GPU kernel module
- `siderolabs/amd-ucode` - AMD microcode updates

**Schematic ID** (for amdgpu + amd-ucode):
```
b6ab12edc37d4a92a0705f4f2f12952d5a1a3f38b51783422b56810b60e230fd
```

### 1.2 Factory Image URL Format

```
factory.talos.dev/installer/<schematic-id>:<talos-version>
```

Example:
```
factory.talos.dev/installer/b6ab12edc37d4a92a0705f4f2f12952d5a1a3f38b51783422b56810b60e230fd:v1.11.5
```

## Step 2: Update Terraform Configuration

### 2.1 Machine Configuration

Update `infrastructure/terraform/talos-cluster/main.tf`:

```hcl
data "talos_machine_configuration" "this" {
  # ... existing config ...

  config_patches = [
    yamlencode({
      machine = {
        install = {
          # Factory image with AMD GPU extensions
          image = "factory.talos.dev/installer/b6ab12edc37d4a92a0705f4f2f12952d5a1a3f38b51783422b56810b60e230fd:${var.talos_version}"
          wipe  = true
          diskSelector = {
            model = "Samsung*"  # OS disk
          }
        }
        # Load amdgpu kernel module
        kernel = {
          modules = [{
            name = "amdgpu"
          }]
        }
        sysctls = {
          "vm.max_map_count" = "262144"  # For Qdrant
        }
      }
    }),
    # ... other patches ...
  ]
}
```

### 2.2 Stable Disk Configuration

**Important**: NVMe device names (`/dev/nvme0n1`, `/dev/nvme1n1`) can swap across reboots. Use stable `/dev/disk/by-id/` paths:

```hcl
# Storage disk configuration patch
yamlencode({
  machine = {
    disks = [{
      # Use stable by-id path instead of /dev/nvmeXn1
      device = "/dev/disk/by-id/nvme-KINGSTON_OM8TAP41024K1-A00_50026B76874B7249"
      partitions = [{
        mountpoint = "/var/mnt/storage"
      }]
    }]

    kubelet = {
      extraMounts = [{
        destination = "/var/mnt/storage"
        type        = "bind"
        source      = "/var/mnt/storage"
        options     = ["bind", "rshared", "rw"]
      }]
    }
  }
})
```

**Finding stable disk paths:**
```bash
talosctl -n 10.20.0.40 ls /dev/disk/by-id/
```

## Step 3: Upgrade Talos Node

### 3.1 Apply Upgrade

```bash
talosctl --talosconfig /path/to/talosconfig \
  -n 10.20.0.40 \
  upgrade \
  --image factory.talos.dev/installer/b6ab12edc37d4a92a0705f4f2f12952d5a1a3f38b51783422b56810b60e230fd:v1.11.5
```

**Note**: The upgrade command may report an error due to connection loss during reboot. This is expected - verify success manually.

### 3.2 Verify Extensions

```bash
# Check installed extensions
talosctl -n 10.20.0.40 get extensions

# Expected output:
# NODE         NAMESPACE   TYPE              ID   VERSION   NAME          VERSION
# 10.20.0.40   runtime     ExtensionStatus   0    1         amdgpu        20251021-v1.11.5
# 10.20.0.40   runtime     ExtensionStatus   1    1         amd-ucode     20251021
```

### 3.3 Verify GPU Device

```bash
# Check /dev/dri exists
talosctl -n 10.20.0.40 ls /dev/dri

# Expected:
# card0
# renderD128
```

## Step 4: Configure Ollama StatefulSet

### 4.1 Key Configuration Points

**Image**: Must use ROCm variant for AMD GPU support
```yaml
image: ollama/ollama:0.5.4-rocm  # NOT ollama/ollama:0.5.4
```

**Environment Variables**:
```yaml
env:
- name: HSA_OVERRIDE_GFX_VERSION
  value: "10.3.0"  # Required for RDNA2 (gfx1035)
- name: OLLAMA_GPU_LAYERS
  value: "999"     # Offload all layers to GPU
- name: OLLAMA_NUM_PARALLEL
  value: "4"       # Parallel request handling
```

**Volume Mounts**:
```yaml
volumeMounts:
- name: dri
  mountPath: /dev/dri

volumes:
- name: dri
  hostPath:
    path: /dev/dri
    type: Directory
```

**Security Context**:
```yaml
securityContext:
  privileged: true  # Required for GPU access
```

### 4.2 Complete StatefulSet Example

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: ollama
  namespace: ai-platform
spec:
  replicas: 1
  serviceName: ollama
  selector:
    matchLabels:
      app: ollama
  template:
    metadata:
      labels:
        app: ollama
    spec:
      containers:
      - name: ollama
        image: ollama/ollama:0.5.4-rocm
        ports:
        - containerPort: 11434
          name: http
        env:
        - name: OLLAMA_HOST
          value: "0.0.0.0:11434"
        - name: OLLAMA_MODELS
          value: "/root/.ollama/models"
        - name: OLLAMA_KEEP_ALIVE
          value: "5m"
        - name: OLLAMA_NUM_PARALLEL
          value: "4"
        - name: HSA_OVERRIDE_GFX_VERSION
          value: "10.3.0"
        - name: OLLAMA_GPU_LAYERS
          value: "999"
        securityContext:
          privileged: true
        resources:
          requests:
            cpu: "2000m"
            memory: "8Gi"
          limits:
            cpu: "8000m"
            memory: "16Gi"
        volumeMounts:
        - name: ollama-models
          mountPath: /root/.ollama
        - name: dri
          mountPath: /dev/dri
        readinessProbe:
          httpGet:
            path: /
            port: 11434
          initialDelaySeconds: 10
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /
            port: 11434
          initialDelaySeconds: 30
          periodSeconds: 30
      volumes:
      - name: dri
        hostPath:
          path: /dev/dri
          type: Directory
  volumeClaimTemplates:
  - metadata:
      name: ollama-models
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: local-path
      resources:
        requests:
          storage: 100Gi
```

## Step 5: Verify GPU Acceleration

### 5.1 Check Ollama Logs

```bash
kubectl logs -n ai-platform ollama-0 | grep -i "rocm\|gpu\|offload"
```

**Expected output:**
```
msg="inference compute" id=0 library=rocm compute=gfx1035 name=1002:1681 total="2.0 GiB" available="2.0 GiB"
msg="offload to rocm" layers.requested=-1 layers.model=29 layers.offload=4
msg="starting llama server" cmd="/usr/lib/ollama/runners/rocm_avx/ollama_llama_server ..."
```

### 5.2 Test Inference

```bash
kubectl exec -n ai-platform ollama-0 -- ollama run qwen2.5:7b "Hello, are you using GPU?"
```

## Troubleshooting

### GPU Not Detected

**Symptom**: `no compatible amdgpu devices detected`

**Causes & Solutions**:

1. **Extensions not installed**
   ```bash
   talosctl -n 10.20.0.40 get extensions
   ```
   If missing, re-upgrade with factory image.

2. **Kernel module not loaded**
   ```bash
   talosctl -n 10.20.0.40 read /proc/modules | grep amdgpu
   ```
   Ensure `kernel.modules` config includes `amdgpu`.

3. **/dev/dri not mounted in pod**
   Check volume mounts in StatefulSet.

4. **Wrong Ollama image**
   Must use `ollama/ollama:X.X.X-rocm`, not standard image.

### Disk Names Swapping

**Symptom**: `filesystem type mismatch: vfat != xfs` after reboot

**Cause**: NVMe device names are not stable across reboots.

**Solution**: Use `/dev/disk/by-id/` paths in Terraform:
```bash
# Find stable path
talosctl -n 10.20.0.40 ls /dev/disk/by-id/ | grep nvme
```

### HSA Version Mismatch

**Symptom**: `HSA_OVERRIDE_GFX_VERSION not set` warnings

**Solution**: Set `HSA_OVERRIDE_GFX_VERSION` environment variable:

| GPU Architecture | GFX Version | HSA Override |
|-----------------|-------------|--------------|
| RDNA (Navi 10)  | gfx1010     | 10.1.0       |
| RDNA2 (Navi 2x) | gfx1030-1035| 10.3.0       |
| RDNA3 (Navi 3x) | gfx1100+    | 11.0.0       |

### Limited VRAM

**Symptom**: Only partial layers offloaded to GPU

**Cause**: Integrated GPU shares system memory (2GB default allocation)

**Mitigation**:
- Use smaller models (7B or less)
- Embedding models fit entirely in 2GB
- Large models will use CPU for remaining layers

## Performance Notes

### Radeon 680M (2GB VRAM)

| Model | Layers | GPU Offload | Performance |
|-------|--------|-------------|-------------|
| nomic-embed-text | 13 | 13/13 (100%) | Full GPU |
| qwen2.5:7b | 29 | 4/29 (14%) | Hybrid CPU+GPU |
| llama3.1:8b | 33 | 4/33 (12%) | Hybrid CPU+GPU |

For larger models, consider:
- Discrete GPU with more VRAM
- Multiple smaller specialized models
- CPU-only with AVX2 optimization

## Related Documentation

- [Talos Factory](https://factory.talos.dev/)
- [Talos System Extensions](https://www.talos.dev/v1.11/talos-guides/configuration/system-extensions/)
- [Ollama ROCm Support](https://github.com/ollama/ollama/blob/main/docs/gpu.md)
- [AMD ROCm Documentation](https://rocm.docs.amd.com/)

## Changelog

| Date | Change |
|------|--------|
| 2026-01-21 | Initial documentation |
| 2026-01-21 | Added stable disk path configuration |
