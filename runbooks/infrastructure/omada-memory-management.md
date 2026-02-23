# Omada Controller Memory Management

## Alert
**Type**: Container Memory Warning
**Threshold**: 85%
**Alert ID**: #155

## Root Cause
The Omada controller LXC runs:
- **Java runtime** (Omada controller service - high memory footprint)
- **MongoDB** (database backend - memory-intensive)
- **System services** (logs, networking, etc.)

These services combined consume ~1.7GB of the original 2GB allocation, causing the container to consistently run at 85%+ memory utilization.

## Symptoms
- Memory usage stays at 85%+ (warning threshold)
- Swap usage increases (120MB of 512MB swap used)
- Risk of OOMKill if traffic spikes cause temporary memory spikes
- Container may experience slowdowns under high load

## Solution: Increase Memory Allocation

### Step 1: Update Terraform (COMPLETED)
**File**: `/home/prod_homelab/infrastructure/terraform/omada.tf`

Changed:
```hcl
# Before
memory = 2048  # 2GB - Omada + MongoDB + Java requires >1GB

# After
memory = 4096  # 4GB - Omada + MongoDB + Java memory footprint increased to prevent 85%+ usage
```

### Step 2: Apply via GitOps
The change is committed to git and will be automatically applied by:
1. Push to GitHub → CI/CD detects change
2. Terraform plan validates the change
3. `terraform apply` increases LXC memory to 4GB
4. Proxmox reconfigures VMID 200 without requiring container restart

**Status**: Committed in `eea3241` (2026-02-22), awaiting `terraform apply` deployment

### Step 3: Verify Memory After Upgrade
```bash
# Check container status
proxmox-cli get-container-status --vmid 200

# SSH into container and verify
ssh root@10.10.0.10 "pct exec 200 -- free -h"

# Expected output:
# Mem: 4.0Gi  ~1.7Gi   ~2.3Gi
# Usage: 1.7 / 4.0 = 42.5% (healthy)
```

## Prevention
- Monitor `omada` container memory weekly
- Alert threshold is appropriately set at 85% (warns before OOMKill at 100%)
- If memory stays >75% after upgrade, investigate:
  - Large switch topology (many devices/clients)
  - High API activity (frequent polling)
  - Database growth (retention policies)

## Related
- **Component**: Omada controller (VMID 200 on Ruapehu)
- **Network**: 10.10.0.0/24 (prod network)
- **IP**: 10.10.0.3
- **Service**: TP-Link TL-SG3428X-M2 management (19 MCP tools in infrastructure-mcp)
