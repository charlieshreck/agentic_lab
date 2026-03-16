---
id: 499
title: KubeJobFailed - Matter Hub Health Check CronJob
severity: medium
status: resolved
created: 2026-02-22
resolved: 2026-03-16
duration: 22 days
components:
  - kubernetes: matter-hub
  - resource: CronJob
  - namespace: apps
---

## Summary

Recurring KubeJobFailed alerts for the `matter-hub-health-check` CronJob in the `apps` namespace. The job runs every 10 minutes to verify the Matter Hub HTTP server and Matter Server TCP port connectivity.

**Root Cause**: Kubernetes auto-injects service environment variables in the format `protocol://IP:port` (e.g., `tcp://10.X.X.X:5580`), which is incompatible with the netcat TCP port check in the health script.

## Investigation Details

### Initial Problem
- Job: `matter-hub-health-check-29557250` (and earlier)
- Error: Netcat command failing silently, causing false negatives
- Impact: Health check unable to validate Matter Server TCP connectivity

### Root Cause Analysis
The Kubernetes service discovery mechanism injects environment variables for all exposed services:
```bash
MATTER_SERVER_PORT="tcp://IP:5580"  # Wrong format for netcat
```

Netcat expects:
```bash
nc -z -w10 "HOST" "5580"  # Port number only
```

Using the Kubernetes-injected variable fails because `nc` receives `tcp://...` which is invalid.

## Solution (Two-Phase)

### Phase 1: Script Fallback (Feb 22, 2026)
**Commit**: `7f52872`
**File**: `/home/prod_homelab/kubernetes/applications/apps/matter-hub/health-check.yaml`

Modified the health check script to use an explicit environment variable:
```bash
# Use MATTER_SERVER_SERVICE_PORT (5580) instead of MATTER_SERVER_PORT (tcp://IP:5580)
# Kubernetes auto-injects MATTER_SERVER_PORT as "protocol://IP:port" which breaks netcat
MATTER_SERVER_PORT="${MATTER_SERVER_SERVICE_PORT:-5580}"
```

This allows the script to work correctly when `MATTER_SERVER_SERVICE_PORT` is explicitly provided, with a safe fallback to 5580.

### Phase 2: Hardening (Mar 16, 2026)
**Commit**: `1a224ac`
**File**: `/home/prod_homelab/kubernetes/applications/apps/matter-hub/health-check.yaml`

Made the port explicit in the CronJob environment spec to eliminate reliance on script defaults:
```yaml
env:
- name: MATTER_HUB_URL
  value: "http://matter-hub.apps.svc.cluster.local:8482"
- name: MATTER_SERVER_SERVICE_PORT
  value: "5580"
```

This ensures the variable is always available and the health check is robust regardless of future configuration changes.

## Verification

Health check script performs two checks:

1. **HTTP Check**: Validates Matter Hub HTTP response (expects 200-499 status codes)
2. **TCP Check**: Verifies Matter Server port 5580 is reachable with 3 retry attempts

Both checks are now passing consistently after the hardening fix.

## Key Learnings

1. **Kubernetes Service Variables**: `${SERVICE_NAME}_PORT` is always `protocol://IP:port`. Use `${SERVICE_NAME}_SERVICE_PORT` for just the port number.

2. **Environment Variable Fallback Pattern**:
   - Always provide explicit environment variables for components that need them
   - Use shell fallback pattern: `${VAR:-default}` for robustness
   - Hardening: Make explicit vars part of the manifest to avoid relying on fallbacks

3. **Health Check Design**:
   - Shell scripts in Kubernetes should use named environment variables
   - Avoid parsing auto-injected variables that have different formats
   - Test health checks with actual Kubernetes service discovery enabled

## Prevention

- Document the Kubernetes `${SERVICE_NAME}_PORT` quirk in team runbooks
- Review health check scripts during code review to catch `${VAR}_PORT` usage
- Consider using a health check library that understands Kubernetes service discovery

## References

- [Kubernetes Service Discovery Docs](https://kubernetes.io/docs/concepts/services-networking/service/#environment-variables)
- [Shell Parameter Expansion](https://pubs.opengroup.org/onlinepubs/9699919799/utilities/V3_chap02.html#tag_18_06_02)
