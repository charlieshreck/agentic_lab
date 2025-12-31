# Environment Variables and Secrets

**Comprehensive guide to secrets management for the Agentic AI Platform**

---

## ⚠️ CRITICAL SECURITY RULES

1. **NEVER commit actual secrets** to this repository
2. **ALWAYS use Infisical** (or SOPS) for secret storage
3. **NEVER hardcode secrets** in Kubernetes manifests
4. **ALWAYS use InfisicalSecret CRs** to sync secrets from Infisical to Kubernetes
5. **Review `.gitignore`** before committing any new files

---

## Infisical Project Setup

### Primary Project

- **Project Name**: `prod_homelab` (or create dedicated `agentic_lab` project)
- **Environment**: `prod`
- **Base Path**: `/agentic-platform/`

### Authentication

The Infisical Operator uses **Universal Auth** with credentials stored in:

```bash
kubectl get secret universal-auth-credentials \
  -n infisical-operator-system \
  -o jsonpath='{.data.clientId}' | base64 -d
# Outputs: Client ID for universal auth

kubectl get secret universal-auth-credentials \
  -n infisical-operator-system \
  -o jsonpath='{.data.clientSecret}' | base64 -d
# Outputs: Client secret for universal auth
```

---

## Secret Organization

All secrets are organized by component under `/agentic-platform/`:

```
/agentic-platform/
├── llm-apis/             # LLM API keys (Gemini, Claude)
├── telegram/             # Telegram bot credentials
├── home-assistant/       # Home Assistant long-lived token
├── arr-suite/            # Sonarr, Radarr, Prowlarr API keys
├── truenas/              # TrueNAS API credentials (if applicable)
└── observability/        # Coroot, Prometheus webhook tokens
```

---

## Required Secrets by Component

### 1. Infrastructure (Terraform)

**Note**: Bare metal Talos deployment requires no API credentials for infrastructure provisioning. All configuration is applied directly via `talosctl` using the generated machine secrets.

**Terraform State**: Consider using Terraform Cloud or encrypted S3 backend for state storage:
```hcl
# infrastructure/terraform/talos-cluster/backend.tf (optional)
terraform {
  backend "s3" {
    bucket = "homelab-terraform-state"
    key    = "agentic-lab/talos-cluster/terraform.tfstate"
    region = "us-east-1"
    encrypt = true
  }
}
```

### 2. LLM APIs

**Infisical Path**: `/agentic-platform/llm-apis`

| Key | Description | Required | Cost |
|-----|-------------|----------|------|
| `GEMINI_API_KEY` | Google Gemini API key | Optional | Pay-per-use |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key | Optional | Pay-per-use |
| `LITELLM_MASTER_KEY` | LiteLLM master key | Yes | N/A |

**How to Obtain**:
- **Gemini**: https://ai.google.dev/gemini-api/docs/api-key
- **Claude**: https://console.anthropic.com/settings/keys

**Kubernetes Usage**:
```yaml
apiVersion: secrets.infisical.com/v1alpha1
kind: InfisicalSecret
metadata:
  name: llm-api-keys
  namespace: ai-platform
spec:
  authentication:
    universalAuth:
      credentialsRef:
        secretName: universal-auth-credentials
        secretNamespace: infisical-operator-system
      secretsScope:
        projectSlug: prod-homelab-y-nij
        envSlug: prod
        secretsPath: /agentic-platform/llm-apis
  managedSecretReference:
    secretName: llm-api-keys
    secretNamespace: ai-platform
```

### 3. Telegram Bot

**Infisical Path**: `/agentic-platform/telegram`

| Key | Description | How to Get |
|-----|-------------|------------|
| `TELEGRAM_BOT_TOKEN` | Bot API token | Message @BotFather: `/newbot` |
| `TELEGRAM_FORUM_CHAT_ID` | Forum supergroup chat ID | Create forum, add bot, get ID from API |
| `TELEGRAM_WEBHOOK_SECRET` | Webhook verification secret | Generate: `openssl rand -hex 32` |

**How to Get Chat ID**:
```bash
# After adding bot to forum supergroup:
curl https://api.telegram.org/bot${BOT_TOKEN}/getUpdates | jq '.result[0].message.chat.id'
# Copy the negative number (starts with -100)
```

### 4. Home Assistant

**Infisical Path**: `/agentic-platform/home-assistant`

| Key | Description | How to Get |
|-----|-------------|------------|
| `HA_URL` | Home Assistant URL | `http://homeassistant.local:8123` |
| `HA_TOKEN` | Long-lived access token | Profile → Security → Long-Lived Access Tokens |

### 5. Arr Suite (Sonarr, Radarr, Prowlarr)

**Infisical Path**: `/agentic-platform/arr-suite`

| Key | Description | How to Get |
|-----|-------------|------------|
| `SONARR_URL` | Sonarr URL | `http://sonarr:8989` |
| `SONARR_API_KEY` | Sonarr API key | Settings → General → Security → API Key |
| `RADARR_URL` | Radarr URL | `http://radarr:7878` |
| `RADARR_API_KEY` | Radarr API key | Settings → General → Security → API Key |
| `PROWLARR_URL` | Prowlarr URL | `http://prowlarr:9696` |
| `PROWLARR_API_KEY` | Prowlarr API key | Settings → General → Security → API Key |
| `SABNZBD_URL` | SABnzbd URL | `http://sabnzbd:8080` |
| `SABNZBD_API_KEY` | SABnzbd API key | Config → General → Security → API Key |

### 6. Observability (Optional)

**Infisical Path**: `/agentic-platform/observability`

| Key | Description | Notes |
|-----|-------------|-------|
| `COROOT_API_KEY` | Coroot API key | If using Coroot from monit_homelab |
| `PROMETHEUS_WEBHOOK_TOKEN` | Webhook auth token | Generate: `openssl rand -hex 32` |

---

## Kubernetes Secret Pattern

All secrets are synced from Infisical using **InfisicalSecret** custom resources:

```yaml
apiVersion: secrets.infisical.com/v1alpha1
kind: InfisicalSecret
metadata:
  name: <component>-secrets
  namespace: <namespace>
spec:
  hostAPI: https://app.infisical.com/api
  authentication:
    universalAuth:
      credentialsRef:
        secretName: universal-auth-credentials
        secretNamespace: infisical-operator-system
      secretsScope:
        projectSlug: prod-homelab-y-nij  # Or your project slug
        envSlug: prod
        secretsPath: /agentic-platform/<component>
  managedSecretReference:
    secretName: <component>-secrets
    secretNamespace: <namespace>
    secretType: Opaque
    creationPolicy: Owner  # Operator owns the secret
```

The operator creates a Kubernetes `Secret` with the same keys as in Infisical.

---

## Local Development

For local testing (NOT for production):

```bash
# Copy example env file
cp .env.example .env

# Edit with actual values
vim .env

# Load into shell
export $(cat .env | xargs)

# Test LiteLLM
docker-compose -f docker-compose.dev.yaml up litellm

# Test Ollama
docker-compose -f docker-compose.dev.yaml up ollama
```

**⚠️ NEVER commit `.env` file** (it's in `.gitignore`)

---

## Secret Rotation

### Rotating API Keys

1. Generate new key in provider UI (Gemini, Claude, etc.)
2. Update Infisical via UI
3. Restart affected pods:
   ```bash
   kubectl rollout restart deployment/litellm -n ai-platform
   ```
4. Verify new key works
5. Revoke old key in provider UI

### Rotating Telegram Bot Token

1. Message @BotFather: `/revoke`
2. Create new bot or get new token
3. Update Infisical `/agentic-platform/telegram/TELEGRAM_BOT_TOKEN`
4. Restart telegram-service:
   ```bash
   kubectl rollout restart deployment/telegram-service -n ai-platform
   ```
5. Re-register webhook:
   ```bash
   curl -X POST "https://api.telegram.org/bot${NEW_TOKEN}/setWebhook" \
     -d "url=https://telegram-webhook.yourdomain.com/webhook"
   ```

---

## Backup and Disaster Recovery

### Exporting Secrets from Infisical

```bash
# Install Infisical CLI
brew install infisical/get-cli/infisical  # macOS
# Or: npm install -g @infisical/cli

# Login
infisical login

# Export secrets to encrypted file
infisical export --env prod --path /agentic-platform > secrets-backup.enc

# Store encrypted backup in secure location (NOT in git)
```

### Restoring Secrets

```bash
# Import from backup
cat secrets-backup.enc | infisical import --env prod --path /agentic-platform
```

---

## Verification

### Check Infisical Sync Status

```bash
# List all InfisicalSecrets
kubectl get infisicalsecrets -A

# Check specific secret status
kubectl describe infisicalsecret llm-api-keys -n ai-platform

# Verify Kubernetes secret was created
kubectl get secret llm-api-keys -n ai-platform

# View secret keys (NOT values)
kubectl get secret llm-api-keys -n ai-platform -o jsonpath='{.data}' | jq 'keys'
```

### Test Secrets in Pods

```bash
# LiteLLM using Gemini key
kubectl exec -n ai-platform deploy/litellm -- \
  env | grep GEMINI_API_KEY
# Should output: GEMINI_API_KEY=<value>

# Telegram service using bot token
kubectl exec -n ai-platform deploy/telegram-service -- \
  env | grep TELEGRAM_BOT_TOKEN
# Should output: TELEGRAM_BOT_TOKEN=<value>
```

---

## Troubleshooting

### InfisicalSecret not syncing

**Symptom**: InfisicalSecret created but Kubernetes Secret doesn't exist

**Check**:
```bash
# Check operator logs
kubectl logs -n infisical-operator-system deploy/infisical-operator-controller-manager

# Check InfisicalSecret status
kubectl describe infisicalsecret <name> -n <namespace>
```

**Common Issues**:
- Wrong project slug (use `prod-homelab-y-nij`, not `prod_homelab`)
- Wrong secrets path (must start with `/`)
- Universal auth credentials incorrect
- Network connectivity to Infisical API

### Secrets exist but pods can't access

**Check**:
```bash
# Verify secret mounted as volume
kubectl describe pod <pod-name> -n <namespace>
# Look for: Volumes → <secret-name>

# Or verify environment variables
kubectl exec <pod-name> -n <namespace> -- env | grep <KEY>
```

**Fix**: Ensure deployment references secret correctly:
```yaml
env:
  - name: GEMINI_API_KEY
    valueFrom:
      secretKeyRef:
        name: llm-api-keys
        key: GEMINI_API_KEY
```

---

## Security Best Practices

1. **Least Privilege**: Create separate Infisical folders for each component
2. **Rotation**: Rotate API keys quarterly (set calendar reminder)
3. **Audit**: Review Infisical audit logs monthly
4. **Backup**: Export secrets backup monthly, store encrypted
5. **Access Control**: Limit who can access Infisical production environment
6. **Monitoring**: Alert on InfisicalSecret sync failures

---

## Example InfisicalSecret Manifests

See `kubernetes/platform/infisical/examples/` for complete examples:
- `llm-api-keys-example.yaml`
- `telegram-secrets-example.yaml`
- `arr-suite-secrets-example.yaml`

---

## References

- Infisical Documentation: https://infisical.com/docs
- Infisical Kubernetes Operator: https://infisical.com/docs/integrations/platforms/kubernetes
- Terraform Sensitive Variables: https://developer.hashicorp.com/terraform/language/values/variables#sensitive-variables

---

**Remember**: If a secret is in git, you've already failed. Use Infisical for everything.
