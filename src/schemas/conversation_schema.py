"""Conversation transcript schemas for evaluation and analysis."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class Speaker(str, Enum):
    AGENT = "agent"
    USER = "user"
    SYSTEM = "system"


class CallOutcome(str, Enum):
    BOOKING_MADE = "booking_made"
    BOOKING_FAILED = "booking_failed"
    INFO_PROVIDED = "info_provided"
    ESCALATED = "escalated"
    CALLER_HUNG_UP = "caller_hung_up"
    ERROR = "error"


class TranscriptTurn(BaseModel):
    """A single turn in a conversation transcript."""

    speaker: Speaker
    text: str
    timestamp: float
    confidence: Optional[float] = None
    tool_calls: list[str] = Field(default_factory=list)
    agent_id: Optional[str] = None
    response_time_ms: Optional[float] = None


class ConversationTranscript(BaseModel):
    """Complete conversation record for evaluation."""

    call_id: str
    timestamp: datetime
    duration_seconds: float
    turns: list[TranscriptTurn]
    outcome: CallOutcome
    slots_collected: dict[str, str] = Field(default_factory=dict)
    slots_confirmed: bool = False
    agents_used: list[str] = Field(default_factory=list)
    handoff_count: int = 0
    error_count: int = 0
    escalation_reason: Optional[str] = None
    metadata: Optional[dict[str, Any]] = None
