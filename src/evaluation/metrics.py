"""
Key performance indicators for voice agent evaluation.

15 KPIs across 5 categories: task success, slot quality,
efficiency, errors, and guardrails. Each metric is calculated
from a ConversationTranscript instance.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from src.schemas.conversation_schema import ConversationTranscript, CallOutcome, Speaker
from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class EvalMetrics:
    """Calculated metrics for a single conversation or batch."""

    # Task success
    success_rate: float = 0.0
    first_call_resolution: float = 0.0
    containment_rate: float = 0.0

    # Slot quality
    slot_fill_rate: float = 0.0
    slot_correction_rate: float = 0.0
    avg_slot_attempts: float = 0.0
    confirmation_pass_rate: float = 0.0

    # Efficiency
    avg_turns_to_booking: float = 0.0
    avg_duration_seconds: float = 0.0
    handoff_rate: float = 0.0

    # Errors
    error_rate: float = 0.0
    recovery_success_rate: float = 0.0
    escalation_rate: float = 0.0

    # Guardrails
    scope_violation_rate: float = 0.0
    hallucination_detection_rate: float = 0.0


class MetricsCalculator:
    """Calculates evaluation metrics from conversation transcripts."""

    def calculate(self, transcript: ConversationTranscript) -> EvalMetrics:
        """Calculate all KPIs from a single transcript."""
        metrics = EvalMetrics()

        total_turns = len(transcript.turns)
        agent_turns = [t for t in transcript.turns if t.speaker == Speaker.AGENT]
        user_turns = [t for t in transcript.turns if t.speaker == Speaker.USER]

        # Task success
        metrics.success_rate = 1.0 if transcript.outcome == CallOutcome.BOOKING_MADE else 0.0
        metrics.first_call_resolution = 1.0 if transcript.outcome in (
            CallOutcome.BOOKING_MADE, CallOutcome.INFO_PROVIDED
        ) else 0.0
        metrics.containment_rate = 1.0 if transcript.outcome != CallOutcome.ESCALATED else 0.0

        # Slot quality
        slots_collected = transcript.slots_collected or {}
        required_slots = [
            "customer_name", "customer_phone", "service_type",
            "preferred_date", "preferred_time", "customer_address",
        ]
        total_required = len(required_slots)
        filled = sum(1 for key in required_slots if slots_collected.get(key))
        metrics.slot_fill_rate = filled / total_required

        corrections = transcript.metadata.get("corrections", 0) if transcript.metadata else 0
        total_attempts = transcript.metadata.get("total_attempts", filled) if transcript.metadata else filled
        metrics.slot_correction_rate = corrections / max(filled, 1)
        metrics.avg_slot_attempts = total_attempts / max(filled, 1)
        metrics.confirmation_pass_rate = 1.0 if transcript.outcome == CallOutcome.BOOKING_MADE else 0.0

        # Efficiency
        metrics.avg_turns_to_booking = float(total_turns) if transcript.outcome == CallOutcome.BOOKING_MADE else 0.0
        metrics.avg_duration_seconds = transcript.duration_seconds or 0.0

        agents_used = transcript.agents_used or []
        handoff_count = max(len(agents_used) - 1, 0)
        metrics.handoff_rate = min(handoff_count / max(total_turns, 1), 1.0)

        # Errors
        metrics.error_rate = transcript.error_count / max(total_turns, 1)
        if transcript.error_count > 0:
            recovery_count = transcript.metadata.get("recoveries", 0) if transcript.metadata else 0
            metrics.recovery_success_rate = recovery_count / transcript.error_count
        metrics.escalation_rate = 1.0 if transcript.outcome == CallOutcome.ESCALATED else 0.0

        # Guardrails
        if transcript.metadata:
            scope_checks = transcript.metadata.get("scope_checks", 0)
            scope_violations = transcript.metadata.get("scope_violations", 0)
            metrics.scope_violation_rate = scope_violations / max(scope_checks, 1)

            hallucination_checks = transcript.metadata.get("hallucination_checks", 0)
            hallucinations = transcript.metadata.get("hallucinations_detected", 0)
            metrics.hallucination_detection_rate = hallucinations / max(hallucination_checks, 1)

        return metrics

    def calculate_batch(self, transcripts: list[ConversationTranscript]) -> EvalMetrics:
        """Calculate averaged metrics across a batch of transcripts."""
        if not transcripts:
            return EvalMetrics()

        all_metrics = [self.calculate(t) for t in transcripts]
        n = len(all_metrics)

        averaged = EvalMetrics()
        for attr in vars(averaged):
            if attr.startswith("_"):
                continue
            total = sum(getattr(m, attr) for m in all_metrics)
            setattr(averaged, attr, total / n)

        return averaged

    def format_report(self, metrics: EvalMetrics) -> str:
        """Format metrics into a human-readable report."""
        targets = settings.evaluation

        lines = [
            "=" * 60,
            "VOICE AGENT EVALUATION REPORT",
            "=" * 60,
            "",
            "TASK SUCCESS",
            f"  Success rate:           {metrics.success_rate:.1%}  (target: {targets.target_success_rate:.0%})",
            f"  First-call resolution:  {metrics.first_call_resolution:.1%}",
            f"  Containment rate:       {metrics.containment_rate:.1%}  (target: {targets.target_containment_rate:.0%})",
            "",
            "SLOT QUALITY",
            f"  Fill rate:              {metrics.slot_fill_rate:.1%}  (target: {targets.target_slot_fill_rate:.0%})",
            f"  Correction rate:        {metrics.slot_correction_rate:.1%}",
            f"  Avg attempts per slot:  {metrics.avg_slot_attempts:.1f}",
            f"  Confirmation pass rate: {metrics.confirmation_pass_rate:.1%}",
            "",
            "EFFICIENCY",
            f"  Avg turns to booking:   {metrics.avg_turns_to_booking:.1f}  (target: <{targets.target_max_turns})",
            f"  Avg duration:           {metrics.avg_duration_seconds:.0f}s",
            f"  Handoff rate:           {metrics.handoff_rate:.1%}",
            "",
            "ERRORS",
            f"  Error rate:             {metrics.error_rate:.1%}",
            f"  Recovery success rate:  {metrics.recovery_success_rate:.1%}",
            f"  Escalation rate:        {metrics.escalation_rate:.1%}  (target: <{targets.target_escalation_rate:.0%})",
            "",
            "GUARDRAILS",
            f"  Scope violation rate:   {metrics.scope_violation_rate:.1%}",
            f"  Hallucination det rate: {metrics.hallucination_detection_rate:.1%}",
            "=" * 60,
        ]
        return "\n".join(lines)
