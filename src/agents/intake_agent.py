"""
Intake agent — first point of contact for all callers.

Greets the caller, identifies their intent, and routes to the
appropriate specialist agent via function tool handoffs.
"""

from __future__ import annotations

import logging
from typing import Union, TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.booking_agent import BookingAgent
    from src.agents.info_agent import InfoAgent
    from src.agents.escalation_agent import EscalationAgent

from src.agents.compat import Agent, function_tool, RunContext

from src.schemas.customer_schema import SessionData
from src.prompts.system_prompts import INTAKE_SYSTEM_PROMPT
from src.tools.customer import lookup_customer
from src.conversation.guardrails import GuardrailPipeline

logger = logging.getLogger(__name__)


class IntakeAgent(Agent):
    """Greeting and intent-routing agent."""

    def __init__(self) -> None:
        super().__init__(
            instructions=INTAKE_SYSTEM_PROMPT,
        )
        self._guardrails = GuardrailPipeline()

    @function_tool()
    async def route_to_booking(self, context: RunContext[SessionData]) -> "BookingAgent":
        """Route the caller to the booking specialist to schedule an appointment."""
        from src.agents.booking_agent import BookingAgent

        context.userdata.intent = "booking"
        logger.info("Routing to BookingAgent")
        return BookingAgent()

    @function_tool()
    async def route_to_info(self, context: RunContext[SessionData]) -> "InfoAgent":
        """Route the caller to the information specialist for service or pricing questions."""
        from src.agents.info_agent import InfoAgent

        context.userdata.intent = "info"
        logger.info("Routing to InfoAgent")
        return InfoAgent()

    @function_tool()
    async def route_to_emergency(self, context: RunContext[SessionData]) -> "EscalationAgent":
        """Route the caller to escalation for an emergency or request to speak to a person."""
        from src.agents.escalation_agent import EscalationAgent

        context.userdata.intent = "emergency"
        logger.info("Routing to EscalationAgent (emergency)")
        return EscalationAgent(reason="emergency")

    @function_tool()
    async def identify_caller(
        self, context: RunContext[SessionData], phone_number: str
    ) -> str:
        """Look up a caller by phone number to personalize the interaction."""
        customer = lookup_customer(phone_number)
        if customer:
            context.userdata.customer_name = customer["name"]
            context.userdata.customer_phone = customer["phone"]
            context.userdata.customer_address = customer.get("address")
            context.userdata.customer_email = customer.get("email")
            logger.info("Returning customer identified: %s", customer["name"])
            return (
                f"Welcome back, {customer['name']}! "
                f"I can see you've used our services before. How can I help you today?"
            )
        return "I don't have a record for that number, but no worries. How can I help you today?"
