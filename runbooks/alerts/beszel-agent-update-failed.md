# BeszelAgentUpdateFailed

## Alert Details

| Field | Value |
|-------|-------|
| **Alert Name** | BeszelAgentUpdateFailed |
| **Severity** | Warning |
| **Source** | error-hunter sweep / Gatus (agent connectivity) |
| **Clusters Affected** | Global (Beszel hub on monit cluster, agents on bare-metal/VMs) |

## Description

This alert fires when a Beszel agent fails to auto-update to match the hub version, typically due to SSH authentication failures. The Beszel hub (running in the monit cluster) manages agents via SSH and attempts auto-updates when version mismatches are detected.

Beszel hub: monit cluster (monitoring namespace), port 8090.
Agents: Run on bare-metal/VMs (TrueNAS-HDD, UniFi-OS, Plex VM, etc.) on port 45876.

## Quick Diagnosis

### 1. Check Beszel hub UI

Navigate to `https://beszel.kernow.io` and check the Systems page for version mismatches or offline agents.

### 2. Verify agent connectivity

```
# Via Gatus (preferred)
mcp__observability__gatus_get_endpoint_status()
# Look for "Beszel Agent (TrueNAS-HDD)" status

# Direct TCP check
nc -z 10.10.0.103 45876
```

### 3. Check agent version

```bash
# SSH to the host and check agent version
ssh root@10.10.0.103 "beszel-agent --version"
```

## Common Causes

### 1. SSH Authentication Failure

**Symptoms:**
- error-hunter reports "SSH auth failed for root@<host>"
- Hub shows version mismatch in UI
- Agent is running and healthy but can't be updated

**Verification:**
```bash
# Test SSH from the Beszel hub pod (monit cluster)
# Or test from a host with the SSH key
ssh root@10.10.0.103 "echo ok"
```

**Resolution:**
1. Check if the SSH key is still valid:
   - Beszel stores SSH keys in its PocketBase data (`/beszel_data/`)
   - The hub needs passwordless SSH access to agents for auto-update
2. Re-authorize the agent:
   - In Beszel UI, go to Settings > Systems
   - Remove and re-add the affected agent
   - Copy the new SSH key to the target host
3. Manual agent update as fallback:
   ```bash
   ssh root@10.10.0.103 "beszel-agent update"
   ```

### 2. Agent Process Not Running

**Symptoms:**
- Gatus TCP check fails (agent port 45876 unreachable)
- Beszel hub shows agent as offline

**Verification:**
```bash
ssh root@10.10.0.103 "ps aux | grep beszel"
# Or check systemd service
ssh root@10.10.0.103 "systemctl status beszel-agent"
```

**Resolution:**
```bash
ssh root@10.10.0.103 "systemctl restart beszel-agent"
```

### 3. Network Connectivity Issue

**Symptoms:**
- Agent TCP port unreachable from monit cluster
- Multiple agents affected simultaneously

**Verification:**
```
# Check from monit cluster
mcp__observability__gatus_get_failing_endpoints()
```

**Resolution:**
- Check firewall rules on OPNsense (10.10.0.1)
- Verify network path: monit (10.10.0.30) → agent host
- Check if the agent host is on a different VLAN with blocked ports

### 4. TrueNAS-HDD Specific: Agent Binary Location

**Symptoms:**
- Agent installed but update command not found
- TrueNAS has non-standard paths

**Verification:**
```bash
ssh root@10.10.0.103 "which beszel-agent"
ssh root@10.10.0.103 "ls /usr/local/bin/beszel-agent"
```

**Resolution:**
```bash
# Reinstall agent on TrueNAS-HDD
ssh root@10.10.0.103 "curl -sL https://raw.githubusercontent.com/henrygd/beszel/main/supplemental/scripts/install-agent.sh -o /tmp/install-agent.sh && bash /tmp/install-agent.sh"
```

## Resolution Steps

### Step 1: Identify the affected agent

Check error-hunter findings or Beszel UI for version mismatch details.

### Step 2: Attempt manual update

```bash
ssh root@<agent-host> "beszel-agent update"
```

### Step 3: If SSH auth fails, fix the keys

```bash
# Get the hub's public key from Beszel UI (Settings > Systems > agent entry)
# Add it to the agent host's authorized_keys
ssh root@<agent-host> "echo '<public-key>' >> ~/.ssh/authorized_keys"
```

### Step 4: Verify the update

Check Beszel UI to confirm the agent version now matches the hub version.

### Step 5: Verify Gatus monitoring

```
mcp__observability__gatus_get_endpoint_status()
# Confirm "Beszel Agent (TrueNAS-HDD)" shows healthy
```

## Known Agent Hosts

| Host | IP | Agent Port | Notes |
|------|-----|-----------|-------|
| TrueNAS-HDD | 10.10.0.103 | 45876 | NAS, NFS server |
| UniFi-OS | 10.10.0.51 | 45876 | Network controller |

## Prevention

1. **Ensure SSH keys are persistent** — Beszel data PVC stores keys; don't delete the PVC
2. **Monitor agent connectivity** — Gatus TCP checks on agent ports
3. **Keep agents updated** — When upgrading Beszel hub, also update agents promptly
4. **Document agent hosts** — Maintain the known agents table above

## Related Alerts

- Gatus `Beszel Agent (TrueNAS-HDD)` — TCP connectivity check
- Gatus `Beszel` — Hub web UI health check

## Detection Methods

| Method | Status |
|--------|--------|
| Gatus TCP check (agent port 45876) | Active — checks every 120s |
| error-hunter sweep (Beszel API) | Active — periodic sweeps |
| Beszel hub UI | Manual — shows version mismatch |
