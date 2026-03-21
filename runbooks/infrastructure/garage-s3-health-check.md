# Garage S3 API Health Check Troubleshooting

## Overview

Gatus monitors Garage S3 API health via HTTP requests to the Anonymous API endpoint (port 30188). This runbook covers common issues with the health check endpoint.

## Key Details

- **TrueNAS-HDD**: 10.10.0.103 (prod network)
- **Garage S3 API Port**: 30188 (Anonymous endpoint)
- **Garage Web UI Port**: 30186
- **Health Check Timeout**: 30s
- **Health Check Interval**: 60s
- **Monitoring Cluster**: talos-monitor (10.10.0.30) on monit network

## Common Issues

### Issue: Health Check Timeout or "Context Deadline Exceeded"

**Root Cause**: Health check condition too restrictive or network connectivity issue.

**Symptoms**:
- Gatus shows unhealthy status
- Alert firing in Discord/monitoring system
- Error: `Get "http://10.10.0.103:30188": context deadline exceeded`

**Diagnosis**:

1. **Verify TrueNAS Connectivity**:
   ```bash
   kubectl exec -it <gatus-pod> -n monitoring -- /bin/sh
   ping 10.10.0.103
   curl -v http://10.10.0.103:30188
   ```

2. **Check Garage Service Status**:
   ```bash
   # SSH to TrueNAS-HDD and check Garage container
   ssh root@10.10.0.103
   docker ps | grep garage
   docker logs <garage-container>
   ```

3. **Verify Monit Cluster Networking**:
   ```bash
   # Check CoreDNS forwarder (should point to 10.10.0.1)
   kubectl get cm -n kube-system coredns -o yaml | grep forward
   ```

### Issue: HTTP Response Code Mismatch

**Root Cause**: Health check condition expects specific HTTP code but Garage returns different code.

**Symptoms**:
- Health check fails despite Garage responding
- Manual curl succeeds but Gatus shows unhealthy

**Resolution**:

Garage S3 Anonymous API returns specific response codes for authentication failures:
- **HTTP 400 Bad Request**: Invalid request format (most common for anonymous requests)
- **HTTP 403 Forbidden**: Request requires authentication (legacy response)

The Gatus health check condition should accept both:
```yaml
conditions:
  - "[STATUS] == any(400, 403)"
```

**File**: `/home/monit_homelab/kubernetes/platform/gatus/deployment.yaml` (line 60)

## Incident #504 Resolution

**Date**: 2026-03-20
**Issue**: Gatus Garage S3 endpoint health check failing with timeout
**Root Cause**: Condition was `[STATUS] == 403` but Garage API returns 400 Bad Request for anonymous requests
**Fix**: Updated condition to `[STATUS] == any(400, 403)` to accept both valid response codes
**Commit**: `6ee5f8d` in monit_homelab

This is expected behavior. The Garage S3 Anonymous endpoint is designed to require authentication, so 400/403 responses from unauthenticated requests are valid indicators that the service is healthy and responding.

## Prevention

- Document that `[STATUS] == any(400, 403)` is the correct condition for Garage S3 Anonymous API monitoring
- Avoid changing this condition without verifying actual Garage API response codes
- Test health checks manually via curl before deploying configuration changes
