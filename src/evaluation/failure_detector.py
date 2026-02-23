"""
Failure pattern detection for conversation analysis.

Identifies 10 distinct failure patterns in conversation transcripts,
each with severity and contextual evidence for root-cause analysis.
"""

import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

from src.schemas.conversation_schema import ConversationTranscript, Speaker, CallOutcome
from src.config import settings

logger = logging.getLogger(__name__)


class FailurePattern(str, Enum):
    """Categorized failure patterns detectable in transcripts."""
    REPEATED_SLOT_FAILURE = "repeated_slot_failure"
    CONFIRMATION_LOOP = "confirmation_loop"
    WRONG_AGENT_HANDOFF = "wrong_agent_handoff"
    SCOPE_VIOLATION = "scope_violation"
    CALLER_FRUSTRATION = "caller_frustration"
    HALLUCINATED_INFO = "hallucinated_info"
    MISSED_INTENT = "missed_intent"
    INCOMPLETE_BOOKING = "incomplete_booking"
    UNNECESSARY_ESCALATION = "unnecessary_escalation"
    SLOW_RESPONSE = "slow_response"


@dataclass
class DetectedFailure:
    """A single detected failure with evidence."""
    pattern: FailurePattern
    severity: str  # "low", "medium", "high", "critical"
    evidence: str
    turn_index: Optional[int] = None
    recommendation: str = ""


class FailureDetector:
    """Detects failure patterns in conversation transcripts."""

    def detect_all(self, transcript: ConversationTranscript) -> list[DetectedFailure]:
        """Run all detection methods and return all found failures."""
        failures: list[DetectedFailure] = []

        failures.extend(self._detect_repeated_slot_failure(transcript))
        failures.extend(self._detect_confirmation_loop(transcript))
        failures.extend(self._detect_wrong_agent_handoff(transcript))
        failures.extend(self._detect_scope_violation(transcript))
        failures.extend(self._detect_caller_frustration(transcript))
        failures.extend(self._detect_hallucinated_info(transcript))
        failures.extend(self._detect_missed_intent(transcript))
        failures.extend(self._detect_incomplete_booking(transcript))
        failures.extend(self._detect_unnecessary_escalation(transcript))
        failures.extend(self._detect_slow_response(transcript))

        if failures:
            logger.info("Detected %d failure(s) in call %s", len(failures), transcript.call_id)

        return failures

    def _detect_repeated_slot_failure(
        self, transcript: ConversationTranscript
    ) -> list[DetectedFailure]:
        """Detect when the agent asks for the same information multiple times."""
        failures: list[DetectedFailure] = []
        slot_questions: dict[str, list[int]] = {}

        for i, turn in enumerate(transcript.turns):
            if turn.speaker != Speaker.AGENT:
                continue
            text = turn.text.lower()
            for slot_keyword in ["name", "phone", "number", "address", "date", "time", "service"]:
                if slot_keyword in text and ("what" in text or "could" in text or "can you" in text):
                    slot_questions.setdefault(slot_keyword, []).append(i)

        for slot, indices in slot_questions.items():
            if len(indices) >= 3:
                failures.append(DetectedFailure(
                    pattern=FailurePattern.REPEATED_SLOT_FAILURE,
                    severity="high",
                    evidence=f"Agent asked for '{slot}' {len(indices)} times (turns {indices})",
                    turn_index=indices[-1],
                    recommendation=f"Improve {slot} slot extraction — add normalization or clarification prompts.",
                ))

        return failures

    def _detect_confirmation_loop(
        self, transcript: ConversationTranscript
    ) -> list[DetectedFailure]:
        """Detect when confirmation is read back multiple times without progress."""
        failures = []
        confirmation_count = 0

        for i, turn in enumerate(transcript.turns):
            if turn.speaker == Speaker.AGENT:
                text = turn.text.lower()
                if "does everything sound correct" in text or "let me confirm" in text or "here's what i have" in text:
                    confirmation_count += 1
                    if confirmation_count >= 3:
                        failures.append(DetectedFailure(
                            pattern=FailurePattern.CONFIRMATION_LOOP,
                            severity="medium",
                            evidence=f"Confirmation read-back repeated {confirmation_count} times",
                            turn_index=i,
                            recommendation="Add logic to detect repeated confirmations and offer to correct specific fields.",
                        ))

        return failures

    def _detect_wrong_agent_handoff(
        self, transcript: ConversationTranscript
    ) -> list[DetectedFailure]:
        """Detect when a caller is routed to an inappropriate agent."""
        failures = []
        agents_used = transcript.agents_used or []

        if len(agents_used) > 3:
            failures.append(DetectedFailure(
                pattern=FailurePattern.WRONG_AGENT_HANDOFF,
                severity="medium",
                evidence=f"Caller passed through {len(agents_used)} agents: {agents_used}",
                recommendation="Review intent detection to reduce unnecessary handoffs.",
            ))

        return failures

    def _detect_scope_violation(
        self, transcript: ConversationTranscript
    ) -> list[DetectedFailure]:
        """Detect when the agent responds to out-of-scope topics."""
        failures = []
        out_of_scope = [
            "medical", "legal advice", "financial advice", "competitor",
            "political", "investment", "cryptocurrency",
        ]

        for i, turn in enumerate(transcript.turns):
            if turn.speaker == Speaker.AGENT:
                lower = turn.text.lower()
                for topic in out_of_scope:
                    if topic in lower and "i can't help with" not in lower and "outside" not in lower:
                        failures.append(DetectedFailure(
                            pattern=FailurePattern.SCOPE_VIOLATION,
                            severity="high",
                            evidence=f"Agent response contains out-of-scope topic '{topic}' at turn {i}",
                            turn_index=i,
                            recommendation=f"Add scope guardrail for '{topic}' topic.",
                        ))

        return failures

    def _detect_caller_frustration(
        self, transcript: ConversationTranscript
    ) -> list[DetectedFailure]:
        """Detect signs of caller frustration not addressed by escalation."""
        failures = []
        frustration_keywords = [
            "i already told you", "this is ridiculous", "useless",
            "speak to a person", "real person", "manager", "supervisor",
            "worst service", "unacceptable",
        ]

        for i, turn in enumerate(transcript.turns):
            if turn.speaker != Speaker.USER:
                continue
            lower = turn.text.lower()
            for keyword in frustration_keywords:
                if keyword in lower:
                    # Check if next agent turn addresses it
                    escalated = False
                    for j in range(i + 1, min(i + 3, len(transcript.turns))):
                        if transcript.turns[j].speaker == Speaker.AGENT:
                            agent_text = transcript.turns[j].text.lower()
                            if "transfer" in agent_text or "connect" in agent_text or "apologize" in agent_text or "sorry" in agent_text:
                                escalated = True
                                break
                    if not escalated:
                        failures.append(DetectedFailure(
                            pattern=FailurePattern.CALLER_FRUSTRATION,
                            severity="critical",
                            evidence=f"Caller frustration ('{keyword}') at turn {i} not addressed",
                            turn_index=i,
                            recommendation="Add frustration detection in guardrails and auto-escalate.",
                        ))

        return failures

    def _detect_hallucinated_info(
        self, transcript: ConversationTranscript
    ) -> list[DetectedFailure]:
        """Detect when the agent makes claims not grounded in tool data."""
        failures = []
        forbidden_claims = [
            "guarantee", "warranty", "award-winning",
            "best in the city", "cheapest", "lowest price",
            "fully insured", "fully licensed",
        ]

        for i, turn in enumerate(transcript.turns):
            if turn.speaker != Speaker.AGENT:
                continue
            lower = turn.text.lower()
            for claim in forbidden_claims:
                if claim in lower:
                    failures.append(DetectedFailure(
                        pattern=FailurePattern.HALLUCINATED_INFO,
                        severity="high",
                        evidence=f"Agent used unverified claim '{claim}' at turn {i}",
                        turn_index=i,
                        recommendation=f"Add post-LLM guardrail to block '{claim}' claims.",
                    ))

        return failures

    def _detect_missed_intent(
        self, transcript: ConversationTranscript
    ) -> list[DetectedFailure]:
        """Detect when a clear caller intent is not acted upon."""
        failures = []
        booking_signals = ["book", "appointment", "schedule", "come out", "send someone"]
        info_signals = ["how much", "price", "cost", "what services", "do you offer"]

        for i, turn in enumerate(transcript.turns):
            if turn.speaker != Speaker.USER:
                continue
            lower = turn.text.lower()
            has_booking_intent = any(s in lower for s in booking_signals)
            has_info_intent = any(s in lower for s in info_signals)

            if has_booking_intent or has_info_intent:
                # Check if agent responds appropriately within next 2 turns
                addressed = False
                for j in range(i + 1, min(i + 3, len(transcript.turns))):
                    if transcript.turns[j].speaker == Speaker.AGENT:
                        agent_lower = transcript.turns[j].text.lower()
                        if has_booking_intent and ("book" in agent_lower or "name" in agent_lower or "appointment" in agent_lower or "schedule" in agent_lower):
                            addressed = True
                        if has_info_intent and ("price" in agent_lower or "service" in agent_lower or "cost" in agent_lower or "offer" in agent_lower):
                            addressed = True
                        break

                if not addressed and i < len(transcript.turns) - 2:
                    intent = "booking" if has_booking_intent else "info"
                    failures.append(DetectedFailure(
                        pattern=FailurePattern.MISSED_INTENT,
                        severity="high",
                        evidence=f"Caller expressed {intent} intent at turn {i} but agent didn't respond appropriately",
                        turn_index=i,
                        recommendation=f"Improve intent detection for {intent} keywords.",
                    ))

        return failures

    def _detect_incomplete_booking(
        self, transcript: ConversationTranscript
    ) -> list[DetectedFailure]:
        """Detect when a booking attempt ends without completion despite having enough info."""
        failures = []
        slots = transcript.slots_collected or {}
        filled_count = sum(1 for v in slots.values() if v)

        if filled_count >= 4 and transcript.outcome not in (
            CallOutcome.BOOKING_MADE, CallOutcome.ESCALATED
        ):
            failures.append(DetectedFailure(
                pattern=FailurePattern.INCOMPLETE_BOOKING,
                severity="high",
                evidence=f"Booking had {filled_count}/6 slots filled but ended as {transcript.outcome.value}",
                recommendation="Review why booking was not completed — possible conversation flow issue.",
            ))

        return failures

    def _detect_unnecessary_escalation(
        self, transcript: ConversationTranscript
    ) -> list[DetectedFailure]:
        """Detect when a call was escalated but could have been resolved automatically."""
        failures: list[DetectedFailure] = []

        if transcript.outcome != CallOutcome.ESCALATED:
            return failures

        # Check if user actually requested escalation
        user_requested = False
        for turn in transcript.turns:
            if turn.speaker == Speaker.USER:
                lower = turn.text.lower()
                if any(kw in lower for kw in ["manager", "supervisor", "human", "real person", "speak to"]):
                    user_requested = True
                    break

        if not user_requested and transcript.error_count < settings.guardrails.confusion_threshold:
            failures.append(DetectedFailure(
                pattern=FailurePattern.UNNECESSARY_ESCALATION,
                severity="medium",
                evidence=f"Call escalated with only {transcript.error_count} errors and no user request for human",
                recommendation="Review escalation triggers — threshold may be too sensitive.",
            ))

        return failures

    def _detect_slow_response(
        self, transcript: ConversationTranscript
    ) -> list[DetectedFailure]:
        """Detect when agent responses took too long."""
        failures = []
        threshold = settings.guardrails.slow_response_threshold_sec

        for i, turn in enumerate(transcript.turns):
            if turn.speaker == Speaker.AGENT and turn.response_time_ms:
                response_sec = turn.response_time_ms / 1000
                if response_sec > threshold:
                    failures.append(DetectedFailure(
                        pattern=FailurePattern.SLOW_RESPONSE,
                        severity="low",
                        evidence=f"Response at turn {i} took {response_sec:.1f}s (threshold: {threshold}s)",
                        turn_index=i,
                        recommendation="Optimize tool calls or reduce prompt complexity for faster responses.",
                    ))

        return failures
