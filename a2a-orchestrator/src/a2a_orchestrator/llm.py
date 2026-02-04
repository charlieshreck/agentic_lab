"""LLM Client - Gemini via OpenRouter for specialist analysis."""

import os
import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# OpenRouter API for Gemini access
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Model selection
SPECIALIST_MODEL = os.environ.get("SPECIALIST_MODEL", "google/gemini-2.0-flash-001")
SYNTHESIS_MODEL = os.environ.get("SYNTHESIS_MODEL", "google/gemini-2.0-flash-001")


async def gemini_analyze(
    system_prompt: str,
    alert: Any,
    evidence: str,
    model: str = None
) -> dict:
    """Analyze alert with Gemini via OpenRouter.

    Args:
        system_prompt: Specialist system prompt
        alert: Alert object with name, labels, severity
        evidence: Evidence gathered from MCP tools
        model: Model to use (default: SPECIALIST_MODEL)

    Returns:
        Dict with status, issue, recommendation
    """
    if not OPENROUTER_API_KEY:
        logger.warning("No OpenRouter API key, returning default analysis")
        return {
            "status": "WARN",
            "issue": f"Alert: {alert.name}",
            "recommendation": "Manual investigation required"
        }

    model = model or SPECIALIST_MODEL

    # Build user message
    alert_info = f"""
Alert: {alert.name}
Severity: {alert.severity}
Labels: {json.dumps(dict(alert.labels) if hasattr(alert.labels, '__dict__') else alert.labels, default=str)}
Description: {alert.description or 'N/A'}
"""

    user_message = f"""
{alert_info}

Evidence from investigation:
{evidence}

Analyze this alert and provide your assessment.
"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://kernow.io",
                    "X-Title": "A2A Orchestrator"
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    "response_format": {"type": "json_object"},
                    "max_tokens": 500,
                    "temperature": 0.3
                }
            )

            if response.status_code == 429:
                logger.warning("OpenRouter rate limited")
                raise Exception("Rate limited")

            response.raise_for_status()
            result = response.json()

            # Extract content
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "{}")

            # Parse JSON response
            try:
                analysis = json.loads(content)
                return {
                    "status": analysis.get("status", "WARN"),
                    "issue": analysis.get("issue", "Unknown"),
                    "recommendation": analysis.get("recommendation")
                }
            except json.JSONDecodeError:
                # If not valid JSON, extract key info
                return {
                    "status": "WARN",
                    "issue": content[:200],
                    "recommendation": None
                }

    except httpx.HTTPError as e:
        logger.error(f"Gemini API error: {e}")
        raise
    except Exception as e:
        logger.error(f"Gemini analysis failed: {e}")
        raise


def _get_attr(finding, attr_name: str, default=None):
    """Get attribute from finding, supporting both old Finding and new SpecialistFinding.

    Attribute mappings:
    - agent/specialist: The specialist name
    - issue/summary: The finding description
    - recommendation: Only in old Finding (returns None for SpecialistFinding)
    - evidence: str in old Finding, List[str] in SpecialistFinding
    """
    attr_map = {
        "agent": ["agent", "specialist"],
        "specialist": ["specialist", "agent"],
        "issue": ["issue", "summary"],
        "summary": ["summary", "issue"],
        "recommendation": ["recommendation"],
    }

    attrs_to_try = attr_map.get(attr_name, [attr_name])

    for attr in attrs_to_try:
        if hasattr(finding, attr):
            value = getattr(finding, attr, None)
            if value is not None:
                return value

    return default


def _get_evidence(finding) -> str:
    """Get evidence as string, handling both str and List[str] types."""
    evidence = getattr(finding, "evidence", None)
    if evidence is None:
        return ""
    if isinstance(evidence, list):
        return "; ".join(str(e) for e in evidence[:3])
    return str(evidence)


async def gemini_synthesize(
    findings: list,
    alert: Any,
    domain_weights: dict
) -> dict:
    """Synthesize findings from multiple specialists.

    Args:
        findings: List of Finding or SpecialistFinding objects from specialists
        alert: Original alert
        domain_weights: Weight per domain for prioritization

    Returns:
        Dict with verdict, confidence, synthesis, suggested_action
    """
    if not OPENROUTER_API_KEY:
        # Simple rule-based synthesis without LLM
        fail_count = sum(1 for f in findings if getattr(f, "status", "PASS") == "FAIL")
        warn_count = sum(1 for f in findings if getattr(f, "status", "PASS") == "WARN")

        if fail_count > 0:
            verdict = "ACTIONABLE"
            confidence = 0.7 + (fail_count * 0.1)
        elif warn_count > 0:
            verdict = "UNKNOWN"
            confidence = 0.5
        else:
            verdict = "FALSE_POSITIVE"
            confidence = 0.6

        issues = [_get_attr(f, "issue") for f in findings if _get_attr(f, "issue")]
        recommendations = [_get_attr(f, "recommendation") for f in findings if _get_attr(f, "recommendation")]

        return {
            "verdict": verdict,
            "confidence": min(confidence, 0.95),
            "synthesis": "; ".join(issues[:3]) if issues else "No significant issues found",
            "suggested_action": recommendations[0] if recommendations else None
        }

    # Build synthesis prompt
    system_prompt = """You are synthesizing findings from multiple specialist agents.

Weight the findings by domain authority (security > devops > sre > network > database).
Determine the overall verdict and recommended action.

Output JSON with:
- verdict: ACTIONABLE (needs fix), UNKNOWN (needs investigation), FALSE_POSITIVE (no action)
- confidence: 0.0-1.0
- synthesis: Brief explanation of the root cause
- suggested_action: Specific command or action to take (if actionable)
"""

    def format_finding(f):
        agent = _get_attr(f, "agent", "unknown")
        status = getattr(f, "status", "UNKNOWN")
        issue = _get_attr(f, "issue", "None")
        evidence = _get_evidence(f)[:200] or "None"
        recommendation = _get_attr(f, "recommendation", "None")
        weight = domain_weights.get(agent, 0.5)

        return (
            f"**{agent.upper()}** (weight: {weight}):\n"
            f"Status: {status}\n"
            f"Issue: {issue}\n"
            f"Evidence: {evidence}\n"
            f"Recommendation: {recommendation}"
        )

    findings_text = "\n\n".join([format_finding(f) for f in findings])

    user_message = f"""
Alert: {alert.name} ({alert.severity})

Specialist findings:
{findings_text}

Synthesize these findings into a final verdict and action.
"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://kernow.io",
                    "X-Title": "A2A Orchestrator"
                },
                json={
                    "model": SYNTHESIS_MODEL,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    "response_format": {"type": "json_object"},
                    "max_tokens": 500,
                    "temperature": 0.2
                }
            )

            response.raise_for_status()
            result = response.json()

            content = result.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            synthesis = json.loads(content)

            return {
                "verdict": synthesis.get("verdict", "UNKNOWN"),
                "confidence": float(synthesis.get("confidence", 0.5)),
                "synthesis": synthesis.get("synthesis", "Analysis complete"),
                "suggested_action": synthesis.get("suggested_action")
            }

    except Exception as e:
        logger.error(f"Synthesis failed, using rule-based: {e}")
        # Fallback to rule-based synthesis
        fail_count = sum(1 for f in findings if getattr(f, "status", "PASS") == "FAIL")
        warn_count = sum(1 for f in findings if getattr(f, "status", "PASS") == "WARN")

        if fail_count > 0:
            verdict = "ACTIONABLE"
            confidence = 0.7 + (fail_count * 0.1)
        elif warn_count > 0:
            verdict = "UNKNOWN"
            confidence = 0.5
        else:
            verdict = "FALSE_POSITIVE"
            confidence = 0.6

        issues = [_get_attr(f, "issue") for f in findings if _get_attr(f, "issue")]

        return {
            "verdict": verdict,
            "confidence": min(confidence, 0.95),
            "synthesis": "; ".join(issues[:3]) if issues else "No significant issues found",
            "suggested_action": None
        }
