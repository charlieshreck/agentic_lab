# Documentation Update Summary
## Signal → Telegram + Hybrid Inference

---

## Files to Update

| File | Action | Artifact |
|------|--------|----------|
| `unified-architecture.md` | **Replace entire file** | `unified-architecture-updated` |
| `cloud-only-architecture-doc.md` | **Replace entire file** | `cloud-only-updated` |
| `routing-flow.mermaid` | **Replace entire file** | `routing-flow-telegram` |
| `architecture-diagram.mermaid` | **Update HITL section** | `architecture-diagram-hitl` |

---

## Quick Reference: Key Changes

### 1. Notification System

| Old | New |
|-----|-----|
| Signal CLI | Telegram Bot API |
| signal-cli container | telegram-service |
| Plain text messages | Inline keyboards + Forum topics |
| Flat conversation | Topic-based organization |
| Text command parsing | Callback query handling |
| Port 8080 | Port 8080 |

### 2. Inference Modes

| Mode | Behavior |
|------|----------|
| `local_first` | Ollama → escalate to cloud if confidence < 0.7 |
| `cloud_only` | Skip local, direct to Gemini/Claude |
| `local_only` | Never touch cloud APIs |
| `cloud_first` | Try cloud → fallback to local if API fails |

### 3. Telegram Forum Topics

| Topic | Purpose |
|-------|---------|
| 🔴 Critical Alerts | High-priority, immediate attention |
| 🟡 Arr Suite | Sonarr, Radarr, Prowlarr, Plex |
| 🔵 Infrastructure | K8s, ArgoCD, storage, network |
| 🏠 Home Assistant | HA, Tasmota, MQTT, Zigbee |
| 📊 Weekly Reports | Scheduled digests |
| 🔧 Incident #N | Dynamic, agent-created |
| ✅ Resolved | Archive of closed items |

### 4. Commands Changed

| Old (Signal) | New (Telegram) |
|--------------|----------------|
| Text: `1` | Button: `[1️⃣]` |
| Text: `approve` | Button: `[✅ Approve]` |
| Text: `ignore` | Button: `[❌ Ignore]` |
| Text: `details` | Button: `[🔍 Details]` |
| - | Button: `[☁️ Re-analyze]` (cloud bypass) |
| - | Text: `/mode cloud_only` |

---

## Environment Variables

### Remove (Signal)
```bash
SIGNAL_PHONE_NUMBER=
SIGNAL_CLI_CONFIG_PATH=
```

### Add (Telegram)
```bash
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_FORUM_CHAT_ID=-100xxxxxxxxxx
TELEGRAM_WEBHOOK_URL=https://telegram-webhook.yourdomain.com/webhook
```

### Add (Hybrid Inference)
```bash
INFERENCE_MODE=local_first
LOCAL_CONFIDENCE_THRESHOLD=0.7
CLOUD_ESCALATION_MODEL=cloud/gemini-flash
```

---

## Kubernetes Changes

### Old Deployment Reference
```yaml
# REMOVE or update
apps/ai-platform/signal-cli/
```

### New Deployment
```yaml
# ADD
apps/ai-platform/telegram-service/
├── deployment.yaml
├── service.yaml
├── ingress.yaml
├── configmap.yaml  # topic policies
└── kustomization.yaml
```

---

## Commit Message Template

```
feat: Replace Signal with Telegram Forum for human-in-the-loop

BREAKING CHANGE: Signal CLI removed, Telegram Bot API now required

Changes:
- Telegram Forum with topic-based message routing
- Inline keyboards for approval workflows
- Dynamic topic creation for complex incidents
- Hybrid inference with mode switching (local_first, cloud_only, local_only)
- Cloud bypass capability via button or command

New features:
- Per-topic organization (Critical, Arr Suite, Infrastructure, etc.)
- Agent can create/close topics dynamically
- Re-analyze button to bypass local and use cloud
- /mode command to switch inference modes

Migration:
- Create Telegram bot via @BotFather
- Create Forum supergroup, add bot as admin
- Update secrets with TELEGRAM_BOT_TOKEN and TELEGRAM_FORUM_CHAT_ID
- Deploy telegram-service
- Remove signal-cli deployment

Docs updated:
- unified-architecture.md
- cloud-only-architecture-doc.md
- routing-flow.mermaid
- architecture-diagram.mermaid
```

---

## Verification Checklist

After committing, verify:

- [ ] Telegram bot responds to `/start`
- [ ] Standing topics created in Forum
- [ ] Messages route to correct topics
- [ ] Inline keyboards render
- [ ] Button callbacks execute actions
- [ ] `/mode` command switches inference
- [ ] `☁️ Re-analyze` bypasses local LLM
- [ ] Weekly report posts to 📊 topic
- [ ] Incidents create dynamic topics
- [ ] Resolved incidents archive to ✅ topic
