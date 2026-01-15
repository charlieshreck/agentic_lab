# Multi-Model Integration Strategy

**Purpose**: Leverage Gemini Flash, Ollama, and Claude strategically to maximize capability while minimizing cost.

---

## Model Tiers

| Tier | Model | Cost | Context | Best For |
|------|-------|------|---------|----------|
| **1 (Free/Local)** | Ollama qwen2.5:7b | $0 | 32K | Simple tasks, fallback |
| **2 (Free/Large)** | Gemini 2.0 Flash | $0* | 1M | Broad context, analysis |
| **3 (Premium)** | Claude Opus/Sonnet | $$ | 200K | Complex reasoning, code |

*Free tier has rate limits (15 RPM, 1M TPM)

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

### Tier 3: Claude (Premium Tasks)

| Task | Why Claude |
|------|------------|
| Code generation | Superior code quality |
| Security analysis | Better at edge cases |
| MCP server generation | Complex architecture |
| Skill generation | Nuanced understanding |
| Validation/review | Catches subtle issues |
| Architectural decisions | Strategic reasoning |
| Human-facing explanations | Better communication |

**Model name in LiteLLM**: `claude-sonnet`, `claude-opus`, `tier3`

---

## Implementation

### 1. LiteLLM Model Aliases

Add tiered aliases to LiteLLM config:

```yaml
model_list:
  # Tier 1: Local (always available)
  - model_name: tier1
    litellm_params:
      model: ollama/qwen2.5:7b
      api_base: http://ollama:11434

  # Tier 2: Gemini (free tier primary)
  - model_name: tier2
    litellm_params:
      model: gemini/gemini-2.0-flash
      api_key: os.environ/GEMINI_API_KEY

  # Tier 3: Claude (premium)
  - model_name: tier3
    litellm_params:
      model: anthropic/claude-3-5-sonnet-20241022
      api_key: os.environ/ANTHROPIC_API_KEY

  # Aliases for explicit model selection
  - model_name: embeddings-local
    litellm_params:
      model: ollama/nomic-embed-text
      api_base: http://ollama:11434
```

### 2. Service Integration Patterns

#### Pattern A: Pre-filter with Ollama

```python
# Use Ollama to classify, then route accordingly
async def smart_route(alert):
    # Quick classification with Ollama
    severity = await call_model(
        "tier1",
        f"Classify severity: {alert['name']}\nResponse: critical/warning/info"
    )

    if severity == "critical":
        # Full analysis with Claude for critical
        return await call_model("tier3", build_full_prompt(alert))
    else:
        # Gemini for non-critical
        return await call_model("tier2", build_full_prompt(alert))
```

#### Pattern B: Context-Aware Selection

```python
# Select model based on input size and task type
async def select_model(task_type: str, input_tokens: int) -> str:
    if task_type in ["classify", "extract", "filter"]:
        return "tier1"  # Ollama for simple tasks

    if input_tokens > 100_000:
        return "tier2"  # Gemini for large context

    if task_type in ["generate_code", "validate", "security"]:
        return "tier3"  # Claude for premium tasks

    return "tier2"  # Default to Gemini
```

#### Pattern C: Fallback Chain

```python
# Try premium first, fall back on rate limits
async def with_fallback(prompt, preferred="tier3"):
    try:
        return await call_model(preferred, prompt)
    except RateLimitError:
        if preferred == "tier3":
            return await call_model("tier2", prompt)
        return await call_model("tier1", prompt)
```

---

## Integration Points

### alerting-pipeline

```python
# Current: Uses Gemini for everything
# Proposed: Tier-based routing

async def triage_alert(alert):
    # Step 1: Quick severity check with Ollama
    severity = await quick_classify(alert, model="tier1")

    # Step 2: Full analysis with appropriate tier
    if severity == "critical":
        analysis = await analyze(alert, model="tier3")  # Claude
    else:
        analysis = await analyze(alert, model="tier2")  # Gemini

    return analysis
```

### claude-validator

```python
# Current: Uses Claude for all validation
# Proposed: Tiered validation

async def validate(content, type):
    # Quick pre-check with Ollama
    has_issues = await quick_scan(content, model="tier1")

    if not has_issues:
        return {"valid": True, "model": "tier1"}

    # Deep validation with Claude
    return await full_validate(content, model="tier3")
```

### LangGraph Orchestrator

```python
# Current: Single model for all nodes
# Proposed: Node-specific model selection

NODE_MODELS = {
    "classify_alert": "tier1",
    "search_runbooks": "tier2",
    "analyze_context": "tier2",
    "generate_action": "tier3",
    "validate_action": "tier3",
    "summarize": "tier1",
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
- Gemini Flash (free): 100% of LLM calls
- Claude (paid): Only via claude-agent/validator

### Proposed State
- Tier 1 (Ollama): 40% of calls (classification, filtering)
- Tier 2 (Gemini): 50% of calls (analysis, summaries)
- Tier 3 (Claude): 10% of calls (validation, generation)

### Monthly Savings
- Reduce Claude calls by pre-filtering: ~60-70% cost reduction
- Use Ollama for embeddings: ~$0 vs Gemini embedding costs
- Batch Gemini requests: Stay within free tier

---

## Implementation Roadmap

### Phase 1: Add Model Aliases (Now)
- Update LiteLLM config with tier1/tier2/tier3 aliases
- No service changes needed, just config

### Phase 2: Update alerting-pipeline
- Add severity pre-classification with Ollama
- Route critical alerts to Claude, others to Gemini

### Phase 3: Update claude-validator
- Add quick pre-scan with Ollama
- Only run Claude validation when issues detected

### Phase 4: Update LangGraph
- Define NODE_MODELS mapping
- Implement per-node model selection

---

## Monitoring

Track model usage via LiteLLM audit logs:

```bash
# Check which models are being used
kubectl logs -n ai-platform deploy/litellm | jq '.model'

# Count by tier
kubectl logs -n ai-platform deploy/litellm | jq -r '.model' | sort | uniq -c
```

Dashboard metrics to add:
- Requests per model tier
- Average latency per tier
- Fallback rate (Gemini → Ollama)
- Cost per tier (when Claude added)

---

## Next Steps

1. **Update LiteLLM config** - Add tier aliases
2. **Test tier routing** - Manual tests with curl
3. **Update alerting-pipeline** - Add pre-classification
4. **Document patterns** - Add to CLAUDE.md

---

*Strategy documented 2026-01-15 by Claude Code*
