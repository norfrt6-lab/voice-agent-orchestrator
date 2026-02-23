"""
Info agent — answers service, pricing, and business questions.

Provides information from the service catalog and can route
to the booking agent if the caller decides to schedule.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.booking_agent import BookingAgent
    from src.agents.escalation_agent import EscalationAgent

from src.agents.compat import Agent, RunContext, function_tool
from src.logging_context import get_call_logger
from src.prompts.system_prompts import INFO_SYSTEM_PROMPT
from src.schemas.customer_schema import SessionData
from src.tools.services import get_all_services, get_service_details, match_service

logger = get_call_logger(__name__)


class InfoAgent(Agent):
    """Service information and FAQ specialist."""

    def __init__(self) -> None:
        super().__init__(
            instructions=INFO_SYSTEM_PROMPT,
        )

    @function_tool()
    async def get_service_info(self, context: RunContext[SessionData], service_query: str) -> str:
        """Look up details about a specific service including pricing and duration."""
        matched_id = match_service(service_query)
        if matched_id:
            details = get_service_details(matched_id)
            if details:
                return (
                    f"Our {details['name']} covers {details['description']} "
                    f"Pricing typically runs {details['price_range']} with a "
                    f"{details['call_out_fee']} call-out fee. "
                    f"Most jobs take {details['typical_duration']}."
                )
        return (
            "I don't have specific details for that service. "
            "Would you like me to connect you with our team for more info?"
        )

    @function_tool()
    async def list_all_services(self, context: RunContext[SessionData]) -> str:
        """List all available services with basic pricing."""
        services = get_all_services()
        lines = [f"{s['name']} ({s['price_range']})" for s in services]
        return "We offer: " + ", ".join(lines) + ". Which service are you interested in?"

    @function_tool()
    async def route_to_booking(self, context: RunContext[SessionData]) -> "BookingAgent":
        """Transfer the caller to the booking specialist to schedule an appointment."""
        from src.agents.booking_agent import BookingAgent

        context.userdata.intent = "booking"
        logger.info("InfoAgent routing to BookingAgent")
        return BookingAgent()

    @function_tool()
    async def escalate_to_human(self, context: RunContext[SessionData]) -> "EscalationAgent":
        """Transfer to a human agent when the question can't be answered automatically."""
        from src.agents.escalation_agent import EscalationAgent

        logger.info("InfoAgent escalating to human")
        return EscalationAgent(reason="complex_question")
