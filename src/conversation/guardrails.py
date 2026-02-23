"""
Multi-layer guardrail system for controlling agent behavior.

Four independent guardrail layers, each checking a different concern:
1. ScopeGuardrail     — validates services and rejects off-topic requests
2. HallucinationGuardrail — flags unverified claims in agent responses
3. PersonaGuardrail   — enforces voice style and blocks AI self-references
4. EscalationGuardrail — detects emergencies and caller frustration

These are composed into a GuardrailPipeline for pre-LLM and post-LLM checks.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from src.config import settings
from src.tools.services import get_valid_service_terms

logger = logging.getLogger(__name__)


@dataclass
class GuardrailResult:
    """Outcome of a single guardrail check."""
    passed: bool
    violation_type: Optional[str] = None
    message: Optional[str] = None
    severity: str = "warning"  # "warning" | "block" | "escalate"


class ScopeGuardrail:
    """Validates that conversations stay within defined service boundaries."""

    OUT_OF_SCOPE_TOPICS = [
        "medical advice", "legal advice", "financial advice",
        "competitor", "political", "religious",
        "investment", "cryptocurrency", "dating",
    ]

    def check_service_scope(self, service: str) -> GuardrailResult:
        normalized = service.lower().strip()
        for valid in get_valid_service_terms():
            if valid in normalized or normalized in valid:
                return GuardrailResult(passed=True)
        return GuardrailResult(
            passed=False,
            violation_type="out_of_scope_service",
            message=f"'{service}' is not in our service catalog.",
            severity="warning",
        )

    def check_topic_scope(self, text: str) -> GuardrailResult:
        lower = text.lower()
        for topic in self.OUT_OF_SCOPE_TOPICS:
            if topic in lower:
                return GuardrailResult(
                    passed=False,
                    violation_type="out_of_scope_topic",
                    message=f"Topic '{topic}' is outside our scope.",
                    severity="block",
                )
        return GuardrailResult(passed=True)


class HallucinationGuardrail:
    """Detects potentially fabricated claims in agent responses."""

    FORBIDDEN_CLAIMS = [
        "guarantee", "warranty", "we guarantee",
        "years of experience", "award-winning",
        "best in the city", "cheapest", "lowest price",
        "fully insured", "fully licensed",
    ]

    def check_response(self, response_text: str) -> GuardrailResult:
        lower = response_text.lower()
        for claim in self.FORBIDDEN_CLAIMS:
            if claim in lower:
                logger.warning("Hallucination detected: '%s'", claim)
                return GuardrailResult(
                    passed=False,
                    violation_type="potential_hallucination",
                    message=f"Response contains unverified claim: '{claim}'.",
                    severity="block",
                )
        return GuardrailResult(passed=True)


class PersonaGuardrail:
    """Enforces consistent voice persona and prevents formatting leaks."""

    FORBIDDEN_PATTERNS = [
        "as an ai", "as a language model", "i'm just a computer",
        "i don't have feelings", "i'm not sure if",
        "i think maybe", "i cannot", "i'm unable to",
    ]

    FORMATTING_VIOLATIONS = ["- ", "* ", "1. ", "## ", "**", "```"]

    def check_persona(self, response_text: str) -> GuardrailResult:
        lower = response_text.lower()
        for pattern in self.FORBIDDEN_PATTERNS:
            if pattern in lower:
                return GuardrailResult(
                    passed=False,
                    violation_type="persona_break",
                    message=f"Response breaks persona with: '{pattern}'.",
                    severity="warning",
                )
        return GuardrailResult(passed=True)

    def check_formatting(self, response_text: str) -> GuardrailResult:
        for fmt in self.FORMATTING_VIOLATIONS:
            if fmt in response_text:
                return GuardrailResult(
                    passed=False,
                    violation_type="formatting_violation",
                    message=f"Voice response should not contain '{fmt}' formatting.",
                    severity="warning",
                )
        return GuardrailResult(passed=True)


class EscalationGuardrail:
    """Detects conditions requiring immediate escalation to a human."""

    EMERGENCY_KEYWORDS = [
        "gas leak", "flooding", "flood", "fire", "sparking",
        "electrocution", "burst pipe", "no hot water emergency",
        "carbon monoxide", "smell gas", "water everywhere",
    ]

    FRUSTRATION_KEYWORDS = [
        "manager", "supervisor", "speak to a person",
        "real person", "human", "unacceptable",
        "lawsuit", "ridiculous", "useless",
        "worst service", "i already told you",
    ]

    def check_escalation_needed(
        self, user_message: str, error_count: int = 0
    ) -> GuardrailResult:
        lower = user_message.lower()

        for keyword in self.EMERGENCY_KEYWORDS:
            if keyword in lower:
                logger.info("Emergency keyword detected: '%s'", keyword)
                return GuardrailResult(
                    passed=False,
                    violation_type="emergency",
                    message=f"Emergency detected: '{keyword}'.",
                    severity="escalate",
                )

        for keyword in self.FRUSTRATION_KEYWORDS:
            if keyword in lower:
                logger.info("Frustration keyword detected: '%s'", keyword)
                return GuardrailResult(
                    passed=False,
                    violation_type="caller_frustration",
                    message=f"Caller frustration detected: '{keyword}'.",
                    severity="escalate",
                )

        threshold = settings.guardrails.confusion_threshold
        if error_count >= threshold:
            return GuardrailResult(
                passed=False,
                violation_type="repeated_confusion",
                message=f"Error count ({error_count}) exceeds threshold ({threshold}).",
                severity="escalate",
            )

        return GuardrailResult(passed=True)


class GuardrailPipeline:
    """Composes all guardrails into pre-LLM and post-LLM check pipelines."""

    def __init__(self) -> None:
        self.scope = ScopeGuardrail()
        self.hallucination = HallucinationGuardrail()
        self.persona = PersonaGuardrail()
        self.escalation = EscalationGuardrail()

    def check_user_input(
        self, text: str, error_count: int = 0
    ) -> list[GuardrailResult]:
        """Pre-LLM: check user input for escalation triggers and scope violations."""
        results = [
            self.escalation.check_escalation_needed(text, error_count),
            self.scope.check_topic_scope(text),
        ]
        return [r for r in results if not r.passed]

    def check_agent_response(self, text: str) -> list[GuardrailResult]:
        """Post-LLM: check agent response for hallucinations, persona, formatting."""
        results = [
            self.hallucination.check_response(text),
            self.persona.check_persona(text),
            self.persona.check_formatting(text),
        ]
        return [r for r in results if not r.passed]
