# UniFi OS Server Deployment

## Overview

UniFi OS Server runs on a dedicated Debian 13 VM using Podman containers. This provides the full UniFi OS experience (not just Network Application) with IaC management via Terraform and Ansible.

## Architecture

| Component | Value |
|-----------|-------|
| **VM ID** | 451 |
| **Hostname** | unifi |
| **IP Address** | 10.10.0.51 |
| **OS** | Debian 13 (Trixie) |
| **Container Runtime** | Podman 5.x |
| **UniFi OS Version** | 4.2.23 |
| **Proxmox Host** | Ruapehu (10.10.0.10) |

### Resource Allocation

- **CPU**: 2 cores
- **RAM**: 3GB (maxmem 3,221,225,472)
- **Disk**: 50GB (scsi0 on local-lvm)
- **Network**: Single NIC on vmbr0 (10.10.0.0/24)

### Memory Budget (steady state ~75% of 3GB)

| Process | RSS | Cap |
|---------|-----|-----|
| Java (UniFi Network) | ~570 MB | `-Xmx512M` heap + JVM overhead |
| Node.js (unifi-core) | ~210 MB | `--max-old-space-size=300` |
| MongoDB (system) | ~116 MB | wiredTiger default |
| MongoDB (UniFi) | ~98 MB | `cache_size=256M` |
| ulp-go | ~145 MB | — |
| PostgreSQL + others | ~200 MB | — |

### Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 11443 | TCP | Web UI (HTTPS) |
| 8080 | TCP | Device inform URL |
| 8443 | TCP | Controller API |
| 8880 | TCP | HTTP portal redirect |
| 8881 | TCP | HTTPS portal redirect |
| 3478 | UDP | STUN |
| 6789 | TCP | Speed test |
| 5514 | UDP | Remote syslog |
| 10001 | UDP | Device discovery |

## Access

### Internal (via Caddy)

```
https://unifi.kernow.io
```

DNS rewrite in AdGuard points to Caddy (10.10.0.1), which proxies to the VM.

### Direct Access

```
https://10.10.0.51:11443
```

### SSH Access

```bash
ssh root@10.10.0.51
# Password in Infisical: /infrastructure/unifi-vm/root_password
```

## Infrastructure as Code

### Terraform

Location: `/home/prod_homelab/infrastructure/terraform/`

**Module**: `modules/unifi-vm/`
- `main.tf` - VM resource definition
- `variables.tf` - Input variables
- `outputs.tf` - Output values
- `cloud-init.yaml.tftpl` - Cloud-init template

**Standalone Config**: `unifi-standalone/`
- Used due to main terraform state being unavailable
- Contains complete VM provisioning config

### Ansible

Location: `/home/prod_homelab/infrastructure/ansible/`

**Role**: `roles/unifi-os/`
- `defaults/main.yml` - Default variables (version, URLs)
- `tasks/main.yml` - Installation tasks
- `handlers/main.yml` - Service handlers

**Playbook**: `playbooks/unifi-os.yml`
**Inventory**: `inventory/unifi.yml`

### Run Ansible Playbook

```bash
cd /home/prod_homelab/infrastructure/ansible
ANSIBLE_HOST_KEY_CHECKING=False ansible-playbook -i inventory/unifi.yml playbooks/unifi-os.yml
```

## UniFi OS Management

### Service Commands

```bash
# SSH to VM first
ssh root@10.10.0.51

# Check status
uosserver status

# Start/Stop/Restart
uosserver start
uosserver stop
uosserver restart

# View logs
uosserver logs

# Help
uosserver help
```

### Container Management

UniFi OS runs as a Podman container:

```bash
# List containers
podman ps

# View container logs
podman logs uosserver

# Restart container
podman restart uosserver
```

### Data Locations

| Volume | Purpose |
|--------|---------|
| `uosserver_persistent` | Persistent configuration |
| `uosserver_data` | Application data |
| `uosserver_var_log` | Logs |
| `uosserver_var_lib_unifi` | UniFi Network data |
| `uosserver_var_lib_mongodb` | MongoDB database |

## Device Adoption

### Inform URL

Set devices to inform to:
```
http://10.10.0.51:8080/inform
```

### Adoption Methods

1. **Layer 2 Discovery**: Devices on same VLAN auto-discover
2. **DNS Override**: Set `unifi` DNS to resolve to 10.10.0.51
3. **DHCP Option 43**: Configure in OPNsense for automatic adoption
4. **SSH Set-Inform**: For devices on different networks:
   ```bash
   ssh ubnt@<device-ip>
   set-inform http://10.10.0.51:8080/inform
   ```

## Backup & Restore

### Automatic Backups

UniFi OS creates automatic backups stored in the container volumes.

### Manual Backup

```bash
# SSH to VM
ssh root@10.10.0.51

# Backup via uosserver (if available)
uosserver backup

# Or backup Podman volumes
podman volume export uosserver_data > /tmp/unifi-data-backup.tar
podman volume export uosserver_var_lib_unifi > /tmp/unifi-network-backup.tar
```

### Restore

```bash
# Stop container
uosserver stop

# Restore volumes
podman volume import uosserver_data /tmp/unifi-data-backup.tar
podman volume import uosserver_var_lib_unifi /tmp/unifi-network-backup.tar

# Start container
uosserver start
```

## Upgrading UniFi OS

### Check Current Version

```bash
ssh root@10.10.0.51 "uosserver status"
```

### Upgrade Process

1. **Get new installer URL** from https://ui.com/download/software/unifi-os-server
   - Right-click download button, copy link
   - URLs have unique UUIDs per version

2. **Update Ansible defaults**:
   ```yaml
   # /home/prod_homelab/infrastructure/ansible/roles/unifi-os/defaults/main.yml
   unifi_version: "X.Y.Z"
   unifi_installer_url: "https://fw-download.ubnt.com/data/unifi-os-server/..."
   ```

3. **Run upgrade on VM**:
   ```bash
   ssh root@10.10.0.51
   wget -O /tmp/unifi-upgrade <new-url>
   chmod +x /tmp/unifi-upgrade
   echo 'y' | /tmp/unifi-upgrade install
   ```

4. **Verify**:
   ```bash
   uosserver status
   ```

## Troubleshooting

### High Memory / JVM Heap Cap Lost

**Symptom**: VM memory exceeds 85%, typically climbing to 95%+.

**Root cause**: UniFi OS runs Java (UniFi Network) inside a Podman container. The `unifi.service` systemd unit sets `-Xmx512M` via `UNIFI_JVM_OPTS`, but `/etc/default/unifi` (loaded via `EnvironmentFile`) can override this. UniFi OS updates may recreate `/etc/default/unifi` without the `-Xmx512M` cap, causing JVM heap to grow to the ergonomic default (~730 MB+).

**Fix architecture**:
1. **Persistent env-overrides file** at `/var/lib/unifi/env-overrides` (on `uosserver_var_lib_unifi` volume — survives container recreations):
   ```
   UNIFI_JVM_OPTS="-Dunifi-os.server=true -Dorg.xerial.snappy.tempdir=/usr/lib/unifi/run -Xmx512M -XX:+UseParallelGC"
   ```
2. **EnvironmentFile directive** in `unifi.service` (overlay layer — may be lost on UniFi OS updates):
   ```
   EnvironmentFile=-/etc/default/unifi
   EnvironmentFile=-/var/lib/unifi/env-overrides   # <-- added, loads AFTER /etc/default
   ```

**Investigation steps** (via Ruapehu host):
```bash
# Check current JVM heap cap
sshpass -p 'H4ckwh1z' ssh root@10.10.0.10 \
  "qm guest exec 451 -- bash -c 'ps aux | grep ace.jar | grep -o Xmx[^ ]*'"

# Check if /etc/default/unifi exists and overrides JVM opts
sshpass -p 'H4ckwh1z' ssh root@10.10.0.10 \
  "qm guest exec 451 -- bash -c 'cat /etc/default/unifi 2>/dev/null || echo FILE_NOT_FOUND'"

# Check env-overrides on persistent volume
sshpass -p 'H4ckwh1z' ssh root@10.10.0.10 \
  "qm guest exec 451 -- cat /home/uosserver/.local/share/containers/storage/volumes/uosserver_var_lib_unifi/_data/env-overrides"

# Check if active overlay has the EnvironmentFile line
sshpass -p 'H4ckwh1z' ssh root@10.10.0.10 \
  "qm guest exec 451 -- bash -c 'grep EnvironmentFile /home/uosserver/.local/share/containers/storage/overlay/*/diff/lib/systemd/system/unifi.service 2>/dev/null'"
```

**Repair steps** (if EnvironmentFile line is missing after update):
```bash
# Find the active overlay layer (the one WITHOUT env-overrides line)
# Then add it after the /etc/default/unifi line:
sshpass -p 'H4ckwh1z' ssh root@10.10.0.10 \
  "qm guest exec 451 -- bash -c 'sed -i \"/EnvironmentFile=-\\/etc\\/default\\/unifi/a EnvironmentFile=-/var/lib/unifi/env-overrides\" /home/uosserver/.local/share/containers/storage/overlay/<LAYER>/diff/lib/systemd/system/unifi.service'"
```

**Post-UniFi-OS-update checklist**: Re-verify the EnvironmentFile line is present in the active overlay. If not, re-apply using the repair steps above.

### VM Not Accessible

1. Check VM status in Proxmox:
   ```bash
   ssh root@10.10.0.10 "qm status 451"
   ```

2. Check via QEMU guest agent:
   ```bash
   ssh root@10.10.0.10 "qm guest exec 451 -- ip addr"
   ```

3. Start VM if stopped:
   ```bash
   ssh root@10.10.0.10 "qm start 451"
   ```

### UniFi OS Not Starting

1. Check Podman container:
   ```bash
   ssh root@10.10.0.51 "podman ps -a"
   ```

2. Check container logs:
   ```bash
   ssh root@10.10.0.51 "podman logs uosserver --tail 50"
   ```

3. Check system resources:
   ```bash
   ssh root@10.10.0.51 "free -h && df -h"
   ```

4. Restart service:
   ```bash
   ssh root@10.10.0.51 "uosserver restart"
   ```

### Web UI Not Loading

1. Verify port is listening:
   ```bash
   ssh root@10.10.0.51 "ss -tlnp | grep 11443"
   ```

2. Test local access:
   ```bash
   ssh root@10.10.0.51 "curl -sk https://localhost:11443/"
   ```

3. Check Caddy proxy:
   ```bash
   curl -sk https://unifi.kernow.io/
   ```

### Devices Not Adopting

1. Verify inform URL is reachable:
   ```bash
   curl -s http://10.10.0.51:8080/inform
   ```

2. Check device can reach controller:
   ```bash
   # From device network
   nc -zv 10.10.0.51 8080
   ```

3. Check firewall rules on OPNsense

4. Force re-adoption via SSH to device

## DNS & Proxy Configuration

### AdGuard DNS Rewrite

```bash
# Add/verify rewrite
ADGUARD_USER=$(/root/.config/infisical/secrets.sh get /infrastructure/adguard username)
ADGUARD_PASS=$(/root/.config/infisical/secrets.sh get /infrastructure/adguard password)

curl -s -u "${ADGUARD_USER}:${ADGUARD_PASS}" \
  "http://10.10.0.1:3000/control/rewrite/list" | jq '.[] | select(.domain == "unifi.kernow.io")'
```

### Caddy Reverse Proxy

The Caddy entry proxies `unifi.kernow.io` to `https://10.10.0.51:11443` with:
- TLS skip verify (self-signed cert)
- **header_up Host {upstream_hostport}** - Critical for UniFi OS

**Important**: UniFi OS requires the `header_up Host` directive to pass the upstream IP as the Host header. Without this, UniFi OS redirects to its internal hostname (e.g., `https://unifi`) causing a redirect loop.

To verify/update via OPNsense API:
```bash
OPNSENSE_KEY=$(/root/.config/infisical/secrets.sh get /infrastructure/opnsense key)
OPNSENSE_SECRET=$(/root/.config/infisical/secrets.sh get /infrastructure/opnsense secret)

# List handles
curl -sk --user "${OPNSENSE_KEY}:${OPNSENSE_SECRET}" \
  'https://10.10.0.1:8443/api/caddy/ReverseProxy/searchHandle' \
  -X POST | jq '.rows[] | select(.ToDomain == "10.10.0.51")'

# List headers (should show Host header_up for UniFi)
curl -sk --user "${OPNSENSE_KEY}:${OPNSENSE_SECRET}" \
  'https://10.10.0.1:8443/api/caddy/ReverseProxy/searchHeader' \
  -X POST | jq '.rows[]'
```

## MCP Integration

The UniFi MCP server (`unifi-mcp`) connects to the UniFi OS API:

- **Endpoint**: https://10.10.0.51:11443
- **Credentials**: Stored in Infisical at `/agentic-platform/unifi`

After setup, generate an API key in UniFi OS and update Infisical.

## Related Documentation

- [AdGuard DNS Rewrite](./adguard-rewrite.md)
- [Caddy Proxy](./caddy-proxy.md)
- [New App Prod Pattern](./new-app-prod.md)

## History

| Date | Change |
|------|--------|
| 2026-01-12 | Initial deployment - migrated from unmanaged VM at 10.10.0.154 |
| 2026-02-25 | Added JVM heap cap fix (env-overrides + EnvironmentFile in overlay) after incident #265 |
