# Beszel Agent Deployment

Runbook for deploying Beszel monitoring agents to homelab systems.

## Overview

Beszel provides lightweight system monitoring with metrics collection, S.M.A.R.T. disk monitoring, and a web dashboard. Agents report to the Beszel Hub running in the monit cluster.

## Architecture

| Component | Location | Purpose |
|-----------|----------|---------|
| Beszel Hub | monit cluster (10.30.0.20:30087) | Central dashboard and data collection |
| Beszel Agents | VMs, Proxmox hosts, NAS | Per-system metric collection |

**Not covered by Beszel:**
- Talos nodes (immutable OS - use Coroot eBPF instead)
- UnifiOS devices (proprietary appliance)

## Prerequisites

1. SSH access to target system
2. System registered in Beszel Hub UI
3. Hub public key: `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINUFgMUc1TX77CLR+okMLEwrDp/G3y8s32a3IC9MzIpd`

## Standard Deployment (Linux VMs/LXCs)

```bash
# Get installer and run with token (system ID)
curl -sL https://get.beszel.dev | KEY="<hub-public-key>" PORT=45876 bash

# Verify service
systemctl status beszel-agent
```

## Proxmox Hosts (with S.M.A.R.T. Support)

### Step 1: Deploy Agent
```bash
curl -sL https://get.beszel.dev | KEY="<hub-public-key>" PORT=45876 bash
```

### Step 2: Enable NVMe S.M.A.R.T. Access

NVMe drives require additional permissions beyond SATA drives.

**Add udev rule for NVMe character devices:**
```bash
cat > /etc/udev/rules.d/99-nvme-smartctl.rules << 'EOF'
SUBSYSTEM=="nvme", KERNEL=="nvme[0-9]*", GROUP="disk", MODE="0660"
EOF
udevadm control --reload-rules
udevadm trigger --subsystem-match=nvme
```

**Add systemd capabilities override:**
```bash
mkdir -p /etc/systemd/system/beszel-agent.service.d
cat > /etc/systemd/system/beszel-agent.service.d/smart.conf << 'EOF'
[Service]
AmbientCapabilities=CAP_SYS_RAWIO CAP_SYS_ADMIN
CapabilityBoundingSet=CAP_SYS_RAWIO CAP_SYS_ADMIN
ProtectSystem=full
EOF
systemctl daemon-reload && systemctl restart beszel-agent
```

**Verify S.M.A.R.T. access:**
```bash
# Test as beszel user
sudo -u beszel smartctl -x /dev/nvme0n1
```

## TrueNAS SCALE

TrueNAS has a read-only `/opt` filesystem. Install to `/root` instead.

### Step 1: Manual Installation
```bash
mkdir -p /root/beszel-agent
curl -sL "https://github.com/henrygd/beszel/releases/latest/download/beszel-agent_Linux_amd64.tar.gz" | tar -xz -C /root/beszel-agent
```

### Step 2: Create Custom Service
```bash
cat > /etc/systemd/system/beszel-agent.service << 'EOF'
[Unit]
Description=Beszel Agent
After=network.target

[Service]
Type=simple
User=root
ExecStart=/root/beszel-agent/beszel-agent
Environment="KEY=<hub-public-key>"
Environment="PORT=45876"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now beszel-agent
```

**Note:** Must run as root because:
- `/root` path inaccessible with `ProtectHome=read-only`
- S.M.A.R.T. monitoring requires elevated privileges

## Adding a New System

1. **Create system in Beszel Hub:**
   - Navigate to https://beszel.kernow.io
   - Login with credentials from Infisical `/monitoring/beszel/`
   - Add System → Enter hostname and IP
   - Copy the system token (system ID)

2. **Deploy agent using appropriate method above**

3. **Verify in Hub UI:**
   - System should show "up" status
   - Check S.M.A.R.T. page for disk health

## Beszel API Access

Beszel uses PocketBase. Useful for automation:

```bash
# Authenticate
TOKEN=$(curl -s -X POST "https://beszel.kernow.io/api/collections/users/auth-with-password" \
  -H "Content-Type: application/json" \
  -d '{"identity":"<email>","password":"<password>"}' | jq -r '.token')

# List systems
curl -s "https://beszel.kernow.io/api/collections/systems/records" \
  -H "Authorization: $TOKEN" | jq '.items[] | {name, host, status}'

# Create system
curl -s -X POST "https://beszel.kernow.io/api/collections/systems/records" \
  -H "Authorization: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"New System","host":"10.10.0.x","port":"45876"}'
```

## Troubleshooting

### S.M.A.R.T. Shows "UNKNOWN"

**For NVMe drives:**
1. Check udev rule exists: `ls -la /etc/udev/rules.d/99-nvme-smartctl.rules`
2. Check systemd override: `systemctl cat beszel-agent | grep CAP_SYS`
3. Test manually: `sudo -u beszel smartctl -x /dev/nvme0n1`

**For SATA drives:**
1. Check CAP_SYS_RAWIO capability in override
2. Verify disk group membership: `groups beszel`

### Agent Not Connecting

1. Check network connectivity: `curl http://10.30.0.20:30087`
2. Verify SSH key matches Hub public key
3. Check port 45876 not blocked

### High CPU on Agent

Beszel agents are lightweight (<1% CPU typical). If high:
1. Check disk I/O: S.M.A.R.T. queries may be slow on degraded disks
2. Review system logs: `journalctl -u beszel-agent -f`

## Ansible Playbook

For bulk deployment, use the playbook at:
`/home/monit_homelab/ansible/playbooks/03-beszel-agents.yml`

With inventory at:
`/home/monit_homelab/ansible/inventory/beszel-agents.yml`

## Version Drift Checks

Beszel agents typically auto-update when a new version is available. If version drift is reported:

```bash
# Check current version on agent
ssh root@<agent-ip> "/opt/beszel-agent/beszel-agent -v"

# Output: beszel-agent 0.18.4

# Check if newer version available
ssh root@<agent-ip> "cd /opt/beszel-agent && ./beszel-agent update"

# Output: "You already have the latest version 0.18.4."
```

If the agent reports an older version than hub:
1. Verify current version with `-v` flag
2. Run update command to trigger if needed
3. Check binary modification time: `ls -la /opt/beszel-agent/beszel-agent`
4. If modification date is recent (within last 7 days), update was already applied — finding is stale

**Example (Feb 2026):** Finding reported Plex-VM at 0.18.3 but agent was actually at 0.18.4 (binary updated Feb 20). Resolved as stale.

## Related

- Coroot agents for Talos nodes: See `/home/monit_homelab/kubernetes/platform/coroot-agent-*/`
- Gatus health checks: `/home/monit_homelab/kubernetes/platform/gatus/`
- Monitoring plan: `/root/.claude/plans/iridescent-painting-kahn.md`
