"""
Escalation agent — handles emergencies, frustrated callers, and human handoff.

This is the terminal agent for conversations that cannot be resolved
automatically. It provides appropriate guidance and ensures proper
handoff documentation.
"""

from src.agents.compat import Agent, RunContext, function_tool
from src.config import settings
from src.logging_context import get_call_logger
from src.prompts.system_prompts import ESCALATION_SYSTEM_PROMPT
from src.schemas.customer_schema import SessionData

logger = get_call_logger(__name__)


class EscalationAgent(Agent):
    """Emergency and human handoff handler."""

    def __init__(self, reason: str = "general") -> None:
        super().__init__(
            instructions=ESCALATION_SYSTEM_PROMPT,
        )
        self._reason = reason

    @function_tool()
    async def complete_handoff(self, context: RunContext[SessionData]) -> str:
        """Complete the escalation handoff and provide the caller with next steps."""
        biz = settings.business

        if self._reason == "emergency":
            logger.info("Emergency handoff completed")
            return (
                f"For immediate emergencies, please call our emergency line at "
                f"{biz.emergency_line}. If you're in danger, call 000 immediately. "
                f"A team member will also call you back within {biz.callback_sla_minutes} minutes."
            )

        logger.info("Standard handoff completed (reason: %s)", self._reason)
        return (
            f"I've noted your details and a team member will call you back within "
            f"{biz.callback_sla_minutes} minutes. Is there anything else you need right now?"
        )

    @function_tool()
    async def record_callback_number(self, context: RunContext[SessionData], phone: str) -> str:
        """Record or confirm the best number for a callback."""
        context.userdata.customer_phone = phone
        logger.info("Callback number recorded: %s", phone)
        return (
            f"Got it, we'll call you back at {phone} within "
            f"{settings.business.callback_sla_minutes} minutes."
        )

    @function_tool()
    async def provide_emergency_guidance(
        self, context: RunContext[SessionData], situation: str
    ) -> str:
        """Provide immediate safety guidance for emergency situations."""
        situation_lower = situation.lower()

        if "gas" in situation_lower:
            return (
                "If you smell gas, leave the area immediately and don't operate any electrical "
                f"switches. Call our emergency line at {settings.business.emergency_line} "
                "from outside, and if the smell is strong, call 000."
            )

        if "flood" in situation_lower or "water" in situation_lower or "burst" in situation_lower:
            return (
                "Please turn off your main water supply if you can safely reach it. "
                f"Then call our emergency line at {settings.business.emergency_line}. "
                "We'll have someone out to you as quickly as possible."
            )

        if "electric" in situation_lower or "spark" in situation_lower:
            return (
                "Don't touch anything electrical, and switch off your "
                "mains power at the switchboard if safe to do so. "
                "Call our emergency line at "
                f"{settings.business.emergency_line} "
                "and if anyone is injured, call 000 immediately."
            )

        return (
            f"Please call our emergency line at {settings.business.emergency_line} for immediate "
            f"assistance. If anyone is in danger, call 000 first."
        )
