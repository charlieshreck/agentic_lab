# Cloud-Only Architecture Doc - UPDATED SECTIONS
## Replace these sections in your existing cloud-only-architecture-doc.md

---

## SECTION: Executive Summary (Replace Key Characteristics bullet)

**OLD:**
```markdown
- **Human approval workflow** - Signal/Mattermost notifications with chat-based approval
```

**NEW:**
```markdown
- **Human approval workflow** - Telegram Forum with topic-based organization and inline keyboard approvals
```

---

## SECTION: Part III - Human-in-the-Loop Framework (Replace entire section)

### The Approval Loop

```
Detection (Coroot/Prometheus/Renovate)
         │
         ▼
┌─────────────────────────────────────────────────────────────────┐
│  🏠 Homelab Ops Forum                                            │
│  ├── 🔴 Critical Alerts                                          │
│  ├── 🟡 Arr Suite  ◄── Alert routed here based on domain        │
│  │   ┌─────────────────────────────────────────────────────────┐│
│  │   │ 🔔 Radarr memory at 95%                                 ││
│  │   │                                                          ││
│  │   │ Similar to: runbook-mem-001 (89%)                       ││
│  │   │ Last time: memory increase worked                        ││
│  │   │                                                          ││
│  │   │ [1️⃣ Increase Memory] [