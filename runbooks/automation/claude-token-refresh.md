# Claude OAuth Token Refresh

## Trigger Pattern
- Alert: `ClaudeOAuthTokenExpiry`
- Symptom: Claude Code authentication failures
- Symptom: "OAuth token has expired" errors

## Quick Resolution

```bash
# Run the login wrapper (auto-syncs to Infisical)
claude-login
```

## Manual Steps

1. **Check current status**
   ```bash
   curl -s http://10.20.0.40:31110/api/status | jq
   ```

2. **If expired or expiring soon, login**
   ```bash
   claude login
   ```

3. **Sync credentials to Infisical**
   ```bash
   curl -X POST http://10.20.0.40:31110/api/push \
     -H "Content-Type: application/json" \
     -d @~/.claude/.credentials.json
   ```

4. **Verify sync succeeded**
   ```bash
   curl -s http://10.20.0.40:31110/api/status | jq
   ```

## Alternative: Web UI

1. Open https://claude-refresh.kernow.io on phone
2. Follow the 3-step wizard
3. Copy credentials from `~/.claude/.credentials.json`
4. Paste into the form

## Root Cause

Claude Max OAuth tokens have short lifetimes (~8 hours). The refresh_token cannot be used programmatically - Claude requires the full PKCE browser flow.

## Prevention

- CronJob `claude-token-monitor` runs daily at 9am
- Alerts via Keep when < 3 days remaining
- Use `claude-login` wrapper to always sync after login

## Escalation

If login fails repeatedly:
1. Check Claude service status: https://status.anthropic.com
2. Try logging out first: `claude logout`
3. Clear credentials: `rm ~/.claude/.credentials.json`
4. Re-login: `claude-login`

## Service Location

- Internal: http://10.20.0.40:31110
- External: https://claude-refresh.kernow.io
- Namespace: ai-platform
- Deployment: claude-refresh
