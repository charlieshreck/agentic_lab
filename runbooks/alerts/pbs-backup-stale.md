# PBSBackupStale

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | PBSBackupStale |
| **Severity** | Warning |
| **Source** | error-hunter sweep (PBS API) |
| **Clusters Affected** | Global (PBS on Pihanga, backups from Ruapehu, Pihanga, Hikurangi) |

## Description

This alert fires when a PBS (Proxmox Backup Server) backup group has not been updated within the expected threshold (typically 48 hours for daily schedules). All three Proxmox hosts (Ruapehu, Pihanga, Hikurangi) push backups to the central PBS server on Pihanga.

**PBS Server**: 10.10.0.151 (VM 101 on Pihanga)
**Datastore**: `pbs-datastore` at `/mnt/pbs-datastore` (NFS from TrueNAS-HDD 10.10.0.103:/mnt/Taupo/pbs)
**Schedule**: Daily at 02:00 on all three hosts

## Quick Diagnosis

### 1. Check PBS backup ages via error-hunter

error-hunter periodically checks all backup groups and reports age. Look for `pbs_backup_stale` findings in the Kernow Hub dashboard.

### 2. Check backup logs on the Proxmox host

```bash
# Ruapehu (VMs 109, 200, 400-403, 450, 451)
sshpass -p 'H4ckwh1z' ssh root@10.10.0.10 "cat /var/log/vzdump/qemu-<VMID>.log"

# Pihanga (VMs 101, 200)
sshpass -p 'H4ckwh1z' ssh root@10.10.0.20 "cat /var/log/vzdump/qemu-<VMID>.log"

# Hikurangi (LXCs 100, 101, 102)
sshpass -p 'H4ckwh1z' ssh root@10.10.0.178 "cat /var/log/vzdump/lxc-<VMID>.log"
```

### 3. Check PBS service status

```bash
sshpass -p 'H4ckwh1z' ssh root@10.10.0.151 "systemctl status proxmox-backup proxmox-backup-proxy"
```

## Common Causes

### 1. Stale NFS File Handles on PBS (Most Common)

**Symptoms:**
- ALL backups across ALL hosts fail simultaneously
- Error: `unable to open chunk store at "/mnt/pbs-datastore/.chunks" - No such file or directory (os error 2)`
- PBS datastore mount shows files exist when checked manually
- PBS services have been running for a long time after NFS disruption

**Verification:**
```bash
# Check vzdump log for the error
sshpass -p 'H4ckwh1z' ssh root@10.10.0.10 "tail -5 /var/log/vzdump/qemu-451.log"
# Look for: "unable to open chunk store"

# Verify NFS mount is healthy on PBS
sshpass -p 'H4ckwh1z' ssh root@10.10.0.151 "df -h /mnt/pbs-datastore; ls /mnt/pbs-datastore/.chunks/ | head -3"
```

**Resolution:**
```bash
# Restart PBS services to clear stale NFS handles
sshpass -p 'H4ckwh1z' ssh root@10.10.0.151 "systemctl restart proxmox-backup proxmox-backup-proxy"

# Wait 5 seconds, then trigger a test backup
sshpass -p 'H4ckwh1z' ssh root@10.10.0.10 "vzdump 200 --storage pbs-pihanga --mode snapshot --compress zstd"

# If test passes, trigger full backup on all hosts
sshpass -p 'H4ckwh1z' ssh root@10.10.0.10 "vzdump --all 1 --storage pbs-pihanga --mode snapshot --compress zstd --notes-template '{{guestname}}' &"
sshpass -p 'H4ckwh1z' ssh root@10.10.0.20 "vzdump --all 1 --storage pbs-pihanga --mode snapshot --compress zstd --notes-template '{{guestname}}' &"
sshpass -p 'H4ckwh1z' ssh root@10.10.0.178 "vzdump --all 1 --storage pbs-pihanga --mode snapshot --compress zstd --notes-template '{{guestname}}' &"
```

**Root Cause**: When the NFS mount to TrueNAS-HDD is disrupted (e.g., TrueNAS IP change, network blip, NFS service restart), the PBS process caches stale file descriptors. Even though the NFS mount recovers and files are visible, the running PBS process retains old handles that return ENOENT. Restarting the service forces it to re-open all file handles.

### 2. PBS Certificate Fingerprint Mismatch

**Symptoms:**
- Error: `certificate validation failed - Certificate fingerprint was not confirmed`
- PBS cert was regenerated (after PBS reinstall or cert rotation)

**Verification:**
```bash
# Get current PBS cert fingerprint
sshpass -p 'H4ckwh1z' ssh root@10.10.0.151 "openssl x509 -in /etc/proxmox-backup/proxy.pem -noout -fingerprint -sha256"

# Compare with storage config on Proxmox hosts
sshpass -p 'H4ckwh1z' ssh root@10.10.0.10 "grep -A 5 pbs-pihanga /etc/pve/storage.cfg"
```

**Resolution:**
Update the fingerprint in the Proxmox storage config (via UI: Datacenter > Storage > pbs-pihanga > Edit).

### 3. NFS Datastore Mount Failure on PBS

**Symptoms:**
- PBS datastore shows as unavailable
- NFS mount missing or stale

**Verification:**
```bash
sshpass -p 'H4ckwh1z' ssh root@10.10.0.151 "mount | grep pbs; df -h /mnt/pbs-datastore"
```

**Resolution:**
```bash
# Remount NFS
sshpass -p 'H4ckwh1z' ssh root@10.10.0.151 "umount /mnt/pbs-datastore; mount /mnt/pbs-datastore"
# Then restart PBS services
```

### 4. Decommissioned VMs/LXCs (Very Stale Backups)

**Symptoms:**
- Specific backup groups are 1000+ hours old
- The VM/LXC no longer exists on any Proxmox host

**Verification:**
```bash
# Check if the VMID exists on any host
sshpass -p 'H4ckwh1z' ssh root@10.10.0.10 "qm status <VMID> 2>&1; pct status <VMID> 2>&1"
sshpass -p 'H4ckwh1z' ssh root@10.10.0.20 "qm status <VMID> 2>&1; pct status <VMID> 2>&1"
sshpass -p 'H4ckwh1z' ssh root@10.10.0.178 "pct status <VMID> 2>&1"
```

**Resolution:**
These are harmless old backup snapshots. They can be cleaned up from PBS if storage space is needed:
- PBS UI > Datastore > pbs-datastore > Content > select old group > Remove
- Or leave them as archive — they don't affect active backups

**Known Decommissioned IDs**: vm/330, vm/331, vm/332, vm/133, vm/104, ct/105, ct/139, ct/103

## Proxmox Host to VM/LXC Mapping

| Host | VMIDs | LXC IDs |
|------|-------|---------|
| Ruapehu (10.10.0.10) | 109, 400-403, 450, 451 | 200 |
| Pihanga (10.10.0.20) | 101, 200 | — |
| Hikurangi (10.10.0.178) | — | 100, 101, 102 |

## Prevention

1. **Monitor PBS service uptime** — restart PBS services after any NFS disruption
2. **Set up NFS mount monitoring** — Gatus or custom check for `/mnt/pbs-datastore` availability
3. **Keep PBS services healthy** — consider a weekly service restart cron as preventive measure
4. **Clean up decommissioned backups** — periodically remove groups for non-existent VMs
5. **Ensure backup schedule is enabled** — check `pvesh get /cluster/backup` on each host

## Detection Methods

| Method | Status |
|--------|--------|
| error-hunter sweep (PBS API) | Active — checks backup group ages periodically |
| alert-forwarder CronJob | Active — forwards PBS alerts to LangGraph |
| Proxmox email notifications | Active — vzdump sends email on failure |

## Related Runbooks

- [PBS Operations](/home/agentic_lab/runbooks/infrastructure/pbs-operations.md)
- [Backup Overview](/home/agentic_lab/runbooks/infrastructure/backup-overview.md)
