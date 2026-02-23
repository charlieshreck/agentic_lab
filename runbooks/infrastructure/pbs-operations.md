# PBS (Proxmox Backup Server) Operations Runbook

## Overview

PBS provides VM/LXC snapshot-level backups as a disaster recovery layer, complementing Backrest file-level backups.

### Current Setup (Pihanga)

**PBS Server**: 10.10.0.151 (VM 101 on Pihanga)
**Web UI**: https://10.10.0.151:8007
**Datastore**: `pbs-datastore` → `/mnt/pbs-datastore` (NFS to TrueNAS-HDD)
**NFS Path**: 10.10.0.103:/mnt/Taupo/pbs
**Storage**: 13.3 TB available

### Why Pihanga?

PBS runs on Pihanga (separate from Ruapehu) for proper DR:
- If Ruapehu fails, PBS and backups are still accessible
- Can restore Ruapehu VMs to new hardware
- Backups stored on TrueNAS-HDD (network storage)

## Backup Strategy

All three Proxmox hosts back up daily at 02:00 to PBS on Pihanga.

| Host | VMs/LXCs | Notes |
|------|----------|-------|
| Ruapehu (10.10.0.10) | vm/109, vm/400-403, vm/450, vm/451, ct/200 | Production workloads |
| Pihanga (10.10.0.20) | vm/101, vm/200 | PBS itself + monitoring |
| Hikurangi (10.10.0.178) | ct/100, ct/101, ct/102 | Synapse, Haute Banque, Tamar |

**Retention**: keep-daily=7, keep-monthly=3, keep-yearly=1

**Note**: Talos K8s VMs (400-403) can be rebuilt from IaC. PBS backups are optional DR layer.

## PBS Configuration

### Access PBS
```
URL: https://10.10.0.151:8007
User: root@pam
Password: H4ckwh1z
```

### Backup Schedule
All hosts have identical schedule configuration:
- Schedule: Daily 02:00
- Selection: All VMs/LXCs (`all=1`)
- Storage: `pbs-pihanga`
- Mode: Snapshot
- Compression: ZSTD

## Troubleshooting

### Stale NFS File Handles (Most Common Failure — Feb 2026)

When ALL backups fail with `unable to open chunk store at "/mnt/pbs-datastore/.chunks"`:

```bash
# 1. Restart PBS services (clears stale NFS handles)
sshpass -p 'H4ckwh1z' ssh root@10.10.0.151 "systemctl restart proxmox-backup proxmox-backup-proxy"

# 2. Test with a small backup
sshpass -p 'H4ckwh1z' ssh root@10.10.0.10 "vzdump 200 --storage pbs-pihanga --mode snapshot --compress zstd"

# 3. Trigger full backups on all hosts
sshpass -p 'H4ckwh1z' ssh root@10.10.0.10 "vzdump --all 1 --storage pbs-pihanga --mode snapshot --compress zstd &"
sshpass -p 'H4ckwh1z' ssh root@10.10.0.20 "vzdump --all 1 --storage pbs-pihanga --mode snapshot --compress zstd &"
sshpass -p 'H4ckwh1z' ssh root@10.10.0.178 "vzdump --all 1 --storage pbs-pihanga --mode snapshot --compress zstd &"
```

**Root cause**: NFS mount disruptions (e.g., TrueNAS IP change, network blip) leave the PBS process with cached stale file descriptors. Files are visible via `ls` but the running process gets ENOENT.

See also: `/home/agentic_lab/runbooks/alerts/pbs-backup-stale.md`

### Job Errors on vzdump
Common causes:
1. VM paused during backup — Check if QEMU guest agent is installed
2. Storage full — Check datastore space (`df -h /mnt/pbs-datastore`)
3. Lock conflicts — Check for stale locks
4. Stale NFS handles — See above

Check logs:
```bash
sshpass -p 'H4ckwh1z' ssh root@10.10.0.10 "cat /var/log/vzdump/qemu-<VMID>.log"
sshpass -p 'H4ckwh1z' ssh root@10.10.0.10 "journalctl -u pvedaemon | grep vzdump | tail -50"
```

### Backup Verification Failed
1. Check datastore consistency
2. Run manual verify via PBS UI or API

## Memory Pressure (Incident #163 — Feb 2026)

### Symptoms
- Pulse/KAO alert: `VM memory at >85% (value: ~98%)` for `pbs` on Pihanga
- Proxmox reports ~98% memory used for PBS VM (VMID 101)
- `free -h` inside VM shows MemAvailable ~1.3GB (actual pressure is low but risk is real during backups)

### Root Cause
PBS VM has 2GB RAM. During backup windows:
- `proxmox-backup-proxy` peaks at ~1GB RSS
- `systemd-journald` can balloon to 240MB+ if error-log flooding occurs
  (e.g., stale NFS causing "unable to open chunk store" errors every ~100s)
- OS overhead + buffer/cache fills remaining 2GB
- Proxmox reports 98%+ because it counts all allocated guest pages

**Risk**: OOM during 02:00 backup window when multiple VMs are backed up concurrently.

### Fix Applied (Incident #163)
1. **Terraform** (`monit_homelab/terraform/talos-single-node/pbs.tf`): Increased RAM 2GB → 4GB
   - Requires `terraform apply` in monit_homelab terraform (PBS VM will restart)
2. **journald** (`/etc/systemd/journald.conf` on PBS): Capped at 128MB runtime / 256MB system
   ```
   RuntimeMaxUse=128M
   SystemMaxUse=256M
   RuntimeMaxFileSize=32M
   SystemMaxFileSize=64M
   ```
   Applied via: `systemctl restart systemd-journald`

### Procedure When Alert Fires

```bash
# 1. SSH to PBS and check real memory pressure
sshpass -p 'H4ckwh1z' ssh root@10.10.0.151 "free -h"
# MemAvailable > 500MB = safe, just Proxmox reporting bloat

# 2. Check for log flooding
sshpass -p 'H4ckwh1z' ssh root@10.10.0.151 "journalctl -u proxmox-backup-proxy --since '30 min ago' --no-pager | grep -c 'unable to open'"

# 3. If journald is bloated from log flooding, restart it
sshpass -p 'H4ckwh1z' ssh root@10.10.0.151 "systemctl restart systemd-journald"

# 4. If actual memory pressure (MemAvailable < 200MB), check for a larger process
sshpass -p 'H4ckwh1z' ssh root@10.10.0.151 "ps aux --sort=rss | tail -10"

# 5. If NFS error flooding, see stale-NFS section above — restart PBS services
```

### Terraform Apply (after RAM increase commit)
```bash
cd /home/monit_homelab/terraform/talos-single-node
terraform init   # if needed
terraform plan -target=proxmox_virtual_environment_vm.pbs  # review
terraform apply  # Updates Proxmox VM config to 4096MB
```

**IMPORTANT**: Terraform only updates the VM config in Proxmox. Because PBS has `balloon = 0`,
the running guest will NOT see the new RAM until the VM is rebooted. After `terraform apply`:

```bash
# Check if VM is still running with old RAM
# (Proxmox API maxmem will show old value until reboot)

# Verify no active backups before rebooting
curl -sk -X POST "https://10.10.0.151:8007/api2/json/access/ticket" \
  -d "username=root@pam&password=H4ckwh1z" | python3 -c "
import sys, json, urllib.request, ssl
r = json.load(sys.stdin)
ticket = r['data']['ticket']
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
req = urllib.request.Request('https://10.10.0.151:8007/api2/json/nodes/localhost/tasks?running=1&limit=10',
  headers={'Cookie': f'PBSAuthCookie={ticket}'})
data = json.loads(urllib.request.urlopen(req, context=ctx).read())
print('Active tasks:', data.get('data', []))
"

# Reboot PBS to pick up new RAM allocation (use Proxmox MCP tool)
# mcp__infrastructure__proxmox_reboot_vm(host="pihanga", node="Pihanga", vmid=101)

# Verify after reboot (30s to boot)
sshpass -p 'H4ckwh1z' ssh root@10.10.0.151 "free -h"
# Should show Total: ~3.8Gi
```

**Note**: Plan PBS restart during a maintenance window (avoid 02:00 backup window).

## Monitoring

### PBS Health
- Datastore → Status shows health
- Check Grafana dashboard (if configured)

### Integration with Keep
PBS can send notifications to Keep via webhook for alert aggregation.

## Recovery Procedures

### Restore VM from PBS
1. Proxmox UI → Datacenter → pbs-ruapehu
2. Select backup snapshot
3. Right-click → Restore
4. Choose target node and storage

### Restore Files from PBS (without full VM restore)
```bash
# Mount backup for file-level recovery
proxmox-backup-client mount <datastore> <backup-id> /mnt/restore --repository <user>@<server>
```

## Related Runbooks
- `/home/agentic_lab/runbooks/infrastructure/backup-overview.md`
- `/home/agentic_lab/runbooks/infrastructure/backrest-operations.md`
- `/home/agentic_lab/runbooks/infrastructure/velero-operations.md`
