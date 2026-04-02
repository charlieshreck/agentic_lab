# SearXNG CrashLoopBackOff — K8s Env Var Collision

## Alert
- **Name**: SearXNG-CrashLoopBackOff
- **Cluster**: agentic
- **Namespace**: ai-platform
- **Severity**: warning

## Symptoms
- SearXNG pod in CrashLoopBackOff with repeated restarts
- Granian error: `Invalid value for '--port': 'tcp://IP:8080' is not a valid integer`
- External-MCP web search tools may fail or degrade

## Root Cause
K8s automatically injects environment variables based on Service names. When a Service is named `searxng`, K8s creates `SEARXNG_PORT=tcp://10.x.x.x:8080`. SearXNG 2026.4.1+ switched from uwsgi to granian as the ASGI server, and granian reads `SEARXNG_PORT` as the port value. It receives the full TCP URL instead of an integer.

This is the well-known K8s service env var collision pattern.

## Fix
Add an explicit `SEARXNG_PORT` env var in the deployment to override the K8s-injected one:

```yaml
env:
  - name: SEARXNG_PORT
    value: "8080"
```

Manifest: `agentic_lab/kubernetes/applications/mcp-servers/searxng.yaml`

## Fix Steps
1. Edit `searxng.yaml` — add `SEARXNG_PORT: "8080"` to deployment env
2. Commit and push to `agentic_lab`
3. Sync ArgoCD app `mcp-servers`
4. Validate: new pod Running 1/1, `wget -qO- http://localhost:8080/healthz` returns OK

## Validation
```bash
kubectl get pods -n ai-platform | grep searxng  # Should show Running 1/1
kubectl exec -n ai-platform <pod> -- wget -qO- http://localhost:8080/healthz  # Should return OK
```

## Lessons Learned
- K8s injects `{SERVICE_NAME}_PORT=tcp://IP:port` for every Service. If the app reads an env var matching this pattern, it breaks.
- Always check for env var collisions when an app starts crashing after an image update.
- SearXNG image updates may change the ASGI server (uwsgi -> granian), introducing new env var sensitivities.

## Automation Potential
- Add a pre-deploy check that warns when Service names could collide with known env var patterns.
- Pin SearXNG to a specific version tag instead of `latest` to prevent surprise breakage.

## History
- **2026-04-02**: First occurrence. SearXNG 2026.4.1 switched to granian. Fixed by Estate Patrol v2 (commit 832cf7a).
