"""Synthesis - Combine specialist findings into final verdict."""

import logging
from dataclasses import dataclass
from typing import Optional, Union

from a2a_orchestrator.llm import gemini_synthesize

logger = logging.getLogger(__name__)


@dataclass
class SynthesisResult:
    verdict: str  # ACTIONABLE, UNKNOWN, FALSE_POSITIVE
    confidence: float
    synthesis: str
    suggested_action: Optional[str] = None


SEVERITY_SCORES = {
    "FAIL": 3,
    "ERROR": 2,
    "WARN": 1,
    "PASS": 0
}


def _get_finding_attr(finding, attr_name: str, default=None):
    """Get attribute from finding, supporting both old Finding and new SpecialistFinding.

    Attribute mappings:
    - agent/specialist: The specialist name
    - issue/summary: The finding description
    - recommendation: Only in old Finding (returns None for SpecialistFinding)
    """
    # Map old attribute names to new ones
    attr_map = {
        "agent": ["agent", "specialist"],
        "specialist": ["specialist", "agent"],
        "issue": ["issue", "summary"],
        "summary": ["summary", "issue"],
        "recommendation": ["recommendation"],  # Only in old Finding
    }

    attrs_to_try = attr_map.get(attr_name, [attr_name])

    for attr in attrs_to_try:
        if hasattr(finding, attr):
            value = getattr(finding, attr, None)
            if value is not None:
                return value

    return default


async def synthesize_findings(
    findings: list,
    alert,
    domain_weights: dict
) -> SynthesisResult:
    """Synthesize findings from all specialists into final verdict.

    Uses weighted scoring based on domain authority and finding severity.
    Falls back to rule-based synthesis if LLM unavailable.

    Args:
        findings: List of Finding or SpecialistFinding objects from specialists
        alert: Original alert
        domain_weights: Weight per domain

    Returns:
        SynthesisResult with verdict, confidence, synthesis, suggested_action
    """
    if not findings:
        return SynthesisResult(
            verdict="UNKNOWN",
            confidence=0.3,
            synthesis="No specialist findings available"
        )

    try:
        # Try LLM-based synthesis
        result = await gemini_synthesize(findings, alert, domain_weights)
        return SynthesisResult(
            verdict=result["verdict"],
            confidence=result["confidence"],
            synthesis=result["synthesis"],
            suggested_action=result.get("suggested_action")
        )

    except Exception as e:
        logger.warning(f"LLM synthesis failed, using rule-based: {e}")
        return rule_based_synthesis(findings, alert, domain_weights)


def rule_based_synthesis(
    findings: list,
    alert,
    domain_weights: dict
) -> SynthesisResult:
    """Rule-based synthesis when LLM unavailable.

    Weights findings by domain authority and severity to determine verdict.
    Supports both old Finding and new SpecialistFinding objects.
    """
    if not findings:
        return SynthesisResult(
            verdict="UNKNOWN",
            confidence=0.3,
            synthesis="No findings"
        )

    # Calculate weighted score
    total_weight = 0
    weighted_score = 0
    issues = []
    recommendations = []

    for f in findings:
        # Get agent/specialist name (supports both old and new models)
        agent_name = _get_finding_attr(f, "agent", "unknown")
        weight = domain_weights.get(agent_name, 0.5)

        # Get status (same in both models)
        status = getattr(f, "status", "PASS")
        severity = SEVERITY_SCORES.get(status, 1)

        weighted_score += weight * severity
        total_weight += weight

        # Get issue/summary (supports both old and new models)
        issue_text = _get_finding_attr(f, "issue")
        if issue_text and status in ("FAIL", "WARN", "ERROR"):
            issues.append(f"{agent_name}: {issue_text}")

        # Get recommendation (only in old Finding, None for SpecialistFinding)
        recommendation = _get_finding_attr(f, "recommendation")
        if recommendation:
            recommendations.append(recommendation)

    # Normalize score
    if total_weight > 0:
        normalized_score = weighted_score / total_weight
    else:
        normalized_score = 0

    # Determine verdict
    fail_count = sum(1 for f in findings if getattr(f, "status", "PASS") == "FAIL")
    error_count = sum(1 for f in findings if getattr(f, "status", "PASS") == "ERROR")

    if fail_count > 0 or normalized_score >= 2.0:
        verdict = "ACTIONABLE"
        confidence = min(0.95, 0.7 + (normalized_score * 0.1))
    elif error_count > 0 or normalized_score >= 1.0:
        verdict = "UNKNOWN"
        confidence = 0.5 + (normalized_score * 0.1)
    else:
        verdict = "FALSE_POSITIVE"
        confidence = max(0.4, 0.8 - (normalized_score * 0.2))

    # Build synthesis text
    if issues:
        synthesis = "; ".join(issues[:3])
    else:
        synthesis = f"Alert '{alert.name}' investigated by {len(findings)} specialists. No critical issues found."

    return SynthesisResult(
        verdict=verdict,
        confidence=round(confidence, 2),
        synthesis=synthesis,
        suggested_action=recommendations[0] if recommendations else None
    )
