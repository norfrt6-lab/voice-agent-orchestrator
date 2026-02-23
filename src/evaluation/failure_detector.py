"""
Failure pattern detection for conversation analysis.

Identifies 10 distinct failure patterns in conversation transcripts,
each with severity and contextual evidence for root-cause analysis.
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from src.config import settings
from src.schemas.conversation_schema import CallOutcome, ConversationTranscript, Speaker

logger = logging.getLogger(__name__)


def _compile_patterns(phrases: list[str]) -> re.Pattern[str]:
    """Compile a list of phrases into a single word-boundary regex."""
    escaped = [re.escape(p) for p in phrases]
    return re.compile(r"\b(?:" + "|".join(escaped) + r")\b", re.IGNORECASE)

# Detection thresholds
REPEATED_SLOT_THRESHOLD = 3
CONFIRMATION_LOOP_THRESHOLD = 3
MAX_REASONABLE_AGENTS = 3
INCOMPLETE_BOOKING_MIN_SLOTS = 4
TOTAL_REQUIRED_SLOTS = 6


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


_SLOT_KEYWORDS = ["name", "phone", "number", "address", "date", "time", "service"]
_SLOT_QUESTION_WORDS = ["what", "could", "can you"]
_SLOT_KW_RE = _compile_patterns(_SLOT_KEYWORDS)
_SLOT_Q_RE = _compile_patterns(_SLOT_QUESTION_WORDS)

_CONFIRMATION_PHRASES = [
    "does everything sound correct",
    "let me confirm",
    "here's what i have",
]
_CONFIRMATION_RE = _compile_patterns(_CONFIRMATION_PHRASES)

_OUT_OF_SCOPE_TOPICS = [
    "medical",
    "legal advice",
    "financial advice",
    "competitor",
    "political",
    "investment",
    "cryptocurrency",
]
_OUT_OF_SCOPE_RE = _compile_patterns(_OUT_OF_SCOPE_TOPICS)
_SCOPE_DEFLECTION_RE = _compile_patterns(["i can't help with", "outside"])

_FRUSTRATION_PHRASES = [
    "i already told you",
    "this is ridiculous",
    "useless",
    "speak to a person",
    "real person",
    "manager",
    "supervisor",
    "worst service",
    "unacceptable",
]
_FRUSTRATION_RE = _compile_patterns(_FRUSTRATION_PHRASES)
_ESCALATION_RESPONSE_RE = _compile_patterns(["transfer", "connect", "apologize", "sorry"])

_HALLUCINATION_CLAIMS = [
    "guarantee",
    "warranty",
    "award-winning",
    "best in the city",
    "cheapest",
    "lowest price",
    "fully insured",
    "fully licensed",
]
_HALLUCINATION_RE = _compile_patterns(_HALLUCINATION_CLAIMS)

_BOOKING_SIGNALS = ["book", "appointment", "schedule", "come out", "send someone"]
_INFO_SIGNALS = ["how much", "price", "cost", "what services", "do you offer"]
_BOOKING_RE = _compile_patterns(_BOOKING_SIGNALS)
_INFO_RE = _compile_patterns(_INFO_SIGNALS)
_BOOKING_RESPONSE_RE = _compile_patterns(["book", "name", "appointment", "schedule"])
_INFO_RESPONSE_RE = _compile_patterns(["price", "service", "cost", "offer"])

_USER_ESCALATION_RE = _compile_patterns(
    ["manager", "supervisor", "human", "real person", "speak to"]
)


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
            text = turn.text
            if not _SLOT_Q_RE.search(text):
                continue
            for match in _SLOT_KW_RE.finditer(text):
                slot_questions.setdefault(match.group().lower(), []).append(i)

        for slot, indices in slot_questions.items():
            if len(indices) >= REPEATED_SLOT_THRESHOLD:
                failures.append(
                    DetectedFailure(
                        pattern=FailurePattern.REPEATED_SLOT_FAILURE,
                        severity="high",
                        evidence=f"Agent asked for '{slot}' {len(indices)} times (turns {indices})",
                        turn_index=indices[-1],
                        recommendation=(
                            f"Improve {slot} slot extraction"
                            " — add normalization or"
                            " clarification prompts."
                        ),
                    )
                )

        return failures

    def _detect_confirmation_loop(
        self, transcript: ConversationTranscript
    ) -> list[DetectedFailure]:
        """Detect when confirmation is read back multiple times without progress."""
        failures = []
        confirmation_count = 0

        for i, turn in enumerate(transcript.turns):
            if turn.speaker == Speaker.AGENT:
                if _CONFIRMATION_RE.search(turn.text):
                    confirmation_count += 1
                    if confirmation_count >= CONFIRMATION_LOOP_THRESHOLD:
                        failures.append(
                            DetectedFailure(
                                pattern=FailurePattern.CONFIRMATION_LOOP,
                                severity="medium",
                                evidence=(
                                    "Confirmation read-back repeated"
                                    f" {confirmation_count} times"
                                ),
                                turn_index=i,
                                recommendation=(
                                    "Add logic to detect repeated"
                                    " confirmations and offer to"
                                    " correct specific fields."
                                ),
                            )
                        )

        return failures

    def _detect_wrong_agent_handoff(
        self, transcript: ConversationTranscript
    ) -> list[DetectedFailure]:
        """Detect when a caller is routed to an inappropriate agent."""
        failures = []
        agents_used = transcript.agents_used or []

        if len(agents_used) > MAX_REASONABLE_AGENTS:
            failures.append(
                DetectedFailure(
                    pattern=FailurePattern.WRONG_AGENT_HANDOFF,
                    severity="medium",
                    evidence=f"Caller passed through {len(agents_used)} agents: {agents_used}",
                    recommendation="Review intent detection to reduce unnecessary handoffs.",
                )
            )

        return failures

    def _detect_scope_violation(self, transcript: ConversationTranscript) -> list[DetectedFailure]:
        """Detect when the agent responds to out-of-scope topics."""
        failures = []

        for i, turn in enumerate(transcript.turns):
            if turn.speaker == Speaker.AGENT:
                text = turn.text
                if _SCOPE_DEFLECTION_RE.search(text):
                    continue
                for match in _OUT_OF_SCOPE_RE.finditer(text):
                    topic = match.group().lower()
                    failures.append(
                        DetectedFailure(
                            pattern=FailurePattern.SCOPE_VIOLATION,
                            severity="high",
                            evidence=(
                                f"Agent response contains"
                                f" out-of-scope topic"
                                f" '{topic}' at turn {i}"
                            ),
                            turn_index=i,
                            recommendation=(
                                "Add scope guardrail for"
                                f" '{topic}' topic."
                            ),
                        )
                    )

        return failures

    def _detect_caller_frustration(
        self, transcript: ConversationTranscript
    ) -> list[DetectedFailure]:
        """Detect signs of caller frustration not addressed by escalation."""
        failures = []

        for i, turn in enumerate(transcript.turns):
            if turn.speaker != Speaker.USER:
                continue
            match = _FRUSTRATION_RE.search(turn.text)
            if not match:
                continue
            keyword = match.group().lower()
            # Check if next agent turn addresses it
            escalated = False
            for j in range(i + 1, min(i + 3, len(transcript.turns))):
                if transcript.turns[j].speaker == Speaker.AGENT:
                    if _ESCALATION_RESPONSE_RE.search(transcript.turns[j].text):
                        escalated = True
                    break
            if not escalated:
                failures.append(
                    DetectedFailure(
                        pattern=FailurePattern.CALLER_FRUSTRATION,
                        severity="critical",
                        evidence=(
                            f"Caller frustration"
                            f" ('{keyword}') at turn"
                            f" {i} not addressed"
                        ),
                        turn_index=i,
                        recommendation=(
                            "Add frustration detection"
                            " in guardrails and"
                            " auto-escalate."
                        ),
                    )
                )

        return failures

    def _detect_hallucinated_info(
        self, transcript: ConversationTranscript
    ) -> list[DetectedFailure]:
        """Detect when the agent makes claims not grounded in tool data."""
        failures = []

        for i, turn in enumerate(transcript.turns):
            if turn.speaker != Speaker.AGENT:
                continue
            for match in _HALLUCINATION_RE.finditer(turn.text):
                claim = match.group().lower()
                failures.append(
                    DetectedFailure(
                        pattern=FailurePattern.HALLUCINATED_INFO,
                        severity="high",
                        evidence=(
                            f"Agent used unverified claim"
                            f" '{claim}' at turn {i}"
                        ),
                        turn_index=i,
                        recommendation=(
                            "Add post-LLM guardrail to"
                            f" block '{claim}' claims."
                        ),
                    )
                )

        return failures

    def _detect_missed_intent(self, transcript: ConversationTranscript) -> list[DetectedFailure]:
        """Detect when a clear caller intent is not acted upon."""
        failures = []

        for i, turn in enumerate(transcript.turns):
            if turn.speaker != Speaker.USER:
                continue
            has_booking_intent = bool(_BOOKING_RE.search(turn.text))
            has_info_intent = bool(_INFO_RE.search(turn.text))

            if has_booking_intent or has_info_intent:
                # Check if agent responds appropriately within next 2 turns
                addressed = False
                for j in range(i + 1, min(i + 3, len(transcript.turns))):
                    if transcript.turns[j].speaker == Speaker.AGENT:
                        agent_text = transcript.turns[j].text
                        if has_booking_intent and _BOOKING_RESPONSE_RE.search(agent_text):
                            addressed = True
                        if has_info_intent and _INFO_RESPONSE_RE.search(agent_text):
                            addressed = True
                        break

                if not addressed and i < len(transcript.turns) - 2:
                    intent = "booking" if has_booking_intent else "info"
                    failures.append(
                        DetectedFailure(
                            pattern=FailurePattern.MISSED_INTENT,
                            severity="high",
                            evidence=(
                                f"Caller expressed {intent}"
                                f" intent at turn {i} but"
                                " agent didn't respond"
                                " appropriately"
                            ),
                            turn_index=i,
                            recommendation=(
                                "Improve intent detection"
                                f" for {intent} keywords."
                            ),
                        )
                    )

        return failures

    def _detect_incomplete_booking(
        self, transcript: ConversationTranscript
    ) -> list[DetectedFailure]:
        """Detect when a booking attempt ends without completion despite having enough info."""
        failures = []
        slots = transcript.slots_collected or {}
        filled_count = sum(1 for v in slots.values() if v)

        if filled_count >= INCOMPLETE_BOOKING_MIN_SLOTS and transcript.outcome not in (
            CallOutcome.BOOKING_MADE,
            CallOutcome.ESCALATED,
        ):
            failures.append(
                DetectedFailure(
                    pattern=FailurePattern.INCOMPLETE_BOOKING,
                    severity="high",
                    evidence=(
                        f"Booking had {filled_count}/{TOTAL_REQUIRED_SLOTS} slots"
                        " filled but ended as"
                        f" {transcript.outcome.value}"
                    ),
                    recommendation=(
                        "Review why booking was not"
                        " completed — possible"
                        " conversation flow issue."
                    ),
                )
            )

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
                if _USER_ESCALATION_RE.search(turn.text):
                    user_requested = True
                    break

        if not user_requested and transcript.error_count < settings.guardrails.confusion_threshold:
            failures.append(
                DetectedFailure(
                    pattern=FailurePattern.UNNECESSARY_ESCALATION,
                    severity="medium",
                    evidence=(
                        "Call escalated with only"
                        f" {transcript.error_count} errors"
                        " and no user request for human"
                    ),
                    recommendation=(
                        "Review escalation triggers"
                        " — threshold may be too"
                        " sensitive."
                    ),
                )
            )

        return failures

    def _detect_slow_response(self, transcript: ConversationTranscript) -> list[DetectedFailure]:
        """Detect when agent responses took too long."""
        failures = []
        threshold = settings.guardrails.slow_response_threshold_sec

        for i, turn in enumerate(transcript.turns):
            if turn.speaker == Speaker.AGENT and turn.response_time_ms:
                response_sec = turn.response_time_ms / 1000
                if response_sec > threshold:
                    failures.append(
                        DetectedFailure(
                            pattern=FailurePattern.SLOW_RESPONSE,
                            severity="low",
                            evidence=(
                                f"Response at turn {i} took"
                                f" {response_sec:.1f}s"
                                f" (threshold: {threshold}s)"
                            ),
                            turn_index=i,
                            recommendation=(
                                "Optimize tool calls or"
                                " reduce prompt complexity"
                                " for faster responses."
                            ),
                        )
                    )

        return failures
