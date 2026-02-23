"""
Agent registry — centralized agent creation without circular imports.

Instead of agents importing each other directly, all agent types are
registered here. Handoff methods resolve agent classes through the
registry at runtime, breaking the import cycle.

This is the senior-level pattern for multi-agent systems where agents
need to hand off to each other without tightly coupling their modules.
"""

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

_AGENT_REGISTRY: dict[str, Callable[..., Any]] = {}


def register_agent(name: str, factory: Callable[..., Any]) -> None:
    """Register an agent factory by name."""
    _AGENT_REGISTRY[name] = factory
    logger.debug("Agent registered: %s", name)


def create_agent(name: str, **kwargs: Any) -> Any:
    """Create an agent instance by registered name.

    Raises:
        KeyError: If the agent name is not registered.
    """
    if name not in _AGENT_REGISTRY:
        registered = list(_AGENT_REGISTRY.keys())
        raise KeyError(f"Agent '{name}' not registered. Available: {registered}")
    return _AGENT_REGISTRY[name](**kwargs)


def get_registered_agents() -> list[str]:
    """Return names of all registered agents."""
    return list(_AGENT_REGISTRY.keys())


def _auto_register() -> None:
    """Auto-register all built-in agents. Called once at import time."""
    from src.agents.booking_agent import BookingAgent
    from src.agents.escalation_agent import EscalationAgent
    from src.agents.info_agent import InfoAgent
    from src.agents.intake_agent import IntakeAgent

    register_agent("intake", IntakeAgent)
    register_agent("booking", BookingAgent)
    register_agent("info", InfoAgent)
    register_agent("escalation", EscalationAgent)


_auto_register()
