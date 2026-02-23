"""Shared test fixtures and helpers."""

from datetime import datetime
from typing import Optional

import pytest

from src.conversation.guardrails import GuardrailPipeline
from src.conversation.slot_manager import SlotManager
from src.conversation.state_machine import ConversationStateMachine
from src.schemas.conversation_schema import (
    CallOutcome,
    ConversationTranscript,
    Speaker,
    TranscriptTurn,
)


@pytest.fixture
def state_machine():
    return ConversationStateMachine()


@pytest.fixture
def slot_manager():
    return SlotManager()


@pytest.fixture
def guardrail_pipeline():
    return GuardrailPipeline()


def make_turn(
    speaker: Speaker,
    text: str,
    timestamp: float = 0.0,
    agent_id: Optional[str] = None,
    tool_calls: Optional[list[str]] = None,
    response_time_ms: Optional[float] = None,
) -> TranscriptTurn:
    """Helper to create a TranscriptTurn."""
    return TranscriptTurn(
        speaker=speaker,
        text=text,
        timestamp=timestamp,
        agent_id=agent_id,
        tool_calls=tool_calls or [],
        response_time_ms=response_time_ms,
    )


def make_transcript(
    call_id: str = "TEST-001",
    outcome: CallOutcome = CallOutcome.BOOKING_MADE,
    turns: Optional[list[TranscriptTurn]] = None,
    slots: Optional[dict[str, str]] = None,
    agents_used: Optional[list[str]] = None,
    error_count: int = 0,
    duration: float = 120.0,
    metadata: Optional[dict] = None,
) -> ConversationTranscript:
    """Helper to create a ConversationTranscript with sensible defaults."""
    if turns is None:
        turns = [
            make_turn(Speaker.AGENT, "Hello, how can I help?", 0.0, "IntakeAgent"),
            make_turn(Speaker.USER, "I need to book a plumber.", 3.0),
            make_turn(Speaker.AGENT, "Let me help with that.", 5.0, "BookingAgent"),
        ]
    return ConversationTranscript(
        call_id=call_id,
        timestamp=datetime(2025, 3, 15, 10, 0),
        duration_seconds=duration,
        turns=turns,
        outcome=outcome,
        slots_collected=slots or {},
        agents_used=agents_used or ["IntakeAgent", "BookingAgent"],
        error_count=error_count,
        metadata=metadata,
    )


def make_transcript_with_turns(
    turn_texts: list[tuple[str, str]],
    outcome: CallOutcome = CallOutcome.BOOKING_MADE,
    **kwargs,
) -> ConversationTranscript:
    """Create a transcript from a list of (speaker, text) tuples."""
    turns = []
    for i, (spk, text) in enumerate(turn_texts):
        speaker = Speaker.AGENT if spk == "agent" else Speaker.USER
        turns.append(make_turn(speaker, text, float(i * 3)))
    return make_transcript(turns=turns, outcome=outcome, **kwargs)
