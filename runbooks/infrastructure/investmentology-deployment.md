# Investmentology Deployment

## Architecture
- **API + PWA**: K8s Deployment in `investmentology` namespace (prod cluster)
- **CLI Agents**: HB LXC (VMID 101, 10.10.0.101 on Hikurangi)
- **Database**: Shared PostgreSQL in agentic cluster
- **Secrets**: Infisical at `/platform/haute-banque/`

## K8s Components
| Resource | Name | Purpose |
|----------|------|---------|
| Deployment | investmentology | API + PWA (serve.py, port 80) |
| Service | investmentology | ClusterIP port 80 |
| Ingress (Traefik) | investmentology-internal | Internal: haute-banque.kernow.io |
| Ingress (Cloudflare) | investmentology-external | External: haute-banque.kernow.io |
| InfisicalSecret | investmentology-secrets | Pulls from /platform/haute-banque |
| CronJob | investmentology-price-refresh | Mon-Fri market hours |
| CronJob | investmentology-screen | Sun 06:00 UTC |
| CronJob | investmentology-post-screen | Sun 07:00 UTC |
| CronJob | investmentology-portfolio-sync | Mon-Fri 13:00 UTC |

## CI/CD
1. Push to `main` on `charlieshreck/investmentology`
2. GitHub Actions: test → build Docker → push GHCR
3. ArgoCD auto-syncs from `k8s/base/`
4. Image: `ghcr.io/charlieshreck/investmentology:latest`

## Manual Deployment
```bash
# Check ArgoCD app status
kubectl --context admin@homelab-prod get app investmentology -n argocd

# Force sync
kubectl --context admin@homelab-prod -n argocd patch app investmentology --type merge -p '{"operation":{"initiatedBy":{"username":"admin"},"sync":{"revision":"HEAD"}}}'

# Check pods
kubectl --context admin@homelab-prod get pods -n investmentology

# Check CronJob history
kubectl --context admin@homelab-prod get jobs -n investmentology
```

## HB LXC Analysis Worker
The analysis worker on HB LXC handles CLI-agent-dependent jobs:
- `investmentology-daily-analyze.timer` — 05:30 UTC daily
- `investmentology-monitor.timer` — 21:15 UTC daily

SSH to HB LXC:
```bash
ssh root@10.10.0.178 "pct exec 101 -- bash -c 'systemctl status investmentology'"
ssh root@10.10.0.178 "pct exec 101 -- bash -c 'journalctl -u investmentology -n 50'"
```

## Troubleshooting
- **Pod CrashLoopBackOff**: Check DB connectivity (`DATABASE_URL` in Infisical)
- **CronJob stuck**: Check `concurrencyPolicy: Forbid` — previous job may still be running
- **Analysis not running**: Check HB LXC timers via Hikurangi
