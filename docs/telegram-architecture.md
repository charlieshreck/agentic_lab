# Telegram Human-in-the-Loop Architecture
## Forum-Based Agentic Communication Layer

---

## Decision Record

| Field | Value |
|-------|-------|
| **Decision** | Telegram Bot with Forum Topics for human-in-the-loop communication |
| **Date** | 2024-12-30 |
| **Status** | Approved |
| **Supersedes** | Signal CLI (original architecture docs) |
| **Rationale** | Native Bot API, Forum Topics for scalable organization, IaC-compatible, inline keyboards for approvals |

### Why Not Signal?

| Criteria | Signal | Telegram | Decision Factor |
|----------|--------|----------|-----------------|
| Official Bot API | ❌ None (signal-cli unofficial) | ✅ Native | IaC compatibility |
| Scalable chat organization | ❌ Flat conversation | ✅ Forum Topics | Agentic routing |
| Interactive buttons | ❌ Text only | ✅ Inline keyboards | UX for approvals |
| Declarative deployment | ❌ Manual phone registration | ✅ Token-based | GitOps principle |
| Container-native | ⚠️ DBus complexity | ✅ Simple HTTP | K8s deployment |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TELEGRAM FORUM ARCHITECTURE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  🏠 Homelab Ops (Forum Supergroup)                                           │
│  ├── 📌 General                    # Default topic                           │
│  ├── 🔴 Critical Alerts            # Standing topic - high priority          │
│  ├── 🟡 Arr Suite                  # Standing topic - *arr domain            │
│  ├── 🔵 Infrastructure             # Standing topic - K8s/storage/network    │
│  ├── 🏠 Home Assistant             # Standing topic - HA domain              │
│  ├── 📊 Weekly Reports             # Standing topic - scheduled digests      │
│  ├── 🔧 Incident #47               # Dynamic topic - agent-created           │
│  └── ✅ Resolved                    # Standing topic - archive                │
│                                                                              │
│  Agent Capabilities:                                                         │
│  • Create/close/reopen topics dynamically                                    │
│  • Route messages to appropriate topics                                      │
│  • Present inline keyboard buttons for approvals                             │
│  • Track conversation context per topic                                      │
│  • Learn routing patterns from human behavior                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Part I: Bot Setup

### Prerequisites

1. Create bot via [@BotFather](https://t.me/botfather)
2. Store token in SOPS-encrypted secret
3. Create Forum Supergroup and add bot as admin
4. Enable `can_manage_topics` permission for bot

### Terraform Configuration

```hcl
# terraform/telegram/main.tf

# Note: Telegram doesn't have official Terraform provider
# Bot creation is manual via BotFather, but we document the config

locals {
  telegram_config = {
    bot_username = "homelab_ops_bot"
    forum_name   = "Homelab Ops"
    
    standing_topics = {
      critical       = { icon = "🔴", name = "Critical Alerts" }
      arr_suite      = { icon = "🟡", name = "Arr Suite" }
      infrastructure = { icon = "🔵", name = "Infrastructure" }
      home_assistant = { icon = "🏠", name = "Home Assistant" }
      weekly_reports = { icon = "📊", name = "Weekly Reports" }
      resolved       = { icon = "✅", name = "Resolved" }
    }
  }
}

# Output for documentation
output "telegram_setup_instructions" {
  value = <<-EOT
    Manual Setup Required:
    1. Message @BotFather: /newbot
    2. Name: ${local.telegram_config.forum_name} Bot
    3. Username: ${local.telegram_config.bot_username}
    4. Save token to: infisical set TELEGRAM_BOT_TOKEN --env prod
    5. Create supergroup, convert to Forum
    6. Add bot as admin with can_manage_topics
    7. Run: kubectl apply -f k8s/telegram-init-job.yaml
  EOT
}
```

### Kubernetes Secret (SOPS)

```yaml
# k8s/secrets/telegram-secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: telegram-secrets
  namespace: ai-platform
type: Opaque
stringData:
  # Encrypted with SOPS
  TELEGRAM_BOT_TOKEN: ENC[AES256_GCM,data:...,type:str]
  TELEGRAM_FORUM_CHAT_ID: ENC[AES256_GCM,data:...,type:str]
```

---

## Part II: Topic Management

### Topic Policies Configuration

```yaml
# config/telegram-topics.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: telegram-topic-policies
  namespace: ai-platform
data:
  policies.yaml: |
    # Standing topics - created on init, always exist
    standing_topics:
      - key: critical
        name: "🔴 Critical Alerts"
        description: "High-priority alerts requiring immediate attention"
        pinned: true
        
      - key: arr_suite
        name: "🟡 Arr Suite"
        description: "Sonarr, Radarr, Prowlarr, SABnzbd notifications"
        domains: ["sonarr", "radarr", "prowlarr", "sabnzbd", "plex"]
        
      - key: infrastructure
        name: "🔵 Infrastructure"
        description: "Kubernetes, ArgoCD, storage, network"
        domains: ["k8s", "argocd", "storage", "network", "proxmox", "talos"]
        
      - key: home_assistant
        name: "🏠 Home Assistant"
        description: "Home automation, Tasmota, sensors"
        domains: ["homeassistant", "tasmota", "mqtt", "zigbee"]
        
      - key: weekly_reports
        name: "📊 Weekly Reports"
        description: "Scheduled summaries and learning digests"
        
      - key: resolved
        name: "✅ Resolved"
        description: "Archive of closed incidents"

    # Dynamic topic policies
    dynamic_topics:
      incident:
        name_template: "🔧 {title} #{id}"
        create_conditions:
          - severity: critical
          - estimated_complexity: high
          - requires_investigation: true
        auto_close_after_hours: 168  # 7 days
        archive_to: resolved
        
      renovation_pr:
        name_template: "📦 PR #{pr_number}: {title}"
        create_conditions:
          - breaking_changes: true
          - requires_discussion: true
        auto_close_after_hours: 72  # 3 days
        
      scheduled_task:
        name_template: "📅 {task_name}"
        auto_close_after_hours: 24

    # Cleanup policies
    cleanup:
      closed_topic_retention_days: 30
      auto_delete_empty_topics: true
      archive_closed_to_resolved: true

    # Routing rules (agent learns from these, can override)
    routing_rules:
      - match:
          alertname: ".*OOM.*|.*Memory.*"
          namespace: "apps"
        route_to: arr_suite
        
      - match:
          alertname: ".*"
          severity: critical
        route_to: critical
        
      - match:
          source: renovate
        route_to: infrastructure
        
      - match:
          domain: homeassistant
        route_to: home_assistant
```

### Topic Manager Service

```python
# src/telegram/topic_manager.py
"""
Telegram Forum Topic Manager for Agentic Workflows.

Handles creation, routing, and lifecycle of forum topics.
Learns from human behavior to improve routing decisions.
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional
import yaml

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from knowledge_mcp import KnowledgeMCP


@dataclass
class TopicInfo:
    """Represents a forum topic."""
    key: str
    topic_id: int
    name: str
    created_at: datetime
    is_standing: bool
    domain: Optional[str] = None
    incident_id: Optional[str] = None


class TelegramTopicManager:
    """Manages Telegram forum topics with agentic capabilities."""
    
    def __init__(
        self,
        bot_token: str,
        forum_chat_id: int,
        knowledge_mcp: KnowledgeMCP,
        policies_path: str = "/config/policies.yaml"
    ):
        self.bot = Bot(token=bot_token)
        self.forum_chat_id = forum_chat_id
        self.knowledge = knowledge_mcp
        self.policies = self._load_policies(policies_path)
        
        # Topic registry - synced with Qdrant
        self.topics: dict[str, TopicInfo] = {}
        
    def _load_policies(self, path: str) -> dict:
        with open(path) as f:
            return yaml.safe_load(f)
    
    async def initialize(self):
        """Initialize standing topics on startup."""
        # Load existing topics from Telegram
        existing = await self._fetch_existing_topics()
        
        # Create missing standing topics
        for topic_config in self.policies["standing_topics"]:
            key = topic_config["key"]
            if key not in existing:
                topic_id = await self._create_topic(
                    name=topic_config["name"],
                    icon_emoji=topic_config["name"].split()[0]  # First char is emoji
                )
                self.topics[key] = TopicInfo(
                    key=key,
                    topic_id=topic_id,
                    name=topic_config["name"],
                    created_at=datetime.utcnow(),
                    is_standing=True
                )
            else:
                self.topics[key] = existing[key]
        
        # Persist to knowledge base
        await self.knowledge.store_topic_registry(self.topics)
    
    async def route_message(
        self,
        alert: dict,
        assessment: dict
    ) -> tuple[int, bool]:
        """
        Determine which topic to route a message to.
        
        Returns:
            tuple: (topic_id, created_new_topic)
        """
        # Check if agent recommends dedicated topic
        if self._should_create_incident_topic(assessment):
            topic_id = await self.create_incident_topic(alert, assessment)
            return topic_id, True
        
        # Route to standing topic based on rules
        topic_key = self._match_routing_rules(alert, assessment)
        
        # Fallback to domain-based routing
        if not topic_key:
            topic_key = self._route_by_domain(assessment.get("domain"))
        
        # Final fallback to General
        if not topic_key or topic_key not in self.topics:
            topic_key = "general"
        
        return self.topics[topic_key].topic_id, False
    
    def _should_create_incident_topic(self, assessment: dict) -> bool:
        """Agent decides if incident warrants dedicated topic."""
        conditions = self.policies["dynamic_topics"]["incident"]["create_conditions"]
        
        for condition in conditions:
            for key, value in condition.items():
                if assessment.get(key) == value:
                    return True
        
        # Also check learned patterns from knowledge base
        return assessment.get("recommend_dedicated_topic", False)
    
    def _match_routing_rules(self, alert: dict, assessment: dict) -> Optional[str]:
        """Match alert against routing rules."""
        import re
        
        for rule in self.policies["routing_rules"]:
            match_all = True
            for field, pattern in rule["match"].items():
                value = alert.get(field) or assessment.get(field, "")
                if not re.match(pattern, str(value)):
                    match_all = False
                    break
            
            if match_all:
                return rule["route_to"]
        
        return None
    
    def _route_by_domain(self, domain: Optional[str]) -> Optional[str]:
        """Route based on domain to standing topic."""
        if not domain:
            return None
            
        for topic_config in self.policies["standing_topics"]:
            domains = topic_config.get("domains", [])
            if domain.lower() in [d.lower() for d in domains]:
                return topic_config["key"]
        
        return None
    
    async def create_incident_topic(
        self,
        alert: dict,
        assessment: dict
    ) -> int:
        """Create a dedicated topic for an incident."""
        incident_id = alert.get("id") or f"{datetime.utcnow():%Y%m%d%H%M%S}"
        title = alert.get("title") or alert.get("alertname", "Incident")
        
        template = self.policies["dynamic_topics"]["incident"]["name_template"]
        topic_name = template.format(title=title[:30], id=incident_id)
        
        topic_id = await self._create_topic(name=topic_name)
        
        # Register in knowledge base
        topic_info = TopicInfo(
            key=f"incident_{incident_id}",
            topic_id=topic_id,
            name=topic_name,
            created_at=datetime.utcnow(),
            is_standing=False,
            incident_id=incident_id
        )
        self.topics[topic_info.key] = topic_info
        
        await self.knowledge.store_incident_topic(
            incident_id=incident_id,
            topic_id=topic_id,
            alert=alert,
            assessment=assessment
        )
        
        # Notify in parent standing topic
        parent_topic = self._route_by_domain(assessment.get("domain")) or "infrastructure"
        await self.send_message(
            topic_key=parent_topic,
            text=f"⚠️ New incident spun off to dedicated topic: {topic_name}"
        )
        
        return topic_id
    
    async def resolve_incident(
        self,
        incident_id: str,
        resolution: dict
    ):
        """Close incident topic and archive to resolved."""
        topic_key = f"incident_{incident_id}"
        if topic_key not in self.topics:
            return
        
        topic = self.topics[topic_key]
        
        # Post resolution summary
        await self.send_message(
            topic_id=topic.topic_id,
            text=(
                f"✅ **Resolved**\n\n"
                f"{resolution['summary']}\n\n"
                f"**Runbook:** `{resolution.get('runbook_id', 'N/A')}`\n"
                f"**Duration:** {resolution.get('duration', 'N/A')}\n"
                f"**Root Cause:** {resolution.get('root_cause', 'N/A')}"
            )
        )
        
        # Close the topic
        await self.bot.close_forum_topic(
            chat_id=self.forum_chat_id,
            message_thread_id=topic.topic_id
        )
        
        # Archive to resolved topic
        await self.send_message(
            topic_key="resolved",
            text=(
                f"**Closed:** {topic.name}\n"
                f"Runbook: `{resolution.get('runbook_id', 'N/A')}`"
            )
        )
        
        # Update knowledge base
        await self.knowledge.record_incident_resolution(
            incident_id=incident_id,
            resolution=resolution
        )
    
    async def send_message(
        self,
        text: str,
        topic_key: Optional[str] = None,
        topic_id: Optional[int] = None,
        keyboard: Optional[InlineKeyboardMarkup] = None,
        parse_mode: str = ParseMode.MARKDOWN
    ) -> int:
        """Send message to a topic."""
        if topic_key and not topic_id:
            topic_id = self.topics.get(topic_key, {}).topic_id
        
        message = await self.bot.send_message(
            chat_id=self.forum_chat_id,
            message_thread_id=topic_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=keyboard
        )
        
        return message.message_id
    
    async def send_approval_request(
        self,
        topic_key: str,
        alert: dict,
        solutions: list[dict],
        context: dict
    ) -> int:
        """Send an approval request with inline keyboard."""
        # Build message
        text = (
            f"🔔 **{alert.get('title', alert.get('alertname', 'Alert'))}**\n\n"
            f"{alert.get('description', '')}\n\n"
        )
        
        if context.get("similar_runbook"):
            text += f"📚 Similar to: `{context['similar_runbook']}` ({context['similarity']}% match)\n\n"
        
        text += "**Solutions:**\n"
        for i, sol in enumerate(solutions, 1):
            text += f"\n{i}. **{sol['name']}**\n"
            text += f"   Impact: {sol['impact']}\n"
            text += f"   Risk: {sol['risk']}\n"
        
        # Build keyboard
        buttons = []
        row = []
        for i, sol in enumerate(solutions, 1):
            row.append(InlineKeyboardButton(
                f"{i}️⃣ {sol['name'][:15]}",
                callback_data=f"approve:{alert['id']}:{i}"
            ))
            if len(row) == 2:
                buttons.append(row)
                row = []
        
        if row:
            buttons.append(row)
        
        buttons.append([
            InlineKeyboardButton("❌ Ignore", callback_data=f"ignore:{alert['id']}"),
            InlineKeyboardButton("🔍 Details", callback_data=f"details:{alert['id']}")
        ])
        
        keyboard = InlineKeyboardMarkup(buttons)
        
        topic_id = self.topics[topic_key].topic_id
        return await self.send_message(
            topic_id=topic_id,
            text=text,
            keyboard=keyboard
        )
    
    async def cleanup_stale_topics(self):
        """Close topics that have been inactive."""
        retention_hours = self.policies["dynamic_topics"]["incident"]["auto_close_after_hours"]
        cutoff = datetime.utcnow() - timedelta(hours=retention_hours)
        
        for key, topic in list(self.topics.items()):
            if topic.is_standing:
                continue
            
            # Check last activity from knowledge base
            last_activity = await self.knowledge.get_topic_last_activity(topic.topic_id)
            
            if last_activity and last_activity < cutoff:
                await self.bot.close_forum_topic(
                    chat_id=self.forum_chat_id,
                    message_thread_id=topic.topic_id
                )
                
                await self.send_message(
                    topic_key="resolved",
                    text=f"**Auto-closed (stale):** {topic.name}"
                )
    
    async def _create_topic(
        self,
        name: str,
        icon_emoji: Optional[str] = None
    ) -> int:
        """Create a new forum topic."""
        result = await self.bot.create_forum_topic(
            chat_id=self.forum_chat_id,
            name=name,
            icon_custom_emoji_id=icon_emoji
        )
        return result.message_thread_id
    
    async def _fetch_existing_topics(self) -> dict[str, TopicInfo]:
        """Fetch existing topics from knowledge base."""
        return await self.knowledge.get_topic_registry()
```

---

## Part III: Webhook Handler

### FastAPI Webhook Service

```python
# src/telegram/webhook_handler.py
"""
Telegram Webhook Handler for Human-in-the-Loop Approvals.

Receives callbacks from inline keyboards and routes to LangGraph.
"""

from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.ext import Application
import structlog

from .topic_manager import TelegramTopicManager
from langgraph_router import LangGraphRouter

log = structlog.get_logger()

app = FastAPI(title="Telegram Webhook Handler")


class WebhookHandler:
    """Handles incoming Telegram updates."""
    
    def __init__(
        self,
        topic_manager: TelegramTopicManager,
        langgraph: LangGraphRouter
    ):
        self.topics = topic_manager
        self.langgraph = langgraph
    
    async def handle_update(self, update: Update):
        """Process incoming Telegram update."""
        
        # Handle callback queries (button presses)
        if update.callback_query:
            await self._handle_callback(update.callback_query)
            return
        
        # Handle text messages (custom commands)
        if update.message and update.message.text:
            await self._handle_message(update.message)
            return
    
    async def _handle_callback(self, callback):
        """Handle inline keyboard button press."""
        data = callback.data
        user = callback.from_user.username or callback.from_user.id
        
        log.info("callback_received", data=data, user=user)
        
        # Parse callback data: action:alert_id:option
        parts = data.split(":")
        action = parts[0]
        alert_id = parts[1] if len(parts) > 1 else None
        option = parts[2] if len(parts) > 2 else None
        
        # Acknowledge callback
        await callback.answer()
        
        if action == "approve":
            await self._handle_approval(callback, alert_id, int(option), user)
            
        elif action == "ignore":
            await self._handle_ignore(callback, alert_id, user)
            
        elif action == "details":
            await self._handle_details(callback, alert_id)
            
        elif action == "snooze":
            await self._handle_snooze(callback, alert_id, option)
    
    async def _handle_approval(self, callback, alert_id: str, option: int, user: str):
        """Process approval of a solution."""
        # Get alert context from knowledge base
        context = await self.langgraph.get_pending_approval(alert_id)
        
        if not context:
            await callback.message.reply_text("⚠️ Approval expired or already processed.")
            return
        
        selected_solution = context["solutions"][option - 1]
        
        # Update message to show selection
        await callback.message.edit_text(
            callback.message.text + f"\n\n✅ **Approved by @{user}:** Option {option}",
            reply_markup=None
        )
        
        # Execute via LangGraph
        result = await self.langgraph.execute_approved_action(
            alert_id=alert_id,
            solution=selected_solution,
            approved_by=user
        )
        
        # Post result
        if result["success"]:
            await callback.message.reply_text(
                f"✅ **Executed successfully**\n\n"
                f"{result['summary']}\n\n"
                f"📚 Runbook: `{result.get('runbook_id', 'pending')}`"
            )
        else:
            await callback.message.reply_text(
                f"❌ **Execution failed**\n\n"
                f"{result['error']}\n\n"
                f"Manual intervention may be required."
            )
    
    async def _handle_ignore(self, callback, alert_id: str, user: str):
        """Process ignore decision."""
        await callback.message.edit_text(
            callback.message.text + f"\n\n⏭️ **Ignored by @{user}**",
            reply_markup=None
        )
        
        # Record preference for learning
        await self.langgraph.record_ignore(
            alert_id=alert_id,
            ignored_by=user
        )
    
    async def _handle_details(self, callback, alert_id: str):
        """Show detailed information about alert."""
        details = await self.langgraph.get_alert_details(alert_id)
        
        await callback.message.reply_text(
            f"📊 **Details for Alert {alert_id}**\n\n"
            f"**Metrics:**\n{details['metrics']}\n\n"
            f"**Recent Events:**\n{details['events']}\n\n"
            f"**Related Runbooks:**\n{details['runbooks']}"
        )
    
    async def _handle_message(self, message):
        """Handle text message commands."""
        text = message.text.lower().strip()
        topic_id = message.message_thread_id
        
        # Custom command parsing
        if text.startswith("custom:"):
            custom_action = text[7:].strip()
            await self._execute_custom(message, custom_action)
            
        elif text == "status":
            await self._show_status(message)
            
        elif text == "weekly":
            await self._trigger_weekly_report(message)
            
        elif text.startswith("snooze"):
            # "snooze 2h" format
            duration = text.split()[-1] if len(text.split()) > 1 else "1h"
            await self._snooze_topic(message, topic_id, duration)
    
    async def _execute_custom(self, message, action: str):
        """Execute custom action via LangGraph."""
        result = await self.langgraph.execute_custom_action(
            action=action,
            requested_by=message.from_user.username,
            topic_id=message.message_thread_id
        )
        
        await message.reply_text(f"🔧 **Custom Action Result:**\n\n{result}")
    
    async def _show_status(self, message):
        """Show pending approvals and system status."""
        status = await self.langgraph.get_system_status()
        
        await message.reply_text(
            f"📊 **System Status**\n\n"
            f"**Pending Approvals:** {status['pending_count']}\n"
            f"**Auto-executed (24h):** {status['auto_executed']}\n"
            f"**Runbooks Active:** {status['active_runbooks']}\n"
            f"**Learning Queue:** {status['learning_queue']}"
        )


# FastAPI endpoint
@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """Receive Telegram webhook updates."""
    try:
        data = await request.json()
        update = Update.de_json(data, bot=None)
        
        handler = request.app.state.webhook_handler
        await handler.handle_update(update)
        
        return {"ok": True}
        
    except Exception as e:
        log.error("webhook_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "healthy"}
```

---

## Part IV: Kubernetes Deployment

### Deployment Manifest

```yaml
# k8s/telegram-service/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: telegram-service
  namespace: ai-platform
  labels:
    app: telegram-service
spec:
  replicas: 1
  strategy:
    type: Recreate  # Single instance for webhook consistency
  selector:
    matchLabels:
      app: telegram-service
  template:
    metadata:
      labels:
        app: telegram-service
    spec:
      containers:
      - name: telegram-service
        image: ghcr.io/yourusername/telegram-service:latest
        ports:
        - name: http
          containerPort: 8000
          protocol: TCP
        env:
        - name: TELEGRAM_BOT_TOKEN
          valueFrom:
            secretKeyRef:
              name: telegram-secrets
              key: TELEGRAM_BOT_TOKEN
        - name: TELEGRAM_FORUM_CHAT_ID
          valueFrom:
            secretKeyRef:
              name: telegram-secrets
              key: TELEGRAM_FORUM_CHAT_ID
        - name: WEBHOOK_URL
          value: "https://telegram-webhook.kernow.io/webhook/telegram"
        - name: LANGGRAPH_URL
          value: "http://langgraph.ai-platform.svc.cluster.local:8000"
        - name: KNOWLEDGE_MCP_URL
          value: "http://knowledge-mcp.ai-platform.svc.cluster.local:8001"
        volumeMounts:
        - name: config
          mountPath: /config
          readOnly: true
        resources:
          requests:
            cpu: 100m
            memory: 256Mi
          limits:
            cpu: 500m
            memory: 512Mi
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 10
      volumes:
      - name: config
        configMap:
          name: telegram-topic-policies
---
apiVersion: v1
kind: Service
metadata:
  name: telegram-service
  namespace: ai-platform
spec:
  selector:
    app: telegram-service
  ports:
  - name: http
    port: 8000
    targetPort: 8000
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: telegram-webhook
  namespace: ai-platform
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - telegram-webhook.kernow.io
    secretName: telegram-webhook-tls
  rules:
  - host: telegram-webhook.kernow.io
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: telegram-service
            port:
              number: 8000
```

### Init Job (Create Standing Topics)

```yaml
# k8s/telegram-service/init-job.yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: telegram-init-topics
  namespace: ai-platform
spec:
  template:
    spec:
      containers:
      - name: init
        image: ghcr.io/yourusername/telegram-service:latest
        command: ["python", "-m", "telegram.init_topics"]
        env:
        - name: TELEGRAM_BOT_TOKEN
          valueFrom:
            secretKeyRef:
              name: telegram-secrets
              key: TELEGRAM_BOT_TOKEN
        - name: TELEGRAM_FORUM_CHAT_ID
          valueFrom:
            secretKeyRef:
              name: telegram-secrets
              key: TELEGRAM_FORUM_CHAT_ID
        volumeMounts:
        - name: config
          mountPath: /config
      volumes:
      - name: config
        configMap:
          name: telegram-topic-policies
      restartPolicy: OnFailure
  backoffLimit: 3
```

---

## Part V: Message Commands Reference

### Inline Keyboard Actions

| Button | Callback Data | Action |
|--------|--------------|--------|
| `1️⃣ Option Name` | `approve:{alert_id}:1` | Execute solution 1 |
| `2️⃣ Option Name` | `approve:{alert_id}:2` | Execute solution 2 |
| `❌ Ignore` | `ignore:{alert_id}` | Skip, record preference |
| `🔍 Details` | `details:{alert_id}` | Show extended info |
| `⏰ Snooze` | `snooze:{alert_id}:{duration}` | Remind later |

### Text Commands

| Command | Description |
|---------|-------------|
| `status` | Show pending approvals and system health |
| `weekly` | Trigger weekly report immediately |
| `snooze 2h` | Snooze current topic for 2 hours |
| `custom: restart radarr` | Execute custom action via LangGraph |
| `approve PR 47` | Merge specific Renovate PR |

---

## Part VI: Learning Integration

### Routing Feedback Loop

```python
# The agent learns from human routing corrections

async def record_routing_feedback(
    alert_id: str,
    original_topic: str,
    corrected_topic: str,
    user: str
):
    """
    When human moves message to different topic,
    record this as routing feedback for learning.
    """
    await knowledge_mcp.store_routing_feedback({
        "alert_id": alert_id,
        "original_route": original_topic,
        "corrected_route": corrected_topic,
        "corrected_by": user,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # Trigger re-evaluation of routing rules
    await langgraph.evaluate_routing_rules()
```

### Topic Usage Metrics

```yaml
# Stored in Qdrant for analysis
topic_metrics:
  - topic_key: arr_suite
    messages_30d: 142
    approvals_30d: 89
    ignores_30d: 12
    avg_response_time_minutes: 4.2
    most_common_alerts:
      - OOMKilled
      - DiskPressure
      - UpdateAvailable
```

---

## Part VII: Migration Checklist

### From Signal to Telegram

- [ ] Create Telegram bot via @BotFather
- [ ] Store bot token in Infisical/SOPS
- [ ] Create Forum supergroup
- [ ] Add bot as admin with `can_manage_topics`
- [ ] Update `cloud-only-architecture-doc.md` references
- [ ] Update `unified-architecture.md` references  
- [ ] Update `routing-flow.mermaid` diagram
- [ ] Deploy Telegram service to cluster
- [ ] Run init job to create standing topics
- [ ] Configure webhook URL with Telegram API
- [ ] Test approval workflow end-to-end
- [ ] Remove Signal CLI references from codebase

### Webhook Registration

```bash
# Register webhook with Telegram
curl -X POST "https://api.telegram.org/bot${BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://telegram-webhook.kernow.io/webhook/telegram",
    "allowed_updates": ["message", "callback_query"],
    "drop_pending_updates": true
  }'
```

---

## Appendix: Updated Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DETECTION LAYER                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  Coroot          Prometheus        Renovate           Scheduled              │
│  Anomaly         Alerts            PRs                Queries                │
└──────────┬──────────────┬──────────────┬──────────────────┬──────────────────┘
           │              │              │                  │
           └──────────────┴──────────────┴──────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              TRIAGE LAYER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  LangGraph Router                                                            │
│  ├── Retrieve context from Qdrant                                           │
│  ├── Match existing runbooks                                                │
│  ├── Assess severity and complexity                                         │
│  └── Determine routing (topic + create dedicated?)                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         TELEGRAM FORUM LAYER                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  🏠 Homelab Ops Forum                                                        │
│  ├── 🔴 Critical Alerts ◄─── High severity routes here                       │
│  ├── 🟡 Arr Suite ◄───────── Domain: sonarr, radarr, etc.                    │
│  ├── 🔵 Infrastructure ◄──── Domain: k8s, argocd, storage                    │
│  ├── 🏠 Home Assistant ◄──── Domain: HA, tasmota, mqtt                       │
│  ├── 📊 Weekly Reports ◄──── Scheduled digests                               │
│  ├── 🔧 Incident #47 ◄────── Dynamic: complex incidents                      │
│  └── ✅ Resolved ◄─────────── Archive of closed items                        │
│                                                                              │
│  Message Format:                                                             │
│  ┌─────────────────────────────────────────┐                                │
│  │ 🔔 Radarr Memory at 95%                 │                                │
│  │                                         │                                │
│  │ Similar to: runbook-mem-001 (89%)       │                                │
│  │                                         │                                │
│  │ [1️⃣ Increase] [2️⃣ Restart]              │                                │
│  │ [❌ Ignore]   [🔍 Details]              │                                │
│  └─────────────────────────────────────────┘                                │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ Callback: approve:alert123:1
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            EXECUTION LAYER                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  LangGraph → MCP Tools → Infrastructure                                      │
│  ├── infrastructure-mcp: kubectl, ArgoCD                                    │
│  ├── arr-suite-mcp: Sonarr, Radarr APIs                                     │
│  ├── home-assistant-mcp: HA API                                             │
│  └── knowledge-mcp: Store result, update runbook                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             LEARNING LAYER                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  Record outcome → Update runbook → Track success rate → Promote to auto     │
└─────────────────────────────────────────────────────────────────────────────┘
```
