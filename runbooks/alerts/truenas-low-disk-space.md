# TrueNAS Low Disk Space Alert

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | TrueNAS Low Disk Space |
| **Source** | infrastructure-mcp / alerting-pipeline |
| **Severity** | WARNING |
| **Threshold** | 85% pool capacity |
| **Current Status** | Taranaki pool at 93.2% (Feb 23, 2026) |

---

## Impact Assessment

At **93.2% capacity**, the Taranaki pool on TrueNAS-Media is critically full:

- **ZFS resilience**: Recommended to keep pools <80% full (ZFS performance degrades >85%)
- **Write performance**: Slowing as free space decreases
- **Snapshot space**: Limited room for new snapshots
- **Emergency buffer**: Minimal headroom for unexpected writes
- **Backup operations**: May fail if new writes needed during backup

**Action required**: Reduce capacity to <85% (preferably <80%) within 1-2 days.

---

## Root Cause Investigation

### Step 1: Identify What's Consuming Space

Access TrueNAS-Media web UI (may need to SSH or use MCP if web interface is restricted):

```bash
# Option A: Via TrueNAS Web UI (if accessible)
# Navigate to: Storage → Pools → Taranaki → Actions → Status
# Look at "Used" capacity and dataset breakdown

# Option B: Via SSH to TrueNAS-Media (if root access available)
ssh -l root 10.20.0.100
# Or via Infisical SSH (requires FreeBSD tcsh shell experience)

# List ZFS datasets and usage
zfs list -r tank/taranaki

# List largest directories
du -sh /mnt/Taranaki/* | sort -hr | head -10
```

### Step 2: Check for Common Space Wasters

**A. Old Snapshots** (if applicable)
```bash
zfs list -r -t snapshot tank/taranaki | grep -v '^NAME'
# Count snapshots and identify old ones
```

**B. Pending Backups or Temp Files**
```bash
ls -lh /mnt/Taranaki/.snapshot/ 2>/dev/null
ls -lh /tmp/ 2>/dev/null | tail -20
```

**C. Dataset-Level Quota Check**
```bash
zfs get quota,used,available tank/taranaki
zfs get quota,used,available -r tank/taranaki
```

**D. Checksums & Dedup (ZFS-level)**
```bash
zpool list taranaki
# Check available vs used
```

### Step 3: Query TrueNAS via API (if web interface unavailable)

```bash
# Get API key from Infisical
export TRUENAS_KEY=$(infisical secrets get API_KEY --path=/infrastructure/truenas-media --plain)
export TRUENAS_URL="https://truenas.kernow.io"

# Query pool status (returns JSON with capacity info)
curl -s -H "Authorization: Bearer $TRUENAS_KEY" \
  "$TRUENAS_URL/api/v2.0/pool/" | jq '.[] | {name, guid, status, scan, topology}'

# Get dataset list with usage
curl -s -H "Authorization: Bearer $TRUENAS_KEY" \
  "$TRUENAS_URL/api/v2.0/pool/dataset/" | jq '.[] | {name, used, available, compression}'
```

---

## Remediation Strategies

### Strategy 1: Remove Old Data (Safest)

**For Downloaded Content** (if applicable):
- Identify and remove incomplete/old downloads
- Check `/mnt/Taranaki/downloads/` or similar
- Archive rarely-accessed media to external storage

**For Temporary Files**:
```bash
find /mnt/Taranaki -type f -mtime +90 -size +1G  # Files not modified in 90+ days, >1GB
# Review results before deletion
```

**For Duplicate/Orphaned Files**:
```bash
# Find and remove symlink targets that are no longer referenced
find /mnt/Taranaki -type l -! -exec test -e {} \; -delete
```

### Strategy 2: Snapshot Cleanup

**List all snapshots**:
```bash
zfs list -r -t snapshot tank/taranaki | head -30
```

**Remove old snapshots** (CAUTION - destructive):
```bash
# Example: Remove snapshots older than 30 days
zfs list -r -t snapshot tank/taranaki -H -o name | while read snap; do
  age=$(date -d "$(zfs get -H -o value creation "$snap")" +%s)
  now=$(date +%s)
  days=$(( ($now - $age) / 86400 ))
  if [ $days -gt 30 ]; then
    echo "Old snapshot ($days days): $snap"
    # zfs destroy -r "$snap"  # UNCOMMENT TO EXECUTE
  fi
done
```

**Auto-cleanup via TrueNAS UI**:
1. Navigate to **Storage** → **Snapshots**
2. Review retention policy
3. Consider enabling automatic snapshot deletion (if configured)

### Strategy 3: Expand Storage (Medium-term)

If the pool is legitimate full:

1. **Add new VDEV to existing pool** (online expansion):
   ```bash
   # Via TrueNAS UI: Storage → Pools → Taranaki → Add VDEV
   # Or via CLI: zpool add tank/taranaki <new-vdev>
   ```

2. **Increase VM disk in Proxmox**:
   - VM VMID 109 (TrueNAS-Media) may have limited disk allocation
   - Expand via Proxmox → VMID 109 → Hardware → scsi disk

3. **Move high-volume datasets** to different storage:
   - Identify largest datasets
   - Create new pool if additional storage available
   - rsync data to new location

### Strategy 4: Compression & Dedup (Low-yield, Higher Risk)

**Enable compression** (future data only):
```bash
zfs set compression=zstd tank/taranaki
```

**Recompress existing data** (slow, resource-intensive):
```bash
zfs send -c tank/taranaki@snapshot | zfs recv tank/taranaki-compressed
```

⚠️ **Warning**: These don't help immediately and can cause performance issues.

---

## Incident #162 Specific Actions

### Current Status (Feb 23, 2026)
- **Pool**: Taranaki (TrueNAS-Media, 10.20.0.100)
- **Capacity**: 93.2% (warning threshold: 85%)
- **Node**: Ruapehu (VM VMID 109)
- **Access**: Limited (API/SSH restricted from this LXC)

### Immediate Steps

1. **Identify space consumers** — Need direct TrueNAS access or Proxmox console
   - SSH to TrueNAS-Media if keys available
   - Check `/mnt/Taranaki` for obvious large files
   - Query ZFS snapshot count

2. **Target cleanup goal**: Reduce to 80% (gain ~3-5% capacity)
   - Safe threshold for ZFS operations
   - Allows breathing room for normal operations

3. **Preferred cleanup strategy** (in order):
   - [ ] Remove stale snapshots (if >100 exist)
   - [ ] Delete old/incomplete downloads (if /downloads exists)
   - [ ] Clean temp files older than 90 days
   - [ ] Archive least-frequently-accessed media
   - [ ] If none viable: Expand pool via Proxmox or add new VDEV

### Escalation Path

If **unable to reduce below 85%**:
1. Check if Backrest weekly backup (Sun 7AM) needs storage space
2. Temporarily disable Backrest jobs if space needed
3. Consider expanding VM disk (Proxmox → VMID 109 → Hardware)
4. Review whether Taranaki is appropriate size for current workload

---

## Prevention & Monitoring

### Future Alert Optimization

The alerting pipeline currently triggers at **85%**. Consider adjusting for TrueNAS-Media:

```yaml
# In alerting-pipeline.yaml (infrastructure-mcp checks)
AlertRule(
    name="TrueNAS Low Disk Space",
    source="infrastructure",
    check_type="threshold",
    threshold=85,  # Current
    # threshold=80,  # More aggressive (recommended for TrueNAS)
    severity="warning",
    description_template="Pool '{pool_name}' is at {usage_percent}% capacity",
    fix_template="Run 'zfs list -r {pool_name}' to identify large datasets; remove old snapshots or data"
)
```

### Recommended Thresholds by Pool

| Threshold | Trigger At | Recommended Action |
|-----------|-----------|-------------------|
| 80% | Production pools (active writes) | Clean up immediately |
| 85% | Archive/backup pools | Review within 48h |
| 90%+ | Critical | Production impact likely |

### Automated Cleanup Options (Future)

1. **Snapshot retention policy** (TrueNAS SCALE UI):
   - Automatic pruning of snapshots >30 days
   - Per-dataset configuration

2. **CronJob for cleanup** (K8s-based):
   ```yaml
   # Example: Daily cleanup of files older than 180 days
   apiVersion: batch/v1
   kind: CronJob
   metadata:
     name: truenas-media-cleanup
     namespace: default
   spec:
     schedule: "0 2 * * *"  # 2 AM daily
     jobTemplate:
       spec:
         template:
           spec:
             containers:
             - name: cleanup
               image: alpine:latest
               command:
               - /bin/sh
               - -c
               - |
                 find /mnt/Taranaki -type f -mtime +180 -delete
                 # or similar cleanup logic
               volumeMounts:
               - name: taranaki
                 mountPath: /mnt/Taranaki
             volumes:
             - name: taranaki
               nfs:
                 server: 10.20.0.100  # TrueNAS-Media
                 path: /mnt/Taranaki
   ```

3. **Quota enforcement** (ZFS):
   ```bash
   # Prevent dataset from exceeding threshold
   zfs set quota=500G tank/taranaki/downloads
   ```

---

## Related Runbooks

- `/home/agentic_lab/runbooks/infrastructure/backup-overview.md` — Backup infrastructure (Backrest schedules)
- `/home/agentic_lab/runbooks/infrastructure/backrest-operations.md` — VM backup operations
- `/home/agentic_lab/runbooks/infrastructure/truenas-app-updates.md` — TrueNAS maintenance
- `/home/agentic_lab/runbooks/alerts/pbs-backup-stale.md` — Related backup storage alert

---

## Infisical References

| Path | Keys | Purpose |
|------|------|---------|
| `/infrastructure/truenas-media` | HOST, API_KEY | TrueNAS-Media API access |

---

## Commands Quick Reference

```bash
# Check pool status via ZFS CLI (from TrueNAS SSH)
zpool status -v tank/taranaki

# List datasets with usage
zfs list -r tank/taranaki -o name,used,available,compression

# Find large files (>5GB)
find /mnt/Taranaki -type f -size +5G

# Calculate total usage by directory
du -sh /mnt/Taranaki/* | sort -hr

# Check snapshot count
zfs list -r -t snapshot tank/taranaki | wc -l

# Remove single snapshot
zfs destroy tank/taranaki@snapshot_name

# Set compression on dataset (future data)
zfs set compression=lz4 tank/taranaki
```

---

## Troubleshooting

### "Cannot access TrueNAS-Media from this LXC"

**Symptom**: SSH/API calls to 10.20.0.100 timeout or connection refused

**Cause**: Network firewall restrictions (ports 22/80/443 closed from Synapse LXC)

**Workaround**:
1. SSH to Proxmox host (10.10.0.10) first
2. From Proxmox, SSH into TrueNAS-Media VM console
3. Or: Use TrueNAS Web UI via DNS (`truenas.kernow.io`) if web port is open
4. Or: Request network rule change to allow Synapse → TrueNAS-Media

### "ZFS operations slow or hanging"

**Cause**: Pool at 93% may have I/O contention

**Action**:
1. Immediately reduce usage to <85%
2. Avoid concurrent snapshot/backup operations
3. Check for zombie processes: `ps aux | grep zfs`

### "Snapshots keep reappearing after deletion"

**Cause**: Backrest or other backup tool is auto-creating snapshots

**Solution**:
1. Check Backrest schedule: `grep "truenas-media" /path/to/backrest/config`
2. Pause/modify Backrest job if needed
3. Update snapshot retention in TrueNAS UI
