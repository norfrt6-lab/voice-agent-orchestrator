"""Tests for import chains and module integrity.

Ensures all public modules can be imported without errors and
that re-exports from __init__.py files work correctly.
"""

import pytest


class TestSchemaImports:
    def test_import_conversation_schema(self):
        from src.schemas.conversation_schema import (
            ConversationTranscript, TranscriptTurn, Speaker, CallOutcome,
        )
        assert Speaker.AGENT == "agent"
        assert CallOutcome.BOOKING_MADE == "booking_made"

    def test_import_booking_schema(self):
        from src.schemas.booking_schema import BookingRequest, BookingResponse
        assert BookingRequest is not None

    def test_import_customer_schema(self):
        from src.schemas.customer_schema import Customer, SessionData
        session = SessionData()
        assert session.customer_name is None
        assert session.error_count == 0


class TestConversationImports:
    def test_import_state_machine(self):
        from src.conversation.state_machine import (
            ConversationStateMachine, ConversationState, TransitionTrigger,
        )
        sm = ConversationStateMachine()
        assert sm.current_state == ConversationState.GREETING

    def test_import_slot_manager(self):
        from src.conversation.slot_manager import SlotManager, SlotStatus
        sm = SlotManager()
        assert sm.slots["customer_name"].status == SlotStatus.EMPTY

    def test_import_guardrails(self):
        from src.conversation.guardrails import (
            GuardrailPipeline, ScopeGuardrail, HallucinationGuardrail,
            PersonaGuardrail, EscalationGuardrail,
        )
        pipeline = GuardrailPipeline()
        assert pipeline.scope is not None


class TestToolImports:
    def test_import_services(self):
        from src.tools.services import get_all_services, match_service, SERVICE_CATALOG
        assert len(SERVICE_CATALOG) >= 6

    def test_import_availability(self):
        from src.tools.availability import check_availability, get_available_dates
        assert callable(check_availability)

    def test_import_booking(self):
        from src.tools.booking import create_booking, cancel_booking, reschedule_booking
        assert callable(create_booking)

    def test_import_customer(self):
        from src.tools.customer import lookup_customer, create_customer
        assert callable(lookup_customer)


class TestPromptImports:
    def test_import_system_prompts(self):
        from src.prompts.system_prompts import (
            INTAKE_SYSTEM_PROMPT, BOOKING_SYSTEM_PROMPT,
            INFO_SYSTEM_PROMPT, ESCALATION_SYSTEM_PROMPT,
        )
        assert "intake agent" in INTAKE_SYSTEM_PROMPT.lower()
        assert "booking specialist" in BOOKING_SYSTEM_PROMPT.lower()

    def test_import_prompt_templates(self):
        from src.prompts.prompt_templates import (
            build_slot_collection_prompt,
            build_confirmation_prompt,
            build_alternative_times_prompt,
        )
        assert callable(build_slot_collection_prompt)


class TestEvalImports:
    def test_import_metrics(self):
        from src.evaluation.metrics import MetricsCalculator, EvalMetrics
        m = EvalMetrics()
        assert m.success_rate == 0.0

    def test_import_failure_detector(self):
        from src.evaluation.failure_detector import FailureDetector, FailurePattern
        assert len(FailurePattern) == 10

    def test_import_auto_improver(self):
        from src.evaluation.auto_improver import AutoImprover, PromptSuggestion
        improver = AutoImprover()
        assert len(improver.FIX_TEMPLATES) == 10

    def test_import_transcript_analyzer(self):
        from src.evaluation.transcript_analyzer import TranscriptAnalyzer
        analyzer = TranscriptAnalyzer()
        assert analyzer is not None

    def test_import_eval_package(self):
        from src.evaluation import (
            TranscriptAnalyzer, FailureDetector, MetricsCalculator, AutoImprover,
        )
        assert TranscriptAnalyzer is not None


class TestAgentRegistry:
    def test_registry_has_all_agents(self):
        from src.agents.registry import get_registered_agents
        agents = get_registered_agents()
        assert "intake" in agents
        assert "booking" in agents
        assert "info" in agents
        assert "escalation" in agents

    def test_create_agent_by_name(self):
        from src.agents.registry import create_agent
        agent = create_agent("intake")
        assert agent is not None

    def test_create_escalation_with_kwargs(self):
        from src.agents.registry import create_agent
        agent = create_agent("escalation", reason="emergency")
        assert agent is not None

    def test_create_unknown_agent_raises(self):
        from src.agents.registry import create_agent
        with pytest.raises(KeyError, match="not registered"):
            create_agent("nonexistent_agent")


class TestConfigImport:
    def test_import_config(self):
        from src.config import settings
        assert settings.business.name is not None
        assert settings.model.llm_model is not None
        assert settings.guardrails.max_slot_retries >= 1


class TestConsoleDemo:
    def test_console_session_imports(self):
        from console_demo import ConsoleSession
        session = ConsoleSession()
        assert session.current_agent == "IntakeAgent"
        assert session.sm.current_state.value == "greeting"
