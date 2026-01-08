# Fabric Patterns

Structured prompts for the Agentic AI Platform.

## Overview

Fabric patterns are reusable prompt templates that guide the AI agent through specific tasks. They provide:
- Consistent structure for common operations
- Domain-specific context
- Expected output formats
- Safety guardrails

## Available Patterns

| Pattern | Description | Use Case |
|---------|-------------|----------|
| `investigate_alert.md` | Structured alert investigation | When AlertManager triggers |
| `health_check.md` | Comprehensive infrastructure health check | Scheduled daily checks |
| `deploy_application.md` | GitOps-compliant application deployment | New app deployments |
| `incident_response.md` | Production incident handling | Critical/high severity alerts |

## Usage

Patterns are loaded by the LangGraph orchestrator and injected into prompts:

```python
pattern = load_pattern("investigate_alert")
prompt = pattern.format(
    alertname=alert["alertname"],
    severity=alert["severity"],
    namespace=alert["namespace"],
    description=alert["description"]
)
```

## Creating New Patterns

1. Create a new `.md` file in `/fabric/patterns/`
2. Include:
   - Clear title and purpose
   - Context section with placeholders
   - Step-by-step instructions
   - Expected output format (JSON preferred)
3. Test with the orchestrator

## Pattern Variables

Use `{variable_name}` for dynamic values:
- `{alertname}` - Alert name
- `{severity}` - Alert severity
- `{namespace}` - Kubernetes namespace
- `{description}` - Alert description
- `{cluster}` - Target cluster (prod/monit/agentic)

## Storage

Patterns can be stored in:
- Filesystem (this directory) - for development
- Qdrant `documentation` collection - for production
- ConfigMap - for K8s deployment
