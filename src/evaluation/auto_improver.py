"""
Auto-improvement engine for generating prompt fix suggestions.

Maps detected failure patterns to specific, actionable prompt modifications.
Each suggestion includes the target prompt section, the proposed change,
and expected impact.
"""

import logging
from dataclasses import dataclass

from src.config import settings
from src.evaluation.failure_detector import DetectedFailure, FailurePattern

logger = logging.getLogger(__name__)


@dataclass
class PromptSuggestion:
    """A specific prompt modification suggestion."""

    target_prompt: str  # Which agent prompt to modify
    section: str  # Section within the prompt
    current_behavior: str
    suggested_change: str
    expected_impact: str
    priority: str  # "low", "medium", "high", "critical"
    failure_pattern: FailurePattern


class AutoImprover:
    """Generates prompt improvement suggestions from detected failures."""

    FIX_TEMPLATES: dict[FailurePattern, dict] = {
        FailurePattern.REPEATED_SLOT_FAILURE: {
            "target_prompt": "BOOKING_SYSTEM_PROMPT",
            "section": "Slot collection rules",
            "current_behavior": "Agent re-asks for information already provided",
            "suggested_change": (
                "Add instruction: 'Before asking for information, check if the caller "
                "has already provided it in a previous message. If so, confirm what you "
                "have and ask only for what is still missing.'"
            ),
            "expected_impact": "Reduce repeated slot requests by 60-80%",
            "priority": "high",
        },
        FailurePattern.CONFIRMATION_LOOP: {
            "target_prompt": "BOOKING_SYSTEM_PROMPT",
            "section": "Confirmation gate",
            "current_behavior": "Agent reads back details multiple times without progress",
            "suggested_change": (
                "Add instruction: 'If the caller does not confirm after the second "
                "read-back, ask which specific detail needs to be changed rather than "
                "repeating the full summary.'"
            ),
            "expected_impact": "Reduce confirmation loops by 50-70%",
            "priority": "medium",
        },
        FailurePattern.WRONG_AGENT_HANDOFF: {
            "target_prompt": "INTAKE_SYSTEM_PROMPT",
            "section": "Intent detection rules",
            "current_behavior": "Caller bounced between multiple agents unnecessarily",
            "suggested_change": (
                "Add instruction: 'Classify intent carefully before routing. If the caller "
                "mentions both a question and a booking need, route to booking — the booking "
                "agent can answer basic questions too.'"
            ),
            "expected_impact": "Reduce unnecessary handoffs by 40-60%",
            "priority": "medium",
        },
        FailurePattern.SCOPE_VIOLATION: {
            "target_prompt": "ALL",
            "section": "DO NOT section",
            "current_behavior": "Agent engages with out-of-scope topics",
            "suggested_change": (
                "Strengthen scope boundaries: 'If the caller asks about topics outside "
                "home services (medical, legal, financial, etc.), politely redirect: "
                '"I can only help with home services. Would you like to book a service '
                "or get information about what we offer?\"'"
            ),
            "expected_impact": "Eliminate scope violations",
            "priority": "high",
        },
        FailurePattern.CALLER_FRUSTRATION: {
            "target_prompt": "BOOKING_SYSTEM_PROMPT",
            "section": "Escalation rules",
            "current_behavior": "Caller frustration not detected or addressed",
            "suggested_change": (
                "Add instruction: 'If the caller expresses frustration (repeated corrections, "
                'raised voice indicators, words like "ridiculous" or "already told you"), '
                "immediately acknowledge their frustration and offer to connect them with a "
                "team member. Never continue collecting slots from a frustrated caller.'"
            ),
            "expected_impact": "Improve caller satisfaction by 30-50%",
            "priority": "critical",
        },
        FailurePattern.HALLUCINATED_INFO: {
            "target_prompt": "ALL",
            "section": "DO NOT section",
            "current_behavior": "Agent makes unverified claims",
            "suggested_change": (
                'Add explicit forbidden claims list: \'Never use words like "guarantee", '
                '"warranty", "award-winning", "best", "cheapest", "fully insured" '
                'or "fully licensed" — only state facts available in the service catalog.\''
            ),
            "expected_impact": "Eliminate hallucinated claims",
            "priority": "high",
        },
        FailurePattern.MISSED_INTENT: {
            "target_prompt": "INTAKE_SYSTEM_PROMPT",
            "section": "Intent detection",
            "current_behavior": "Agent misses clear booking or info intent signals",
            "suggested_change": (
                "Add keyword triggers: 'Detect booking intent "
                'from phrases like "book", "appointment", '
                '"schedule", "come out", "send someone". '
                'Detect info intent from "how much", "price", '
                '"cost", "what services", "do you offer". '
                "Route immediately when detected.'"
            ),
            "expected_impact": "Improve intent detection accuracy by 20-40%",
            "priority": "high",
        },
        FailurePattern.INCOMPLETE_BOOKING: {
            "target_prompt": "BOOKING_SYSTEM_PROMPT",
            "section": "Completion rules",
            "current_behavior": "Booking attempt abandoned despite having most information",
            "suggested_change": (
                "Add instruction: 'If the caller has provided 4 or more details, make every "
                "effort to complete the booking. If they seem to be leaving, summarize what "
                "you have and offer to complete the booking quickly with just the remaining "
                "information.'"
            ),
            "expected_impact": "Recover 20-40% of incomplete bookings",
            "priority": "high",
        },
        FailurePattern.UNNECESSARY_ESCALATION: {
            "target_prompt": "ESCALATION triggers",
            "section": "Escalation thresholds",
            "current_behavior": "Call escalated without clear trigger",
            "suggested_change": (
                "Review escalation thresholds: increase confusion_threshold "
                f"from {settings.guardrails.confusion_threshold} to "
                f"{settings.guardrails.confusion_threshold + 1}, "
                "and require at least one frustration keyword before "
                "auto-escalating."
            ),
            "expected_impact": "Reduce unnecessary escalations by 30-50%",
            "priority": "medium",
        },
        FailurePattern.SLOW_RESPONSE: {
            "target_prompt": "Model configuration",
            "section": "LLM settings",
            "current_behavior": "Agent response latency exceeds threshold",
            "suggested_change": (
                "Consider: 1) Reduce system prompt length, 2) Use gpt-4o-mini for "
                "simple slot recording, 3) Pre-compute tool responses where possible, "
                "4) Add response streaming for immediate feedback."
            ),
            "expected_impact": "Reduce average response latency by 30-50%",
            "priority": "low",
        },
    }

    def suggest_improvements(self, failures: list[DetectedFailure]) -> list[PromptSuggestion]:
        """Generate prompt improvement suggestions from detected failures."""
        suggestions: list[PromptSuggestion] = []
        seen_patterns: set[FailurePattern] = set()

        for failure in failures:
            if failure.pattern in seen_patterns:
                continue
            seen_patterns.add(failure.pattern)

            template = self.FIX_TEMPLATES.get(failure.pattern)
            if template:
                suggestions.append(
                    PromptSuggestion(
                        target_prompt=template["target_prompt"],
                        section=template["section"],
                        current_behavior=template["current_behavior"],
                        suggested_change=template["suggested_change"],
                        expected_impact=template["expected_impact"],
                        priority=template["priority"],
                        failure_pattern=failure.pattern,
                    )
                )

        # Sort by priority
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        suggestions.sort(key=lambda s: priority_order.get(s.priority, 4))

        return suggestions

    def format_suggestions(self, suggestions: list[PromptSuggestion]) -> str:
        """Format suggestions into a readable report."""
        if not suggestions:
            return "No improvement suggestions — all patterns look clean."

        lines = [
            "",
            "=" * 60,
            "PROMPT IMPROVEMENT SUGGESTIONS",
            "=" * 60,
        ]

        for i, s in enumerate(suggestions, 1):
            lines.extend(
                [
                    "",
                    f"[{i}] {s.failure_pattern.value} ({s.priority.upper()} priority)",
                    f"    Target: {s.target_prompt} > {s.section}",
                    f"    Issue:  {s.current_behavior}",
                    f"    Fix:    {s.suggested_change}",
                    f"    Impact: {s.expected_impact}",
                ]
            )

        lines.append("")
        lines.append("=" * 60)
        return "\n".join(lines)
