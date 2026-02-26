# Haute Banque LXC Rebuild

Disaster recovery runbook for rebuilding the HB LXC from scratch.

## Recovery Time: ~30 minutes

## Prerequisites
- Hikurangi (10.10.0.178) Proxmox host accessible
- Terraform state available
- Ansible inventory configured
- Git access to `charlieshreck/investmentology`

## Step 1: Terraform Provision (5 min)
```bash
cd /home/prod_homelab/infrastructure/terraform
terraform apply -target=module.hb_lxc
```
This creates the LXC container with correct resources and networking.

## Step 2: Ansible Configuration (10 min)
```bash
cd /home/prod_homelab/infrastructure/ansible
ansible-playbook -i inventory/lxc.yml playbooks/hb-worker.yml
```
This installs:
- Python 3.12+, Node.js 22
- Infisical CLI
- All systemd units and timers
- Base packages

## Step 3: Application Code (5 min)
```bash
ssh root@10.10.0.178 "pct exec 101 -- bash -c '
  cd /home && git clone git@github.com:charlieshreck/investmentology.git
  cd investmentology && pip install -e .
'"
```

## Step 4: Claude & Gemini CLI Auth (5 min)
These require interactive authentication:
```bash
ssh root@10.10.0.178 "pct exec 101 -- bash"
# Then manually:
# 1. Install Claude CLI and authenticate
# 2. Copy Gemini oauth_creds.json from backup or re-authenticate
```

## Step 5: Restore Screen Sessions (2 min)
```bash
ssh root@10.10.0.178 "pct exec 101 -- bash -c 'systemctl start screens'"
```

## Step 6: Verify (3 min)
```bash
ssh root@10.10.0.178 "pct exec 101 -- bash -c '
  systemctl status investmentology
  systemctl status synapse-hb
  systemctl list-timers --all
  curl -s localhost/api/invest/system/health
'"
```

## Accepted Risk
HB LXC is a single point of failure for AI analysis (CLI agents). This is accepted due to CLI subscription cost savings vs API keys. See production hardening plan for details.

## PBS Backup
Daily backups to PBS (10.10.0.151). Check backup status:
```bash
# From PBS
pvesh get /nodes/localhost/storage/pbs-datastore/content --type backup | grep 101
```
