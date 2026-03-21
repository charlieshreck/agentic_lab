# Gatus S3 API Health Check Configuration

## Problem

The Garage S3 API health check endpoint was configured too restrictively, expecting only HTTP 403 responses for anonymous API requests. However, the API sometimes returns HTTP 400 (Bad Request), which is also a valid and normal response for unauthenticated S3 operations.

This caused false-positive health check failures when the API returned 400 instead of 403.

## Root Cause

S3 API specification allows multiple valid HTTP status codes for denied access:
- **HTTP 400 (Bad Request)**: Invalid request format or missing required headers
- **HTTP 403 (Forbidden)**: Valid request but access denied due to authentication/permissions

The original Gatus condition was overly strict:
```yaml
conditions:
  - "[STATUS] == 403"  # Only accepts 403
```

## Solution

Update the Gatus health check condition to accept both valid response codes:
```yaml
conditions:
  - "[STATUS] == any(400, 403)"  # Accept both 400 and 403
```

## Implementation

Location: `monit_homelab/kubernetes/platform/gatus/deployment.yaml` (ConfigMap `gatus-config`)

Edit the Garage S3 API endpoint section:
```yaml
endpoints:
  - name: Garage S3 API
    group: Storage
    url: "http://10.10.0.103:30188"
    interval: 60s
    conditions:
      - "[STATUS] == any(400, 403)"  # ← Updated condition
    client:
      insecure: true
      timeout: 30s
    alerts:
      - type: custom
      - type: discord
        description: "Garage S3 API is down"
```

## Verification

After deploying via GitOps:
1. Check Gatus web UI at `https://gatus.kernow.io/`
2. Verify "Garage S3 API" endpoint shows "UP" status in Storage group
3. Confirm ArgoCD has synced the gatus Application (check `monit` cluster context)

## Prevention

When configuring S3 health checks:
- S3-compatible APIs (Garage, MinIO, AWS) return **400 or 403** for anonymous requests
- Accept both status codes in the condition using `any(400, 403)` syntax
- Test with actual anonymous requests before deployment: `curl -v http://<s3-endpoint>/`

## References

- Gatus ConfigMap: `monit_homelab/kubernetes/platform/gatus/deployment.yaml`
- Garage S3: TrueNAS-HDD at 10.10.0.103:30188
- Incident #504: Resolved 2026-03-20 (commit 6ee5f8d)
