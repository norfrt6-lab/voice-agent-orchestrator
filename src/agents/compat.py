"""
LiveKit compatibility layer — allows agents to be imported without LiveKit installed.

In production, the real LiveKit Agent base class and decorators are used.
For testing, evaluation, and console demo, lightweight stubs are provided
so the codebase can be explored and tested without installing the full
voice pipeline.
"""

import logging
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

try:
    from livekit.agents import Agent, RunContext, function_tool  # type: ignore[import-untyped]

    LIVEKIT_AVAILABLE = True
    logger.debug("LiveKit agents SDK available")
except ImportError:
    LIVEKIT_AVAILABLE = False
    logger.debug("LiveKit not installed — using compatibility stubs")

    class Agent:  # type: ignore[no-redef]
        """Stub Agent base class when LiveKit is not installed."""

        def __init__(self, instructions: str = "", **kwargs: Any) -> None:
            self.instructions = instructions

    class RunContext(Generic[T]):  # type: ignore[no-redef]
        """Stub RunContext for type hints."""

        def __init__(self) -> None:
            self.userdata: Any = None

    def function_tool(**kwargs: Any) -> Any:  # type: ignore[no-redef]
        """Stub decorator that preserves the method as-is."""

        def decorator(func: Any) -> Any:
            return func

        return decorator
