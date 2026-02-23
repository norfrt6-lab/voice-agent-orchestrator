"""Integration tests: state machine + slot manager + guardrails together."""

import pytest

from src.conversation.state_machine import (
    ConversationStateMachine,
    ConversationState,
    TransitionTrigger,
    InvalidTransitionError,
)
from src.conversation.slot_manager import SlotManager, SlotStatus
from src.conversation.guardrails import GuardrailPipeline
from src.tools.services import match_service, get_service_details
from src.tools.availability import check_availability, get_available_dates
from src.tools.booking import create_booking, cancel_booking, reschedule_booking, get_booking
from src.tools.customer import lookup_customer, create_customer


class TestFullBookingFlow:
    """Simulate a complete booking from greeting to farewell."""

    def test_happy_path_integration(self):
        sm = ConversationStateMachine()
        slots = SlotManager()
        guardrails = GuardrailPipeline()

        # Greeting
        sm.transition(TransitionTrigger.GREETING_DELIVERED)
        assert sm.current_state == ConversationState.INTENT_DETECTION

        # Check user input through guardrails
        violations = guardrails.check_user_input("I need to book a plumber")
        assert len(violations) == 0

        # Intent: booking
        sm.transition(TransitionTrigger.INTENT_BOOK)
        sm.transition(TransitionTrigger.SERVICE_CONFIRMED)

        # Fill all slots
        ok, _ = slots.set_slot("customer_name", "John Smith")
        assert ok
        ok, _ = slots.set_slot("customer_phone", "0412345678")
        assert ok
        ok, _ = slots.set_slot("service_type", "plumbing")
        assert ok
        ok, _ = slots.set_slot("preferred_date", "2025-03-18")
        assert ok
        ok, _ = slots.set_slot("preferred_time", "10:00")
        assert ok
        ok, _ = slots.set_slot("customer_address", "42 Oak Ave, Richmond VIC 3121")
        assert ok

        assert slots.all_required_filled()

        # Transition to confirmation
        sm.transition(TransitionTrigger.ALL_SLOTS_FILLED)
        assert sm.current_state == ConversationState.SLOT_CONFIRMATION

        # Confirmation summary
        summary = slots.get_confirmation_summary()
        assert "John Smith" in summary

        # Caller confirms
        slots.confirm_all()
        assert slots.all_confirmed()
        sm.transition(TransitionTrigger.CALLER_CONFIRMED)

        # Check availability and book
        sm.transition(TransitionTrigger.TIME_SELECTED)
        result = create_booking(
            name="John Smith",
            phone="0412345678",
            service="plumbing",
            date="2025-03-18",
            time="10:00",
            address="42 Oak Ave, Richmond VIC 3121",
        )
        assert result["success"]
        assert result["booking_ref"].startswith("BK-")

        sm.transition(TransitionTrigger.BOOKING_SUCCESS)
        sm.transition(TransitionTrigger.GOODBYE)
        assert sm.is_terminal()

    def test_correction_flow_integration(self):
        slots = SlotManager()

        slots.set_slot("customer_name", "Emma Watson")
        slots.correct_slot("customer_name", "Emma Wilson")
        assert slots.get_slot_value("customer_name") == "Emma Wilson"
        assert slots.slots["customer_name"].attempts == 2

        slots.set_slot("customer_phone", "0412345678")
        slots.set_slot("service_type", "plumbing")
        slots.set_slot("preferred_date", "2025-03-18")
        slots.set_slot("preferred_time", "10:00")
        slots.set_slot("customer_address", "42 Oak Ave, Richmond VIC 3121")

        assert slots.all_required_filled()
        summary = slots.get_confirmation_summary()
        assert "Emma Wilson" in summary


class TestEmergencyEscalation:
    def test_emergency_bypasses_booking(self):
        sm = ConversationStateMachine()
        guardrails = GuardrailPipeline()

        sm.transition(TransitionTrigger.GREETING_DELIVERED)

        violations = guardrails.check_user_input("I have a gas leak!")
        assert len(violations) > 0
        assert any(v.severity == "escalate" for v in violations)

        sm.transition(TransitionTrigger.INTENT_EMERGENCY)
        assert sm.current_state == ConversationState.ESCALATION

        sm.transition(TransitionTrigger.HANDOFF_COMPLETE)
        assert sm.is_terminal()


class TestServiceTools:
    def test_match_service_alias(self):
        assert match_service("I need a plumber") == "plumbing"

    def test_match_service_direct(self):
        assert match_service("electrical") == "electrical"

    def test_match_service_unknown(self):
        assert match_service("landscaping") is None

    def test_get_service_details_found(self):
        details = get_service_details("plumbing")
        assert details is not None
        assert details["name"] == "Plumbing Service"
        assert "$" in details["price_range"]

    def test_get_service_details_not_found(self):
        details = get_service_details("landscaping")
        assert details is None


class TestBookingTools:
    def test_create_and_retrieve_booking(self):
        result = create_booking(
            name="Test User",
            phone="0400000000",
            service="plumbing",
            date="2025-04-01",
            time="09:00",
            address="123 Test St",
        )
        assert result["success"]
        ref = result["booking_ref"]

        booking = get_booking(ref)
        assert booking is not None
        assert booking["customer_name"] == "Test User"
        assert booking["status"] == "confirmed"

    def test_cancel_booking(self):
        result = create_booking(
            name="Cancel Test",
            phone="0400000001",
            service="electrical",
            date="2025-04-02",
            time="10:00",
            address="456 Test St",
        )
        ref = result["booking_ref"]

        cancel_result = cancel_booking(ref)
        assert cancel_result["success"]

        booking = get_booking(ref)
        assert booking["status"] == "cancelled"

    def test_cancel_nonexistent_booking(self):
        result = cancel_booking("BK-NONEXIST")
        assert result["success"] is False

    def test_reschedule_booking(self):
        result = create_booking(
            name="Resched Test",
            phone="0400000002",
            service="hvac",
            date="2025-04-03",
            time="11:00",
            address="789 Test St",
        )
        ref = result["booking_ref"]

        resched_result = reschedule_booking(ref, "2025-04-10", "14:00")
        assert resched_result["success"]

    def test_reschedule_nonexistent_booking(self):
        result = reschedule_booking("BK-NONEXIST", "2025-04-10", "14:00")
        assert result["success"] is False


class TestCustomerTools:
    def test_lookup_existing_customer(self):
        customer = lookup_customer("0412345678")
        assert customer is not None
        assert customer["name"] == "John Smith"

    def test_lookup_with_spaces(self):
        customer = lookup_customer("0412 345 678")
        assert customer is not None
        assert customer["name"] == "John Smith"

    def test_lookup_with_international_prefix(self):
        customer = lookup_customer("+61412345678")
        assert customer is not None
        assert customer["name"] == "John Smith"

    def test_lookup_nonexistent_customer(self):
        customer = lookup_customer("0400000000")
        assert customer is None

    def test_create_customer(self):
        customer = create_customer("New Person", "0499888777", email="new@test.com")
        assert customer["name"] == "New Person"
        assert customer["phone"] == "0499888777"
        assert customer["previous_bookings"] == 0

        # Should now be findable
        found = lookup_customer("0499888777")
        assert found is not None
        assert found["name"] == "New Person"


class TestAvailabilityTools:
    def test_get_available_dates(self):
        dates = get_available_dates("plumbing", limit=3)
        assert len(dates) <= 3
        assert all("date" in d for d in dates)

    def test_check_availability_unavailable_date(self):
        result = check_availability("plumbing", "1999-01-01")
        assert result["available"] is False
        assert result["next_available"] is not None
