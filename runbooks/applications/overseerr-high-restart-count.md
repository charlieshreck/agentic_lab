# Overseerr High Restart Count (HomelabPodHighRestartCount)

## Alert Trigger
Pod `overseerr` in namespace `media` (production cluster) has accumulated excessive restart count (threshold: 100+).

## Root Causes

### 1. **GitHub API Update Check Failure** (Most Common)
- **Symptom**: Pod logs show `fetch failed` when fetching GitHub releases on startup
- **Exit code**: 143 (SIGTERM - graceful termination)
- **Error**: `ELIFECYCLE  Command failed.`
- **Cause**: Overseerr attempts to check for updates from GitHub on every startup
- **Network issue**: Either DNS timeout, GitHub API unreachable, or network policy blocking external access

### 2. **Network Connectivity Issues**
- Pod cannot reach GitHub API servers
- DNS resolution failing
- CoreDNS not forwarding to correct upstream servers

### 3. **Memory or CPU Limits Exceeded**
- Application consuming more than 1Gi memory
- Pod eviction due to node resource pressure

## Resolution

### Quick Fix (Disable Update Checks)
1. Edit deployment manifest: `/home/prod_homelab/kubernetes/applications/media/overseerr/deployment.yaml`
2. Add environment variable to disable telemetry/update checks:
   ```yaml
   env:
   - name: DISABLE_TELEMETRY
     value: "true"
   ```

3. Add startup probe to allow extended startup time:
   ```yaml
   startupProbe:
     httpGet:
       path: /api/v1/status
       port: 5055
     initialDelaySeconds: 10
     periodSeconds: 5
     failureThreshold: 30
   ```

4. Increase liveness probe delay:
   ```yaml
   livenessProbe:
     httpGet:
       path: /api/v1/status
       port: 5055
     initialDelaySeconds: 60  # Allow 60s for startup
     periodSeconds: 30
     failureThreshold: 3
   ```

5. Commit and push (GitOps will sync automatically):
   ```bash
   git -C /home/prod_homelab add kubernetes/applications/media/overseerr/deployment.yaml
   git -C /home/prod_homelab commit -m "fix(overseerr): disable telemetry and add startup probe"
   git -C /home/prod_homelab push origin main
   ```

### Verify the Fix
```bash
# Check if pod is stable (no new restarts after deployment)
kubectl get pods -n media overseerr-* --watch

# Check logs for startup behavior
kubectl logs -n media deployment/overseerr --tail=100

# Verify API is responding
kubectl port-forward -n media svc/overseerr 5055:5055
curl http://localhost:5055/api/v1/status
```

### Long-term Prevention
1. **Monitor GitHub API**: Add alert if Overseerr repeatedly fails GitHub checks
2. **Network policy**: Ensure CoreDNS can resolve github.com properly
3. **Resource monitoring**: Watch memory/CPU usage patterns to catch early signs of issues
4. **Regular updates**: Keep Overseerr image up-to-date (currently using 2.3.0)

## Troubleshooting

### If restarts continue after fix
1. Check pod logs for other errors:
   ```bash
   kubectl logs -n media deployment/overseerr --previous --tail=200
   ```

2. Verify environment variables are applied:
   ```bash
   kubectl get deployment -n media overseerr -o yaml | grep -A5 env:
   ```

3. Check if PVC is healthy:
   ```bash
   kubectl get pvc -n media overseerr-config
   kubectl describe pvc -n media overseerr-config
   ```

4. Verify DNS resolution from pod:
   ```bash
   kubectl run -it --rm debug --image=busybox --restart=Never -n media -- sh
   nslookup github.com  # Should resolve to real IP, not 10.10.0.1
   ```

## Related Alerts
- `KubePodNotReady`: Pod cannot become ready (different root cause)
- `KubeContainerWaiting`: Pod stuck in waiting state
- `KubePodCrashLooping`: Application actually crashing (vs. liveness failures)

## References
- [Jellyseerr Environment Variables](https://github.com/fallenbagel/jellyseerr)
- [Kubernetes Startup Probe Documentation](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
- Alert rule: `HomelabPodHighRestartCount` (Prometheus)
