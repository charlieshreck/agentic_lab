# architecture-diagram.mermaid - HITL Section Update

## Find and Replace this section in your existing file:

### OLD (Signal):
```mermaid
    subgraph HITL["👤 HUMAN-IN-THE-LOOP LAYER"]
        COROOT["Coroot<br/>Anomaly Detection"]
        TRIAGE["Local LLM Triage<br/>Is this a problem?"]
        NOTIFY["Notification Service<br/>Signal/Mattermost"]
        APPROVAL["Approval Handler<br/>Parse responses"]
        RUNBOOK_DB["Runbook Database<br/>Learned fixes"]
        WEEKLY["Weekly Reports<br/>What I did/learned"]
    end
```

### NEW (Telegram Forum):
```mermaid
    subgraph HITL["👤 HUMAN-IN-THE-LOOP LAYER"]
        COROOT["Coroot<br/>Anomaly Detection"]
        TRIAGE["Hybrid Triage<br/>Local → Cloud escalation"]
        TELEGRAM["Telegram Forum<br/>Topic-based routing"]
        TOPICS["Standing Topics<br/>🔴🟡🔵🏠📊✅"]
        CALLBACK["Callback Handler<br/>Inline Keyboards"]
        RUNBOOK_DB["Runbook Database<br/>Learned fixes"]
        WEEKLY["Weekly Reports<br/>📊 Topic"]
    end
```

---

## Full HITL Subgraph with Connections

If you need the complete subgraph with all connections, use this:

```mermaid
    subgraph HITL["👤 HUMAN-IN-THE-LOOP LAYER"]
        direction TB
        COROOT["Coroot<br/>Anomaly Detection"]
        TRIAGE["Hybrid Triage<br/>Local-first + Cloud"]
        
        subgraph TELEGRAM_FORUM["📱 Telegram Forum"]
            FORUM["🏠 Homelab Ops"]
            CRITICAL["🔴 Critical"]
            ARR["🟡 Arr Suite"]
            INFRA["🔵 Infrastructure"]
            HA["🏠 Home Assistant"]
            REPORTS["📊 Reports"]
            RESOLVED["✅ Resolved"]
        end
        
        CALLBACK["Callback Handler<br/>Inline Keyboards"]
        RUNBOOK_DB["Runbook Database<br/>Qdrant vectors"]
        WEEKLY["Weekly Digest<br/>Learning summary"]
    end

    %% HITL Connections
    COROOT --> TRIAGE
    TRIAGE --> TELEGRAM_FORUM
    TELEGRAM_FORUM --> CALLBACK
    CALLBACK --> RUNBOOK_DB
    RUNBOOK_DB --> TRIAGE
    WEEKLY --> REPORTS
```

---

## Updated Connections to HITL

Also update any references connecting TO the HITL layer:

### OLD:
```mermaid
    NOTIFY["Notification Service<br/>Signal/Mattermost"]
    %% ...
    LANGGRAPH --> NOTIFY
    NOTIFY --> APPROVAL
```

### NEW:
```mermaid
    TELEGRAM["Telegram Service<br/>Forum + Webhooks"]
    %% ...
    LANGGRAPH --> TELEGRAM
    TELEGRAM --> CALLBACK
```
