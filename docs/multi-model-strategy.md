# Multi-Model Integration Strategy

**Purpose**: Leverage Gemini Flash, Ollama, and Claude strategically to maximize capability while minimizing cost.

---

## Model Tiers

| Tier | Model | Cost | Context | Access Method |
|------|-------|------|---------|---------------|
| **1 (Free/Local)** | Ollama qwen2.5:7b | $0 | 32K | LiteLLM proxy |
| **2 (Free/Large)** | Gemini 2.0 Flash | $0* | 1M | LiteLLM proxy |
| **3 (Subscription)** | Claude Max | $20/mo flat | 200K | claude-agent service |

*Free tier has rate limits

**IMPORTANT**: Tier 3 uses Claude Max subscription via `claude-agent` service, NOT the Anthropic API. This provides unlimited Claude usage for a flat monthly fee instead of per-token costs. (15 RPM, 1M TPM)

---

## Task → Model Routing Matrix

### Tier 1: Ollama (Always Available, Zero Cost)

| Task | Why Ollama |
|------|------------|
| Alert severity classification | Simple pattern matching |
| Entity extraction from logs | Structured output, fast |
| Yes/no decisions | Binary classification |
| Local embeddings | When Gemini rate limited |
| Summarization of small texts | Under 8K tokens |
| Pre-filtering before LLM calls | Reduce expensive calls |

**Model name in LiteLLM**: `ollama-qwen`, `tier1`

### Tier 2: Gemini Flash (Primary Workhorse)

| Task | Why Gemini |
|------|------------|
| Alert analysis with full context | 1M token context window |
| Log aggregation (last 24h) | Large input capacity |
| Runbook selection (RAG) | Fast semantic reasoning |
| Daily summaries | Batch processing, free |
| Documentation generation | Good for structured content |
| Entity enrichment | Network context synthesis |
| Incident timeline reconstruction | Large log correlation |

**Model name in LiteLLM**: `gemini/gemini-2.0-flash`, `tier2`, `gemini-pro`

### Tier 3: Claude (Subscription via claude-agent)

| Task | Why Claude |
|------|------------|
| Code generation | Superior code quality |
| Security analysis | Better at edge cases |
| MCP server generation | Complex architecture |
| Skill generation | Nuanced understanding |
| Validation/review | Catches subtle issues |
| Architectural decisions | Strategic reasoning |
| Human-facing explanations | Better communication |

**Access**: HTTP POST to `http://claude-agent:8000/agent/run` or `/queue/submit`

```python
# Direct execution
response = await client.post(
    "http://claude-agent:8000/agent/run",
    json={"prompt": prompt, "tools": tools}
)

# Priority queue (for batch/background tasks)
response = await client.post(
    "http://claude-agent:8000/queue/submit",
    json={"prompt": prompt, "priority": "normal"}
)
```

---

## Implementation

### 1. Two Access Paths

The system uses two distinct paths for LLM access:

```
┌─────────────────────────────────────────────────────────┐
│                    LiteLLM Proxy                        │
│  http://litellm:4000/v1/chat/completions               │
│  Models: tier1 (Ollama), tier2 (Gemini), embeddings    │
└─────────────────────────────────────────────────────────┘
                           │
        ┌──────────────────┴──────────────────┐
        ▼                                      ▼
   ┌─────────┐                          ┌─────────────┐
   │ Ollama  │                          │   Gemini    │
   │ (local) │                          │ (free tier) │
   └─────────┘                          └─────────────┘

┌─────────────────────────────────────────────────────────┐
│                  claude-agent Service                    │
│  http://claude-agent:8000/agent/run                     │
│  http://claude-agent:8000/queue/submit                  │
│  Uses: Claude Max subscription (flat $20/mo)            │
└─────────────────────────────────────────────────────────┘
```

### 2. LiteLLM Model Aliases (Tier 1 & 2)

```yaml
model_list:
  # Tier 1: Local (always available, $0)
  - model_name: tier1
    litellm_params:
      model: ollama/qwen2.5:7b
      api_base: http://ollama:11434

  # Tier 2: Gemini (free tier)
  - model_name: tier2
    litellm_params:
      model: gemini/gemini-2.0-flash
      api_key: os.environ/GEMINI_API_KEY

  # Embeddings (with local fallback)
  - model_name: embeddings
    litellm_params:
      model: gemini/text-embedding-004
  - model_name: embeddings-local
    litellm_params:
      model: ollama/nomic-embed-text
```

### 3. Service Integration Patterns

#### Pattern A: Pre-filter with Ollama, Premium to Claude

```python
async def smart_route(alert):
    # Quick classification with Ollama (tier1)
    severity = await call_litellm(
        model="tier1",
        prompt=f"Classify: {alert['name']}\nResponse: critical/warning/info"
    )

    if severity == "critical":
        # Full analysis with Claude subscription
        return await call_claude_agent(build_full_prompt(alert))
    else:
        # Gemini for non-critical (tier2)
        return await call_litellm(model="tier2", prompt=build_prompt(alert))
```

#### Pattern B: Task-Based Routing

```python
async def route_by_task(task_type: str, prompt: str):
    if task_type in ["classify", "extract", "filter", "summarize"]:
        # Simple tasks → Ollama
        return await call_litellm(model="tier1", prompt=prompt)

    elif task_type in ["analyze", "search", "aggregate"]:
        # Analysis tasks → Gemini (1M context)
        return await call_litellm(model="tier2", prompt=prompt)

    elif task_type in ["validate", "generate_code", "security", "generate_mcp"]:
        # Premium tasks → Claude subscription
        return await call_claude_agent(prompt)

    return await call_litellm(model="tier2", prompt=prompt)  # Default
```

#### Pattern C: Helper Functions

```python
import httpx

LITELLM_URL = "http://litellm:4000"
CLAUDE_AGENT_URL = "http://claude-agent:8000"

async def call_litellm(model: str, prompt: str) -> str:
    """Call Ollama or Gemini via LiteLLM proxy."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{LITELLM_URL}/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}]
            }
        )
        return response.json()["choices"][0]["message"]["content"]

async def call_claude_agent(prompt: str, priority: str = "normal") -> str:
    """Call Claude via subscription (claude-agent service)."""
    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.post(
            f"{CLAUDE_AGENT_URL}/agent/run",
            json={"prompt": prompt, "priority": priority}
        )
        return response.json()["result"]
```

---

## Integration Points

### alerting-pipeline

```python
# Current: Uses Gemini for everything
# Proposed: Tier-based routing

async def triage_alert(alert):
    # Step 1: Quick severity check with Ollama (free, fast)
    severity = await call_litellm(model="tier1", prompt=classify_prompt)

    # Step 2: Full analysis
    if severity == "critical":
        # Claude subscription for critical alerts
        analysis = await call_claude_agent(build_full_prompt(alert))
    else:
        # Gemini for non-critical (free tier)
        analysis = await call_litellm(model="tier2", prompt=build_prompt(alert))

    return analysis
```

### claude-validator (v2.0)

Already uses the correct pattern:
- Calls `claude-agent` service for all validation
- Uses subscription, not API

```python
# From claude-validator configmap.yaml
async with httpx.AsyncClient() as client:
    response = await client.post(
        f"{CLAUDE_AGENT_URL}/agent/run",
        json={"prompt": prompt, "tools": TOOLS_VALIDATION}
    )
```

Could be enhanced with pre-filtering:
```python
async def validate(content, type):
    # Quick pre-check with Ollama (free)
    has_issues = await call_litellm(model="tier1", prompt=quick_scan_prompt)

    if not has_issues:
        return {"valid": True, "model": "ollama", "cost": "$0"}

    # Deep validation with Claude subscription
    return await call_claude_agent(full_validation_prompt)
```

### LangGraph Orchestrator

```python
# Node-specific routing
NODE_ROUTING = {
    # Tier 1: Ollama (via LiteLLM)
    "classify_alert": "tier1",
    "extract_entities": "tier1",
    "summarize": "tier1",

    # Tier 2: Gemini (via LiteLLM)
    "search_runbooks": "tier2",
    "analyze_context": "tier2",
    "aggregate_logs": "tier2",

    # Tier 3: Claude (via claude-agent)
    "generate_action": "claude-agent",
    "validate_action": "claude-agent",
    "generate_runbook": "claude-agent",
}
```

---

## Gemini Free Tier Limits

| Limit | Value | Strategy |
|-------|-------|----------|
| RPM | 15 requests/min | Batch requests, use cache |
| TPM | 1M tokens/min | Usually sufficient |
| RPD | 1,500 requests/day | ~1 request/minute average |

**When rate limited**: Automatic fallback to Ollama via LiteLLM router.

---

## Cost Optimization

### Current State
- Gemini Flash (free): 100% of LLM calls via LiteLLM
- Claude (subscription): Via claude-agent ($20/mo flat)

### Proposed State
- Tier 1 (Ollama): 40% of calls (classification, filtering) - **$0**
- Tier 2 (Gemini): 50% of calls (analysis, summaries) - **$0**
- Tier 3 (Claude): 10% of calls (validation, generation) - **$20/mo flat**

### Monthly Cost Breakdown

| Model | Usage | Cost |
|-------|-------|------|
| Ollama | Unlimited local | $0 |
| Gemini Flash | Free tier (1500 RPD) | $0 |
| Claude Max | Subscription | $20/mo |
| **Total** | | **$20/mo** |

vs. API pricing for equivalent usage:
- Claude API: ~$50-200/mo depending on volume
- Gemini API (paid tier): ~$20-50/mo

### Optimization Tactics
- Pre-filter with Ollama before Claude calls
- Use Gemini's 1M context for large aggregations
- Batch Claude requests via priority queue
- Local embeddings when Gemini rate limited

---

## Implementation Roadmap

### Phase 1: LiteLLM Tier Aliases ✅ (Done)
- Added tier1/tier2 aliases to LiteLLM config
- Ollama fallback on Gemini rate limits
- Local embeddings available

### Phase 2: Update alerting-pipeline
- Add severity pre-classification with Ollama (tier1)
- Route critical alerts to claude-agent
- Route non-critical to Gemini (tier2)

### Phase 3: Enhance claude-validator
- Add quick pre-scan with Ollama (tier1)
- Only run Claude validation when issues detected
- Already uses claude-agent (correct pattern)

### Phase 4: Update LangGraph
- Define NODE_ROUTING mapping
- Implement per-node model/service selection
- Add metrics for routing decisions

---

## Monitoring

### LiteLLM Usage (Tier 1 & 2)
```bash
# Check model usage
kubectl logs -n ai-platform deploy/litellm | jq -r '.model' | sort | uniq -c

# Track fallbacks
kubectl logs -n ai-platform deploy/litellm | grep "fallback"
```

### claude-agent Usage (Tier 3)
```bash
# Check queue depth
curl http://10.20.0.40:31095/queue/status

# Check recent tasks
kubectl logs -n ai-platform deploy/claude-agent --tail=100 | grep "task"
```

### Metrics to Track
- Requests per tier (tier1, tier2, claude-agent)
- Latency per tier
- Gemini rate limit hits / fallbacks
- Claude queue depth and wait time

---

## Summary

| Tier | Backend | Access | Cost | Use For |
|------|---------|--------|------|---------|
| 1 | Ollama | LiteLLM `tier1` | $0 | Classify, filter, extract |
| 2 | Gemini | LiteLLM `tier2` | $0 | Analyze, aggregate, search |
| 3 | Claude | claude-agent | $20/mo | Validate, generate, complex |

**Key Insight**: By using Claude Max subscription instead of API, and pre-filtering with free tiers, the ecosystem gets premium AI capabilities for a fixed $20/month regardless of volume.

---

*Strategy documented 2026-01-15 by Claude Code*
