# LinuxServer Image Update

## Alert
- **Name**: UpdateAvailable-{app} (from Sonarr/Radarr health check or update-patrol)
- **Domain**: upgrade
- **Severity**: info

## Root Cause
LinuxServer.io publishes new Docker images when upstream applications release updates. The app's built-in health check reports an update available.

## Investigation
1. Check current image tag: `kubectl get deployment -n media <app> -o jsonpath='{.spec.template.spec.containers[0].image}'`
2. Check available tags on DockerHub: `curl -s "https://registry.hub.docker.com/v2/repositories/linuxserver/<app>/tags?page_size=5&ordering=last_updated"`
3. Confirm the tag exists and is for the correct architecture
4. Check `known-conditions.yaml` for pinned versions (e.g. mosquitto 2.0.22 is pinned)

## Fix Steps
1. Edit the deployment manifest: `prod_homelab/kubernetes/applications/media/<app>/deployment.yaml`
2. Update the `image:` tag to the new version
3. Commit and push via git workflow:
   ```bash
   git -C /home/prod_homelab add kubernetes/applications/media/<app>/deployment.yaml
   git -C /home/prod_homelab commit -m "fix: update <app> <old> -> <new>"
   git -C /home/prod_homelab push origin main
   ```
4. Update parent submodule pointer
5. Trigger ArgoCD sync: `argocd_sync_application(<app>)`

## Validation
- Pod Running 1/1 with new image tag
- App health check returns no warnings (the update available message is gone)
- Wait 60s after ArgoCD sync for Recreate strategy rollout

## Gotchas
- LinuxServer images use their own tag format (e.g. `6.0.4` not `v6.0.4`)
- Media apps use **Recreate** strategy (RWO Mayastor PVCs) — expect ~30s downtime during rollout
- Check `known-conditions.yaml` pinned_images before updating
- Major version bumps (e.g. 5.x -> 6.x) should be treated as `review` policy, not auto-applied

## History
- 2026-04-03: Radarr 6.0.4 -> 6.1.1 (Estate Patrol automated)
