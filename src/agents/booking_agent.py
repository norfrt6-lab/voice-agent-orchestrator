"""
Booking agent — collects slot data, confirms details, and creates bookings.

This is the most complex agent, implementing the full slot-filling lifecycle:
Collect -> Validate -> Confirm -> Book. Each slot is recorded via its own
function tool so the LLM can be guided one question at a time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.escalation_agent import EscalationAgent

from src.agents.compat import Agent, RunContext, function_tool
from src.conversation.guardrails import GuardrailPipeline
from src.conversation.slot_manager import SlotManager
from src.logging_context import get_call_logger
from src.prompts.prompt_templates import (
    build_alternative_times_prompt,
)
from src.prompts.system_prompts import BOOKING_SYSTEM_PROMPT
from src.schemas.customer_schema import SessionData
from src.tools.availability import check_availability, get_available_dates
from src.tools.booking import create_booking
from src.tools.services import match_service

logger = get_call_logger(__name__)


class BookingAgent(Agent):
    """Slot-filling booking specialist with confirmation gates."""

    def __init__(self) -> None:
        super().__init__(
            instructions=BOOKING_SYSTEM_PROMPT,
        )
        self._slots = SlotManager()
        self._guardrails = GuardrailPipeline()

    # ------------------------------------------------------------------ #
    # Shared slot recording logic
    # ------------------------------------------------------------------ #

    def _record_slot(
        self, context: RunContext[SessionData], slot_name: str, value: str
    ) -> str:
        """Validate, store, and sync a slot value to session data."""
        ok, msg = self._slots.set_slot(slot_name, value)
        if ok:
            setattr(context.userdata, slot_name, self._slots.get_slot_value(slot_name))
        return msg + self._next_slot_hint()

    # ------------------------------------------------------------------ #
    # Slot recording tools — one per field
    # ------------------------------------------------------------------ #

    @function_tool()
    async def record_customer_name(self, context: RunContext[SessionData], name: str) -> str:
        """Record the customer's full name."""
        return self._record_slot(context, "customer_name", name)

    @function_tool()
    async def record_phone_number(self, context: RunContext[SessionData], phone: str) -> str:
        """Record the customer's phone number."""
        ok, msg = self._slots.set_slot("customer_phone", phone)
        if ok:
            context.userdata.customer_phone = self._slots.get_slot_value("customer_phone")
        elif self._slots.has_exceeded_retries("customer_phone"):
            return msg + " Let's move on and we can come back to this."
        return msg + self._next_slot_hint()

    @function_tool()
    async def record_service_type(self, context: RunContext[SessionData], service: str) -> str:
        """Record the type of service the customer needs."""
        matched = match_service(service)
        if matched:
            self._slots.set_slot("service_type", matched)
            context.userdata.service_type = matched
            return f"Got it — {matched} service." + self._next_slot_hint()
        return self._record_slot(context, "service_type", service)

    @function_tool()
    async def record_preferred_date(self, context: RunContext[SessionData], date: str) -> str:
        """Record the customer's preferred appointment date (YYYY-MM-DD format)."""
        return self._record_slot(context, "preferred_date", date)

    @function_tool()
    async def record_preferred_time(self, context: RunContext[SessionData], time: str) -> str:
        """Record the customer's preferred appointment time (HH:MM format)."""
        return self._record_slot(context, "preferred_time", time)

    @function_tool()
    async def record_address(self, context: RunContext[SessionData], address: str) -> str:
        """Record the service address."""
        return self._record_slot(context, "customer_address", address)

    @function_tool()
    async def record_job_description(
        self, context: RunContext[SessionData], description: str
    ) -> str:
        """Record a brief description of the issue or job needed."""
        return self._record_slot(context, "job_description", description)

    # ------------------------------------------------------------------ #
    # Correction tool
    # ------------------------------------------------------------------ #

    _CORRECTABLE_FIELDS: frozenset[str] = frozenset(
        d.name for d in SlotManager.SLOT_DEFINITIONS
    )

    @function_tool()
    async def correct_detail(
        self, context: RunContext[SessionData], field_name: str, new_value: str
    ) -> str:
        """Correct a previously recorded detail.

        field_name is one of: customer_name, customer_phone,
        service_type, preferred_date, preferred_time,
        customer_address, job_description.
        """
        if field_name not in self._CORRECTABLE_FIELDS:
            valid = ", ".join(sorted(self._CORRECTABLE_FIELDS))
            return f"Unknown field '{field_name}'. Valid: {valid}."
        ok, msg = self._slots.correct_slot(field_name, new_value)
        if ok:
            setattr(context.userdata, field_name, self._slots.get_slot_value(field_name))
            val = self._slots.get_slot_value(field_name)
            label = field_name.replace('_', ' ')
            return f"Updated {label} to {val}."
        return msg

    # ------------------------------------------------------------------ #
    # Confirmation gate
    # ------------------------------------------------------------------ #

    @function_tool()
    async def confirm_booking_details(self, context: RunContext[SessionData]) -> str:
        """Read back all collected details for confirmation.

        Call this when all required slots are filled.
        """
        if not self._slots.all_required_filled():
            missing = self._slots.get_missing_slots()
            names = [s.display_name for s in missing]
            return f"Still need: {', '.join(names)}. Please collect these first."
        summary = self._slots.get_confirmation_summary()
        return summary + '\n\nPlease ask: "Does everything sound correct?"'

    # ------------------------------------------------------------------ #
    # Availability check + booking
    # ------------------------------------------------------------------ #

    @function_tool()
    async def check_and_book(self, context: RunContext[SessionData]) -> str:
        """Check availability and create the booking.

        Only call AFTER the caller explicitly confirms details.
        """
        if not self._slots.all_required_filled():
            return "Cannot book — required information is still missing."

        # Mark all as confirmed since the caller approved
        self._slots.confirm_all()

        slot_data = self._slots.to_dict()
        service = slot_data.get("service_type", "general handyman")
        date = slot_data.get("preferred_date", "")
        time = slot_data.get("preferred_time")

        # Check availability
        avail = check_availability(service, date, time)

        if not avail["available"]:
            # Offer alternatives
            alt_dates = get_available_dates(service, limit=3)
            if alt_dates:
                alt_slots = [
                    {"date": d["date"], "time": "09:00", "technician": "Available tech"}
                    for d in alt_dates
                ]
                return build_alternative_times_prompt(date, time or "any", alt_slots)
            return (
                f"Unfortunately, there's no availability for {service} in the coming days. "
                "Would you like me to put you on a waitlist, or connect you with our team?"
            )

        # Book with the first available slot
        selected = avail["slots"][0]
        result = create_booking(
            name=slot_data.get("customer_name", ""),
            phone=slot_data.get("customer_phone", ""),
            service=service,
            date=selected["date"],
            time=selected["time"],
            address=slot_data.get("customer_address", ""),
            description=slot_data.get("job_description"),
            technician=selected.get("technician"),
        )

        if result["success"]:
            context.userdata.booking_ref = result["booking_ref"]
            logger.info("Booking created: %s", result["booking_ref"])
            return str(result["message"])

        return "Something went wrong creating the booking. Let me connect you with our team."

    # ------------------------------------------------------------------ #
    # Escalation handoff
    # ------------------------------------------------------------------ #

    @function_tool()
    async def escalate_to_human(self, context: RunContext[SessionData]) -> "EscalationAgent":
        """Transfer to a human agent.

        Use when the caller is frustrated or the system
        cannot resolve their issue.
        """
        from src.agents.escalation_agent import EscalationAgent

        logger.info("BookingAgent escalating to human")
        return EscalationAgent(reason="booking_difficulty")

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _next_slot_hint(self) -> str:
        """Generate a hint about what to ask next."""
        next_slot = self._slots.get_next_empty_slot()
        if next_slot:
            return f" Now ask for their {next_slot.display_name}."
        return " All details collected — use confirm_booking_details to read them back."
