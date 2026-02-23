"""Tests for the conversation state machine."""

import pytest

from src.conversation.state_machine import (
    ConversationStateMachine,
    ConversationState,
    TransitionTrigger,
    InvalidTransitionError,
)


class TestInitialState:
    def test_starts_in_greeting(self, state_machine):
        assert state_machine.current_state == ConversationState.GREETING

    def test_initial_history_has_one_entry(self, state_machine):
        assert len(state_machine.get_history()) == 1

    def test_initial_error_count_is_zero(self, state_machine):
        assert state_machine.error_count == 0

    def test_not_terminal_at_start(self, state_machine):
        assert not state_machine.is_terminal()


class TestGreetingTransitions:
    def test_greeting_to_intent_detection(self, state_machine):
        new = state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        assert new == ConversationState.INTENT_DETECTION

    def test_invalid_trigger_from_greeting(self, state_machine):
        with pytest.raises(InvalidTransitionError):
            state_machine.transition(TransitionTrigger.INTENT_BOOK)


class TestIntentRouting:
    def test_intent_book_goes_to_service_selection(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        new = state_machine.transition(TransitionTrigger.INTENT_BOOK)
        assert new == ConversationState.SERVICE_SELECTION

    def test_intent_info_goes_to_info_response(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        new = state_machine.transition(TransitionTrigger.INTENT_INFO)
        assert new == ConversationState.INFO_RESPONSE

    def test_intent_emergency_goes_to_escalation(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        new = state_machine.transition(TransitionTrigger.INTENT_EMERGENCY)
        assert new == ConversationState.ESCALATION

    def test_intent_human_goes_to_escalation(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        new = state_machine.transition(TransitionTrigger.INTENT_HUMAN)
        assert new == ConversationState.ESCALATION

    def test_intent_unclear_goes_to_error_recovery(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        new = state_machine.transition(TransitionTrigger.INTENT_UNCLEAR)
        assert new == ConversationState.ERROR_RECOVERY


class TestBookingFlow:
    def test_service_confirmed_to_slot_filling(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        state_machine.transition(TransitionTrigger.INTENT_BOOK)
        new = state_machine.transition(TransitionTrigger.SERVICE_CONFIRMED)
        assert new == ConversationState.SLOT_FILLING

    def test_all_slots_filled_to_confirmation(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        state_machine.transition(TransitionTrigger.INTENT_BOOK)
        state_machine.transition(TransitionTrigger.SERVICE_CONFIRMED)
        new = state_machine.transition(TransitionTrigger.ALL_SLOTS_FILLED)
        assert new == ConversationState.SLOT_CONFIRMATION

    def test_caller_confirmed_to_availability(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        state_machine.transition(TransitionTrigger.INTENT_BOOK)
        state_machine.transition(TransitionTrigger.SERVICE_CONFIRMED)
        state_machine.transition(TransitionTrigger.ALL_SLOTS_FILLED)
        new = state_machine.transition(TransitionTrigger.CALLER_CONFIRMED)
        assert new == ConversationState.AVAILABILITY_CHECK

    def test_caller_corrected_returns_to_slot_filling(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        state_machine.transition(TransitionTrigger.INTENT_BOOK)
        state_machine.transition(TransitionTrigger.SERVICE_CONFIRMED)
        state_machine.transition(TransitionTrigger.ALL_SLOTS_FILLED)
        new = state_machine.transition(TransitionTrigger.CALLER_CORRECTED)
        assert new == ConversationState.SLOT_FILLING

    def test_time_selected_to_booking_creation(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        state_machine.transition(TransitionTrigger.INTENT_BOOK)
        state_machine.transition(TransitionTrigger.SERVICE_CONFIRMED)
        state_machine.transition(TransitionTrigger.ALL_SLOTS_FILLED)
        state_machine.transition(TransitionTrigger.CALLER_CONFIRMED)
        new = state_machine.transition(TransitionTrigger.TIME_SELECTED)
        assert new == ConversationState.BOOKING_CREATION

    def test_booking_success_to_confirmation(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        state_machine.transition(TransitionTrigger.INTENT_BOOK)
        state_machine.transition(TransitionTrigger.SERVICE_CONFIRMED)
        state_machine.transition(TransitionTrigger.ALL_SLOTS_FILLED)
        state_machine.transition(TransitionTrigger.CALLER_CONFIRMED)
        state_machine.transition(TransitionTrigger.TIME_SELECTED)
        new = state_machine.transition(TransitionTrigger.BOOKING_SUCCESS)
        assert new == ConversationState.CONFIRMATION

    def test_happy_path_to_farewell(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        state_machine.transition(TransitionTrigger.INTENT_BOOK)
        state_machine.transition(TransitionTrigger.SERVICE_CONFIRMED)
        state_machine.transition(TransitionTrigger.ALL_SLOTS_FILLED)
        state_machine.transition(TransitionTrigger.CALLER_CONFIRMED)
        state_machine.transition(TransitionTrigger.TIME_SELECTED)
        state_machine.transition(TransitionTrigger.BOOKING_SUCCESS)
        new = state_machine.transition(TransitionTrigger.GOODBYE)
        assert new == ConversationState.FAREWELL
        assert state_machine.is_terminal()


class TestErrorRecovery:
    def test_max_retries_goes_to_error_recovery(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        state_machine.transition(TransitionTrigger.INTENT_BOOK)
        state_machine.transition(TransitionTrigger.SERVICE_CONFIRMED)
        new = state_machine.transition(TransitionTrigger.MAX_RETRIES)
        assert new == ConversationState.ERROR_RECOVERY

    def test_correction_received_returns_to_slot_filling(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        state_machine.transition(TransitionTrigger.INTENT_BOOK)
        state_machine.transition(TransitionTrigger.SERVICE_CONFIRMED)
        state_machine.transition(TransitionTrigger.MAX_RETRIES)
        new = state_machine.transition(TransitionTrigger.CORRECTION_RECEIVED)
        assert new == ConversationState.SLOT_FILLING

    def test_recovery_failed_goes_to_escalation(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        state_machine.transition(TransitionTrigger.INTENT_BOOK)
        state_machine.transition(TransitionTrigger.SERVICE_CONFIRMED)
        state_machine.transition(TransitionTrigger.MAX_RETRIES)
        new = state_machine.transition(TransitionTrigger.RECOVERY_FAILED)
        assert new == ConversationState.ESCALATION

    def test_error_count_increments_on_recovery(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        state_machine.transition(TransitionTrigger.INTENT_BOOK)
        state_machine.transition(TransitionTrigger.SERVICE_CONFIRMED)
        state_machine.transition(TransitionTrigger.MAX_RETRIES)
        assert state_machine.error_count == 1


class TestInfoFlow:
    def test_info_follow_up_returns_to_intent(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        state_machine.transition(TransitionTrigger.INTENT_INFO)
        new = state_machine.transition(TransitionTrigger.FOLLOW_UP)
        assert new == ConversationState.INTENT_DETECTION

    def test_info_wants_to_book_goes_to_service_selection(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        state_machine.transition(TransitionTrigger.INTENT_INFO)
        new = state_machine.transition(TransitionTrigger.WANTS_TO_BOOK)
        assert new == ConversationState.SERVICE_SELECTION

    def test_info_satisfied_goes_to_farewell(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        state_machine.transition(TransitionTrigger.INTENT_INFO)
        new = state_machine.transition(TransitionTrigger.SATISFIED)
        assert new == ConversationState.FAREWELL


class TestHistory:
    def test_history_tracks_all_transitions(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        state_machine.transition(TransitionTrigger.INTENT_BOOK)
        history = state_machine.get_history()
        assert len(history) == 3  # initial + 2 transitions

    def test_state_trace_returns_state_names(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        state_machine.transition(TransitionTrigger.INTENT_BOOK)
        trace = state_machine.get_state_trace()
        assert trace == ["greeting", "intent_detection", "service_selection"]

    def test_valid_triggers_from_greeting(self, state_machine):
        triggers = state_machine.get_valid_triggers()
        assert triggers == [TransitionTrigger.GREETING_DELIVERED]

    def test_valid_triggers_from_intent_detection(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        triggers = state_machine.get_valid_triggers()
        assert len(triggers) == 5  # book, info, emergency, human, unclear


class TestAvailabilityTransitions:
    def test_no_availability_returns_to_slot_filling(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        state_machine.transition(TransitionTrigger.INTENT_BOOK)
        state_machine.transition(TransitionTrigger.SERVICE_CONFIRMED)
        state_machine.transition(TransitionTrigger.ALL_SLOTS_FILLED)
        state_machine.transition(TransitionTrigger.CALLER_CONFIRMED)
        new = state_machine.transition(TransitionTrigger.NO_AVAILABILITY)
        assert new == ConversationState.SLOT_FILLING

    def test_no_availability_at_all_goes_to_escalation(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        state_machine.transition(TransitionTrigger.INTENT_BOOK)
        state_machine.transition(TransitionTrigger.SERVICE_CONFIRMED)
        state_machine.transition(TransitionTrigger.ALL_SLOTS_FILLED)
        state_machine.transition(TransitionTrigger.CALLER_CONFIRMED)
        new = state_machine.transition(TransitionTrigger.NO_AVAILABILITY_AT_ALL)
        assert new == ConversationState.ESCALATION

    def test_booking_failed_goes_to_error_recovery(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        state_machine.transition(TransitionTrigger.INTENT_BOOK)
        state_machine.transition(TransitionTrigger.SERVICE_CONFIRMED)
        state_machine.transition(TransitionTrigger.ALL_SLOTS_FILLED)
        state_machine.transition(TransitionTrigger.CALLER_CONFIRMED)
        state_machine.transition(TransitionTrigger.TIME_SELECTED)
        new = state_machine.transition(TransitionTrigger.BOOKING_FAILED)
        assert new == ConversationState.ERROR_RECOVERY


class TestEscalationFlow:
    def test_handoff_complete_goes_to_farewell(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        state_machine.transition(TransitionTrigger.INTENT_EMERGENCY)
        new = state_machine.transition(TransitionTrigger.HANDOFF_COMPLETE)
        assert new == ConversationState.FAREWELL

    def test_farewell_is_terminal(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        state_machine.transition(TransitionTrigger.INTENT_EMERGENCY)
        state_machine.transition(TransitionTrigger.HANDOFF_COMPLETE)
        assert state_machine.is_terminal()

    def test_farewell_self_transition(self, state_machine):
        state_machine.transition(TransitionTrigger.GREETING_DELIVERED)
        state_machine.transition(TransitionTrigger.INTENT_EMERGENCY)
        state_machine.transition(TransitionTrigger.HANDOFF_COMPLETE)
        new = state_machine.transition(TransitionTrigger.GOODBYE)
        assert new == ConversationState.FAREWELL
