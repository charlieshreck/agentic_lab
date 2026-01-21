# Claude OAuth Token Refresh Service

Manages Claude Code OAuth credentials with automatic syncing to Infisical and expiry monitoring.

## Overview

Claude Code uses OAuth tokens that expire periodically. This service:
- Stores credentials centrally in Infisical for all agents/services to access
- Provides a web UI for manual token updates (mobile-friendly)
- Monitors token expiry and alerts when refresh is needed
- Auto-syncs credentials after login via wrapper script

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌───────────────┐
│  claude-login   │────▶│  claude-refresh  │────▶│   Infisical   │
│  (wrapper)      │     │  (Flask app)     │     │   (secrets)   │
└─────────────────┘     └──────────────────┘     └───────────────┘
                               │
                               ▼
                        ┌──────────────┐
                        │     Keep     │
                        │   (alerts)   │
                        └──────────────┘
```

## Quick Start

### After Running `claude login`

Use the wrapper script that auto-syncs:

```bash
claude-login
```

Or manually sync after a regular login:

```bash
curl -X POST http://10.20.0.40:31110/api/push \
  -H "Content-Type: application/json" \
  -d @~/.claude/.credentials.json
```

### Check Token Status

```bash
curl http://10.20.0.40:31110/api/status
```

Response:
```json
{
  "expires": "2026-01-24T06:18:47",
  "days_remaining": 7,
  "is_expired": false,
  "needs_refresh": false,
  "status": "healthy"
}
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET/POST | Web UI for manual credential entry |
| `/health` | GET | Health check |
| `/api/status` | GET | Current token status (expiry, days remaining) |
| `/api/push` | POST | Push credentials JSON to Infisical |
| `/api/auto-refresh` | POST | Attempt OAuth refresh (may not work with Claude Max) |
| `/api/auto-refresh-if-needed` | POST | Only refresh if expiring soon |

## Access

| Type | URL |
|------|-----|
| Internal | `http://10.20.0.40:31110` |
| External | `https://claude-refresh.kernow.io` |
| Service | `http://claude-refresh.ai-platform.svc.cluster.local:8080` |

## Components

### 1. Flask Application (`configmap.yaml`)

Mobile-first web UI with:
- Token status display (healthy/warning/expired)
- Step-by-step login wizard
- Direct paste support (JSON or base64)
- One-liner command for CLI users

### 2. Token Monitor CronJob (`cronjob.yaml`)

Runs daily at 9am to check token expiry:
- Alerts via Keep when token < 3 days remaining
- Severity escalates: warning → critical → expired
- Job fails (visible in k8s) when alert triggered

### 3. Wrapper Script (`/usr/local/bin/claude-login`)

Replaces `claude login` with auto-sync:
```bash
#!/bin/bash
claude login "$@"
curl -X POST http://10.20.0.40:31110/api/push \
  -H "Content-Type: application/json" \
  -d @~/.claude/.credentials.json
```

## Infisical Secret

| Path | Key | Format |
|------|-----|--------|
| `/agentic-platform/claude` | `CREDENTIALS_JSON_B64` | Base64-encoded JSON |

The credential structure:
```json
{
  "claudeAiOauth": {
    "accessToken": "sk-ant-oat01-...",
    "refreshToken": "sk-ant-ort01-...",
    "expiresAt": 1768608858147,
    "scopes": ["user:inference", "user:profile"],
    "subscriptionType": "...",
    "rateLimitTier": "..."
  }
}
```

## Monitoring

### Manual Check
```bash
# Token status
curl -s http://10.20.0.40:31110/api/status | jq

# Trigger monitor job manually
kubectl create job --from=cronjob/claude-token-monitor token-check-now -n ai-platform
kubectl logs job/token-check-now -n ai-platform
```

### Alerts

When token expires in < 3 days, Keep receives:
```json
{
  "name": "ClaudeOAuthTokenExpiry",
  "status": "firing",
  "severity": "warning|critical",
  "description": "Claude OAuth token expires in X days...",
  "source": "claude-token-monitor"
}
```

## Limitations

- **Auto-refresh doesn't work**: Claude Max OAuth requires full PKCE flow, not simple refresh_token grants
- **Manual login required**: When token expires, you must run `claude-login` interactively
- **8-hour tokens**: Claude Max tokens typically have short lifetimes (~8 hours after login)

## Troubleshooting

### Token shows 0 days but isn't expired
Tokens < 24 hours show as 0 days. Check actual hours:
```bash
curl -s http://10.20.0.40:31110/api/status | jq '.expires'
```

### Push fails with Infisical error
Check Infisical credentials in the deployment:
```bash
kubectl logs -n ai-platform -l app=claude-refresh | tail -20
```

### CronJob not sending alerts
Verify Keep API key is configured:
```bash
kubectl get secret claude-refresh-secrets -n ai-platform -o yaml
```

## Related

- Infisical path: `/agentic-platform/claude`
- Keep alert: `ClaudeOAuthTokenExpiry`
- ArgoCD app: `claude-refresh`
