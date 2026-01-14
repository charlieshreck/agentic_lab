# Lessons Learned: Comprehensive Monitoring Implementation

**Date**: 2026-01-14
**Project**: Kernow Homelab Monitoring
**Plan Reference**: `/root/.claude/plans/iridescent-painting-kahn.md`

---

## Summary

Implemented comprehensive monitoring across the Kernow homelab, filling gaps identified in the 2026-01-13 plan. Deployed Coroot agents to the agentic cluster, added 17 MCP health endpoints to Gatus, and deployed Beszel agents to 8 systems.

---

## What Went Well

### 1. Beszel Agent Deployment
- Official installer script (`get.beszel.dev`) worked reliably on standard Linux systems
- API-based system creation allowed automation without manual UI interaction
- Token-based authentication (system ID as token) simplified deployment

### 2. Cross-Cluster Monitoring
- Beszel hub on monit cluster (10.30.0.20) successfully monitors systems on:
  - Prod network (10.10.0.0/24)
  - Agentic network (10.20.0.0/24)
  - Monit network (10.30.0.0/24)
- Network routing between clusters worked without additional firewall rules

### 3. Coroot eBPF Integration
- Coroot node agent successfully deployed to agentic cluster
- Required sysctl (`net.netfilter.nf_conntrack_events=1`) identified and fixed via Talos machineconfig

---

## Issues Encountered and Solutions

### 1. S.M.A.R.T. Monitoring Not Working (NVMe)

**Symptom**: NVMe disks showing "UNKNOWN" status in Beszel /smart page, SATA drives work fine
**Root Cause**: Multiple permission issues for NVMe SMART:
1. Beszel agent runs as non-root user with `ProtectSystem=strict` systemd sandboxing
2. NVMe character devices (`/dev/nvme0`, etc.) are root-only by default
3. NVMe admin ioctls require `CAP_SYS_ADMIN`, not just `CAP_SYS_RAWIO`

**Solution - Two Parts**:

Part 1: Add udev rule for NVMe device permissions:
```bash
cat > /etc/udev/rules.d/99-nvme-smartctl.rules << EOF
SUBSYSTEM=="nvme", KERNEL=="nvme[0-9]*", GROUP="disk", MODE="0660"
EOF
udevadm control --reload-rules
udevadm trigger --subsystem-match=nvme
```

Part 2: Add systemd override with both capabilities:
```bash
mkdir -p /etc/systemd/system/beszel-agent.service.d
cat > /etc/systemd/system/beszel-agent.service.d/smart.conf << EOF
[Service]
AmbientCapabilities=CAP_SYS_RAWIO CAP_SYS_ADMIN
CapabilityBoundingSet=CAP_SYS_RAWIO CAP_SYS_ADMIN
ProtectSystem=full
EOF
systemctl daemon-reload && systemctl restart beszel-agent
```

**Key Insight**: NVMe SMART requires access to both:
- Block devices (`/dev/nvmeXn1`) - accessible via disk group
- Character devices (`/dev/nvmeX`) - needs udev rule for disk group access
- Admin ioctl capability - needs `CAP_SYS_ADMIN`

**Lesson**: NVMe vs SATA have different permission requirements. Always test with the actual user the service runs as (`sudo -u beszel smartctl -x /dev/nvme0n1`).

---

### 2. TrueNAS Read-Only Filesystem

**Symptom**: `mkdir: cannot create directory '/opt/beszel-agent': Read-only file system`
**Root Cause**: TrueNAS SCALE uses immutable root filesystem with `/opt` mounted read-only
**Solution**: Install to `/root` (which is on a writable ZFS dataset)

```bash
mkdir -p /root/beszel-agent
curl -sL "https://github.com/henrygd/beszel/releases/latest/download/beszel-agent_Linux_amd64.tar.gz" | tar -xz -C /root/beszel-agent
# Update service file to point to /root/beszel-agent/beszel-agent
```

**Also Required**: Change service `User=root` because:
- `ProtectHome=read-only` prevents the `beszel` user from accessing `/root`
- TrueNAS needs root access for SMART monitoring anyway

**Lesson**: Immutable/appliance-style systems may require non-standard installation paths. Check mount options before assuming standard paths work.

---

### 3. Talos Sysctl Configuration

**Symptom**: Coroot node agent CrashLoopBackOff with "read-only file system" error for `/proc/sys/net/netfilter/nf_conntrack_events`
**Root Cause**: Talos Linux is immutable - sysctls can't be changed at runtime, must be set in machineconfig
**Solution**: Patch Talos machineconfig via talosctl

```bash
talosctl patch machineconfig --mode no-reboot -n 10.20.0.40 -p @- << 'EOF'
- op: add
  path: /machine/sysctls/net.netfilter.nf_conntrack_events
  value: "1"
EOF
```

**Better Solution**: Add sysctl to Terraform `main.tf` for GitOps consistency:
```hcl
sysctls = {
  "net.netfilter.nf_conntrack_events" = "1"
}
```

**Lesson**: Talos changes should be in Terraform for reproducibility. Direct talosctl patches work but drift from IaC.

---

### 4. Terraform State Drift

**Symptom**: Terraform state referenced 10.20.0.109 (old IP) while live cluster was at 10.20.0.40
**Root Cause**: Multiple iterations of agentic cluster builds left stale state and config files
**Solution**:
1. Found correct talosconfig at `/root/.talos/config`
2. Updated `variables.tf` with correct IP
3. Backed up old state
4. Need to run `terraform refresh` to sync state

**Lesson**: After infrastructure iterations, always verify Terraform state matches live infrastructure before making changes. Clean up stale configs.

---

### 5. ArgoCD AppProject Destination Restrictions

**Symptom**: `coroot-agent-agentic` application stuck in "Unknown" state
**Error**: "destination server '10.20.0.40:6443' does not match allowed destinations in project 'monitoring'"
**Solution**: Add agentic cluster to monitoring AppProject destinations

```yaml
destinations:
  - server: https://kubernetes.default.svc
    namespace: '*'
  - server: https://10.20.0.40:6443  # Add this
    namespace: coroot-agent
```

**Lesson**: AppProject destination restrictions apply to all applications in the project. Plan cross-cluster deployments when defining projects.

---

### 6. PBS Without Guest Agent

**Symptom**: Could not use `qm guest exec` to install Beszel agent
**Root Cause**: qemu-guest-agent not installed inside PBS VM
**Solution**: Used sshpass with password authentication to add SSH key, then deployed via SSH

```bash
sshpass -p 'password' ssh root@10.10.0.150 'mkdir -p ~/.ssh && echo "ssh-key" >> ~/.ssh/authorized_keys'
```

**Better Solution**: Enable cloud-init on VM or pre-configure SSH keys in VM template

**Lesson**: For VMs without guest agent or SSH access, password-based initial access may be required. Store credentials in Infisical for future use.

---

## Credentials Management

### Stored in Infisical
| Path | Key | Purpose |
|------|-----|---------|
| `/monitoring/beszel` | `admin_email` | Beszel web UI login |
| `/monitoring/beszel` | `admin_password` | Beszel web UI login |
| `/monitoring/beszel` | `hub_public_key` | Agent authentication |

### API Access
- Beszel uses PocketBase under the hood
- Auth endpoint: `POST /api/collections/users/auth-with-password`
- Systems endpoint: `GET/POST /api/collections/systems/records`

---

## Configuration Artifacts

### Beszel S.M.A.R.T. Override
Location on each Proxmox host: `/etc/systemd/system/beszel-agent.service.d/smart.conf`

### TrueNAS Custom Service
Location: `/etc/systemd/system/beszel-agent.service`
- ExecStart points to `/root/beszel-agent/beszel-agent`
- Runs as User=root

### Talos Sysctl
Added to `/home/agentic_lab/infrastructure/terraform/talos-cluster/main.tf`:
```hcl
sysctls = {
  "net.netfilter.nf_conntrack_events" = "1"
}
```

---

## Monitoring Coverage Summary

| System Type | Count | Tool |
|-------------|-------|------|
| Proxmox hosts | 2 | Beszel |
| VMs (Plex, UniFi, PBS) | 3 | Beszel |
| LXC (IAC) | 1 | Beszel |
| TrueNAS (Media, HDD) | 2 | Beszel |
| Talos nodes | 5 | Coroot (eBPF) |
| MCP servers | 17 | Gatus |
| Kubernetes services | All | Coroot |

---

## Recommendations for Future

1. **Create VM Template** with qemu-guest-agent and SSH key pre-configured
2. **Document TrueNAS Workarounds** in Beszel setup guide
3. **Add Terraform Refresh** to infrastructure runbook
4. **Monitor SMART Warnings**: Ruapehu and TrueNAS HDD have disk warnings
5. **Check Carrick Temperature**: Running at 76°C - may need better cooling

---

## Files Modified

| Repository | File | Change |
|------------|------|--------|
| monit_homelab | `ansible/inventory/beszel-agents.yml` | Created |
| monit_homelab | `ansible/playbooks/03-beszel-agents.yml` | Created |
| monit_homelab | `kubernetes/bootstrap/monitoring-project.yaml` | Added agentic destination |
| agentic_lab | `infrastructure/terraform/talos-cluster/main.tf` | Added sysctl |
| agentic_lab | `infrastructure/terraform/talos-cluster/variables.tf` | Fixed node_ip |
