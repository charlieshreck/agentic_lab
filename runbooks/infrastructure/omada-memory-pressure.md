# Omada Container Memory Pressure Alert

## Alert Threshold
- **Condition**: Container memory at 85%+ (warning) or 90%+ (critical)
- **Typical Value**: 88.4% with 3GB allocation
- **Expected After Fix**: <60% with 4GB allocation

---

## Root Cause

### Current State
- **Omada LXC Allocation**: 3GB (VMID 200 on Ruapehu)
- **Intended Allocation**: 4GB (per Terraform config)
- **Status**: Terraform drift—IaC and runtime are out of sync

### Why This Happens
The `prod_homelab/infrastructure/terraform/omada.tf` specifies:
```hcl
memory = 4096  # 4GB - Omada + MongoDB + Java memory footprint increased to prevent 85%+ usage
```

But the actual Omada LXC container is provisioned with only 3GB, causing memory pressure alerts when Java + MongoDB workloads spike.

---

## Investigation Steps

### Verify Drift
```bash
# Check allocated memory (max)
curl -s -u root@pam:PASSWORD https://10.10.0.10:8006/api2/json/nodes/Ruapehu/lxc/200/status/current \
  | jq '.data.maxmem / 1024 / 1024 / 1024'  # Should show 3 (actual) vs 4 (intended)

# Check current usage
kubectl exec -n monitoring <pod> -- curl -s http://localhost:9090/api/v1/query \
  '?query=omada_container_memory_bytes'
```

### Check Omada Logs for OOM Events
```bash
ssh root@10.10.0.3 "cat /var/log/syslog | grep -i 'out of memory\|oom\|killed'"
```

---

## Solution: Apply Terraform

### One-Time Setup (Credentials)
Get secrets from Infisical `/infrastructure/proxmox-ruapehu`:
- `PASSWORD` → `TF_VAR_proxmox_password`
- `CLIENT_ID/CLIENT_SECRET` → Infisical auth

### Apply Fix
```bash
cd /home/prod_homelab/infrastructure/terraform

# Set credentials as environment variables
export TF_VAR_proxmox_password="<from Infisical>"
export TF_VAR_infisical_client_id="<from Infisical>"
export TF_VAR_infisical_client_secret="<from Infisical>"
export TF_VAR_dockerhub_password="<from Infisical>"

# Plan and verify Omada change
terraform plan -out=prod.plan | grep -A 5 omada

# Apply (this resizes the LXC from 3GB → 4GB, requires brief Omada downtime)
terraform apply prod.plan
```

### Expected Changes
- **Before**: `modules.omada.proxmox_lxc_container.omada` memory: 3GB
- **After**: Same resource, memory: 4GB
- **Downtime**: ~30 seconds (LXC restart required for memory resize)

---

## Prevention: Alert Rule

### Prometheus Alert (for 85% threshold)
Add to `/home/prod_homelab/kubernetes/platform/prometheus/rules.yaml`:
```yaml
- alert: OmadaMemoryPressure
  expr: omada_container_memory_percent > 85
  for: 5m
  labels:
    severity: warning
    component: omada
  annotations:
    summary: "Omada container memory at {{ $value }}%"
    description: "Omada LXC (VMID 200) memory usage exceeds 85%. Either Terraform drift has occurred (check memory allocation is 4GB) or workload has grown. See runbook: omada-memory-pressure.md"
```

### Action Items
- [ ] Create/update Prometheus rule
- [ ] Sync via ArgoCD (push to `prod_homelab/kubernetes/...`)
- [ ] Test alert fires at 85%+ (can artificially trigger if needed)

---

## Monitoring After Fix

### Verify Success
```bash
# 1. Check new allocation
kubectl exec -n monitoring <pod> -- curl -s http://localhost:9090/api/v1/query \
  '?query=omada_container_maxmem_bytes' | jq '.[0].value[1] / 1024 / 1024 / 1024'  # Should show 4

# 2. Confirm alert clears
# Alert should auto-clear within 5-10 minutes once memory usage drops below 85%

# 3. Monitor for 1 week
# Alert should NOT re-trigger if Omada workloads remain stable
```

---

## Related Incidents
- **#160 (Ruapehu High Memory)**: Broader Proxmox host memory exhaustion—different root cause (over-allocated VMs)
- **#155 (Omada Memory)**: Container-level drift (this runbook)

---

## References
- **Terraform Config**: `/home/prod_homelab/infrastructure/terraform/omada.tf` (line 21)
- **Omada LXC**: VMID 200, IP 10.10.0.3, Ruapehu node
- **Monitoring**: Alert source "pulse" (error-hunter LangGraph)
