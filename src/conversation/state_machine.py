"""
Finite state machine for deterministic conversation flow control.

Defines 12 conversation states and explicit transitions with triggers.
Every conversation follows a deterministic path through the state graph,
ensuring predictable agent behavior on top of probabilistic LLM outputs.

Usage:
    sm = ConversationStateMachine()
    sm.transition(TransitionTrigger.GREETING_DELIVERED)
    assert sm.current_state == ConversationState.INTENT_DETECTION
"""

import logging
from enum import Enum
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class ConversationState(str, Enum):
    """All possible states in a conversation lifecycle."""
    GREETING = "greeting"
    INTENT_DETECTION = "intent_detection"
    SERVICE_SELECTION = "service_selection"
    SLOT_FILLING = "slot_filling"
    SLOT_CONFIRMATION = "slot_confirmation"
    AVAILABILITY_CHECK = "availability_check"
    BOOKING_CREATION = "booking_creation"
    CONFIRMATION = "confirmation"
    INFO_RESPONSE = "info_response"
    ESCALATION = "escalation"
    FAREWELL = "farewell"
    ERROR_RECOVERY = "error_recovery"


class TransitionTrigger(str, Enum):
    """Events that cause state transitions."""
    GREETING_DELIVERED = "greeting_delivered"
    INTENT_BOOK = "intent_book"
    INTENT_INFO = "intent_info"
    INTENT_EMERGENCY = "intent_emergency"
    INTENT_HUMAN = "intent_human"
    INTENT_UNCLEAR = "intent_unclear"
    SERVICE_CONFIRMED = "service_confirmed"
    ALL_SLOTS_FILLED = "all_slots_filled"
    CALLER_CONFIRMED = "caller_confirmed"
    CALLER_CORRECTED = "caller_corrected"
    TIME_SELECTED = "time_selected"
    NO_AVAILABILITY = "no_availability"
    NO_AVAILABILITY_AT_ALL = "no_availability_at_all"
    BOOKING_SUCCESS = "booking_success"
    BOOKING_FAILED = "booking_failed"
    SATISFIED = "satisfied"
    FOLLOW_UP = "follow_up"
    WANTS_TO_BOOK = "wants_to_book"
    CORRECTION_RECEIVED = "correction_received"
    RECOVERY_FAILED = "recovery_failed"
    HANDOFF_COMPLETE = "handoff_complete"
    GOODBYE = "goodbye"
    MAX_RETRIES = "max_retries"


@dataclass
class Transition:
    """A single valid state transition."""
    from_state: ConversationState
    to_state: ConversationState
    trigger: TransitionTrigger
    guard: Optional[Callable[[], bool]] = None


@dataclass
class StateEntry:
    """Recorded history entry for a state visit."""
    state: ConversationState
    entered_at: datetime
    trigger: Optional[TransitionTrigger] = None


class InvalidTransitionError(Exception):
    """Raised when a transition is not valid from the current state."""


class ConversationStateMachine:
    """
    Deterministic state machine controlling conversation flow.

    Every transition must be explicitly defined. If the LLM attempts
    an action without a corresponding valid transition, it is rejected
    with a clear error indicating what transitions are allowed.
    """

    TRANSITIONS: list[Transition] = [
        # --- Greeting ---
        Transition(ConversationState.GREETING, ConversationState.INTENT_DETECTION,
                   TransitionTrigger.GREETING_DELIVERED),

        # --- Intent routing ---
        Transition(ConversationState.INTENT_DETECTION, ConversationState.SERVICE_SELECTION,
                   TransitionTrigger.INTENT_BOOK),
        Transition(ConversationState.INTENT_DETECTION, ConversationState.INFO_RESPONSE,
                   TransitionTrigger.INTENT_INFO),
        Transition(ConversationState.INTENT_DETECTION, ConversationState.ESCALATION,
                   TransitionTrigger.INTENT_EMERGENCY),
        Transition(ConversationState.INTENT_DETECTION, ConversationState.ESCALATION,
                   TransitionTrigger.INTENT_HUMAN),
        Transition(ConversationState.INTENT_DETECTION, ConversationState.ERROR_RECOVERY,
                   TransitionTrigger.INTENT_UNCLEAR),

        # --- Booking flow ---
        Transition(ConversationState.SERVICE_SELECTION, ConversationState.SLOT_FILLING,
                   TransitionTrigger.SERVICE_CONFIRMED),
        Transition(ConversationState.SLOT_FILLING, ConversationState.SLOT_CONFIRMATION,
                   TransitionTrigger.ALL_SLOTS_FILLED),
        Transition(ConversationState.SLOT_FILLING, ConversationState.ERROR_RECOVERY,
                   TransitionTrigger.MAX_RETRIES),

        # --- Confirmation gate ---
        Transition(ConversationState.SLOT_CONFIRMATION, ConversationState.AVAILABILITY_CHECK,
                   TransitionTrigger.CALLER_CONFIRMED),
        Transition(ConversationState.SLOT_CONFIRMATION, ConversationState.SLOT_FILLING,
                   TransitionTrigger.CALLER_CORRECTED),

        # --- Availability ---
        Transition(ConversationState.AVAILABILITY_CHECK, ConversationState.BOOKING_CREATION,
                   TransitionTrigger.TIME_SELECTED),
        Transition(ConversationState.AVAILABILITY_CHECK, ConversationState.SLOT_FILLING,
                   TransitionTrigger.NO_AVAILABILITY),
        Transition(ConversationState.AVAILABILITY_CHECK, ConversationState.ESCALATION,
                   TransitionTrigger.NO_AVAILABILITY_AT_ALL),

        # --- Booking result ---
        Transition(ConversationState.BOOKING_CREATION, ConversationState.CONFIRMATION,
                   TransitionTrigger.BOOKING_SUCCESS),
        Transition(ConversationState.BOOKING_CREATION, ConversationState.ERROR_RECOVERY,
                   TransitionTrigger.BOOKING_FAILED),

        # --- Post-booking ---
        Transition(ConversationState.CONFIRMATION, ConversationState.FAREWELL,
                   TransitionTrigger.GOODBYE),

        # --- Info flow ---
        Transition(ConversationState.INFO_RESPONSE, ConversationState.INTENT_DETECTION,
                   TransitionTrigger.FOLLOW_UP),
        Transition(ConversationState.INFO_RESPONSE, ConversationState.SERVICE_SELECTION,
                   TransitionTrigger.WANTS_TO_BOOK),
        Transition(ConversationState.INFO_RESPONSE, ConversationState.FAREWELL,
                   TransitionTrigger.SATISFIED),

        # --- Error recovery ---
        Transition(ConversationState.ERROR_RECOVERY, ConversationState.SLOT_FILLING,
                   TransitionTrigger.CORRECTION_RECEIVED),
        Transition(ConversationState.ERROR_RECOVERY, ConversationState.ESCALATION,
                   TransitionTrigger.RECOVERY_FAILED),

        # --- Escalation ---
        Transition(ConversationState.ESCALATION, ConversationState.FAREWELL,
                   TransitionTrigger.HANDOFF_COMPLETE),

        # --- Terminal ---
        Transition(ConversationState.FAREWELL, ConversationState.FAREWELL,
                   TransitionTrigger.GOODBYE),
    ]

    def __init__(self) -> None:
        self._current_state = ConversationState.GREETING
        self._history: list[StateEntry] = [
            StateEntry(state=ConversationState.GREETING, entered_at=datetime.now(timezone.utc))
        ]
        self._error_count: int = 0

    @property
    def current_state(self) -> ConversationState:
        return self._current_state

    @property
    def error_count(self) -> int:
        return self._error_count

    def transition(self, trigger: TransitionTrigger) -> ConversationState:
        """
        Execute a state transition.

        Args:
            trigger: The event triggering the transition.

        Returns:
            The new conversation state.

        Raises:
            InvalidTransitionError: If no valid transition exists.
        """
        for t in self.TRANSITIONS:
            if t.from_state == self._current_state and t.trigger == trigger:
                if t.guard is not None and not t.guard():
                    continue

                old_state = self._current_state
                self._current_state = t.to_state

                self._history.append(StateEntry(
                    state=self._current_state,
                    entered_at=datetime.now(timezone.utc),
                    trigger=trigger,
                ))

                if t.to_state == ConversationState.ERROR_RECOVERY:
                    self._error_count += 1

                logger.debug(
                    "State transition: %s -> %s (trigger: %s)",
                    old_state.value, self._current_state.value, trigger.value,
                )
                return self._current_state

        valid = [t.value for t in self.get_valid_triggers()]
        raise InvalidTransitionError(
            f"No valid transition from '{self._current_state.value}' "
            f"with trigger '{trigger.value}'. Valid triggers: {valid}"
        )

    def get_valid_triggers(self) -> list[TransitionTrigger]:
        """Return all triggers valid from the current state."""
        return [t.trigger for t in self.TRANSITIONS if t.from_state == self._current_state]

    def get_history(self) -> list[StateEntry]:
        """Return the full state transition history."""
        return list(self._history)

    def get_state_trace(self) -> list[str]:
        """Return ordered list of state names visited."""
        return [entry.state.value for entry in self._history]

    def is_terminal(self) -> bool:
        """Check if the conversation has reached a terminal state."""
        return self._current_state == ConversationState.FAREWELL
