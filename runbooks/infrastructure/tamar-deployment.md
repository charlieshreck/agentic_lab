# Tamar Deployment

## Architecture
- **Server**: Express + Node.js on Synapse LXC (VMID 100, 10.10.0.22 on Pihanga)
- **Frontend**: React + Vite, built to `/home/tamar/public/`
- **Session store**: Redis db 3 (local)
- **Secrets**: Infisical at `/platform/tamar/`
- **Systemd**: tamar.service

## Access
- Internal: `https://tamar.kernow.io` (AdGuard → Caddy → 10.10.0.22:3456)
- External: Cloudflare tunnel via prod cluster

## CI/CD
1. Push to `main` on `charlieshreck/kernow-homelab` (changes in `tamar/`)
2. GitHub Actions: build frontend → rsync to LXC → restart service
3. Requires `SYNAPSE_SSH_KEY` GitHub secret

## Manual Deployment
```bash
# SSH to Synapse LXC
ssh root@10.10.0.22

# Check service
systemctl status tamar

# View logs
journalctl -u tamar -n 50 -f

# Manual restart
systemctl restart tamar

# Rebuild frontend
cd /home/tamar/client && npx vite build
```

## Ansible-Managed Config
```bash
cd /home/prod_homelab/infrastructure/ansible
ansible-playbook -i inventory/lxc.yml playbooks/tamar.yml
```

The `tamar` Ansible role manages:
- Node.js 22 LTS installation
- Redis configuration
- systemd unit with Infisical secret injection
- Service enablement and startup

## Secrets (Infisical /platform/tamar/)
| Key | Purpose |
|-----|---------|
| AUTH_USERNAME | Login username |
| AUTH_PASSWORD | Login password |
| SESSION_SECRET | Cookie signing key |
| A2A_API_TOKEN | Agent-to-agent API auth |

## Troubleshooting
- **Service won't start**: Check `journalctl -u tamar -n 100`
- **Auth failing**: Verify Infisical CLI works: `infisical export --env=prod --path=/platform/tamar`
- **Frontend stale**: Rebuild: `cd /home/tamar/client && npx vite build`
- **Redis issues**: `redis-cli -n 3 DBSIZE` to check session store

## Monitoring: Transient CPU Spikes
**Pattern**: Pulse alerts for `cpu - synapse` at 80-87% (instances #330 on 2026-03-01, similar incident 2026-02-26)

**Expected behavior**:
- Node.js server occasionally spikes to 80-90% CPU during brief workload (request processing, garbage collection, agent dispatch)
- Spike lasts <1 minute, self-heals immediately
- Baseline CPU usage is very low (~0.2% average, 4m total in 24h)

**Verification**:
```bash
# SSH to Synapse
ssh root@10.10.0.22

# Check current CPU (should be <15%)
top -b -n1 | grep "node"

# Check sustained load (should be <2.0)
uptime

# Check service health (should show "active (running)")
systemctl status tamar
```

**When to escalate**:
- CPU spike persists >5 minutes
- Multiple restarts detected (`systemctl show tamar | grep Restart`)
- Memory usage >500MB sustained
- Service unable to process requests (test: `curl https://tamar.kernow.io/`)

**When to auto-resolve**:
- Current CPU <20% AND load <1.5 AND service running
- Spike already resolved (self-healed within 1 minute of alert)
- No errors in `journalctl -u tamar` (past hour)
