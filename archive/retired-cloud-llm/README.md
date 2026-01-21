# Retired Cloud LLM Infrastructure

**Retired Date**: 2026-01-21
**Reason**: Migration to local Ollama + LangGraph architecture

## What Was Retired

| Component | Description | Replacement |
|-----------|-------------|-------------|
| `claude-agent` | Claude API-based alert responder | LangGraph + Ollama (qwen2.5:7b) |
| `claude-validator` | Claude-based output validation | Ollama self-validation in LangGraph |
| `claude-refresh` | OAuth token refresh service | Not needed (Claude Code uses different auth) |
| `gemini-agent` | Gemini API-based workhorse agent | LangGraph + Ollama |

## CronJobs Removed

- `claude-token-monitor` - Monitored token expiry, no longer needed
- `claude-validator-daily` - Daily validation runs, now handled by LangGraph

## New Architecture

```
Alerts → Keep → LangGraph → Ollama (qwen2.5:7b) → MCP Tools → Resolution
                    ↓
              OpenWebUI (manual fallback)
```

## Secrets Cleaned Up

The following secrets can be removed from Infisical:
- `/agentic-platform/gemini/GEMINI_API_KEY`
- `/agentic-platform/claude/CREDENTIALS_JSON_B64`
- Any OPENROUTER_API_KEY references

## Preserved Components

- `litellm` - Still routes to Ollama, useful abstraction layer
- `openwebui` - Manual chat interface for Ollama

## Restoration

If needed, these files can be restored from this archive directory.
The ArgoCD application manifests are also preserved here.
