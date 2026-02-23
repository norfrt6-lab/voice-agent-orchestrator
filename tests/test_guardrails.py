"""Tests for the multi-layer guardrail system."""

from src.conversation.guardrails import (
    EscalationGuardrail,
    HallucinationGuardrail,
    PersonaGuardrail,
    ScopeGuardrail,
)


class TestScopeGuardrail:
    def setup_method(self):
        self.guard = ScopeGuardrail()

    def test_valid_service_exact_match(self):
        result = self.guard.check_service_scope("plumbing")
        assert result.passed is True

    def test_valid_service_partial_match(self):
        result = self.guard.check_service_scope("plumbing repair")
        assert result.passed is True

    def test_valid_service_case_insensitive(self):
        result = self.guard.check_service_scope("ELECTRICAL")
        assert result.passed is True

    def test_invalid_service(self):
        result = self.guard.check_service_scope("landscaping")
        assert result.passed is False
        assert result.violation_type == "out_of_scope_service"

    def test_out_of_scope_topic(self):
        result = self.guard.check_topic_scope("Can you give me financial advice?")
        assert result.passed is False
        assert result.violation_type == "out_of_scope_topic"
        assert result.severity == "block"

    def test_in_scope_topic(self):
        result = self.guard.check_topic_scope("I need help with my kitchen sink")
        assert result.passed is True

    def test_competitor_topic_blocked(self):
        result = self.guard.check_topic_scope("What about your competitor down the street?")
        assert result.passed is False

    def test_medical_advice_blocked(self):
        result = self.guard.check_topic_scope("Can you give me medical advice about my injury?")
        assert result.passed is False


class TestHallucinationGuardrail:
    def setup_method(self):
        self.guard = HallucinationGuardrail()

    def test_clean_response_passes(self):
        result = self.guard.check_response("We can schedule your plumbing appointment for Tuesday.")
        assert result.passed is True

    def test_guarantee_claim_blocked(self):
        result = self.guard.check_response("We guarantee all our work for 5 years.")
        assert result.passed is False
        assert result.violation_type == "potential_hallucination"

    def test_warranty_claim_blocked(self):
        result = self.guard.check_response("All our services come with a warranty.")
        assert result.passed is False

    def test_award_winning_blocked(self):
        result = self.guard.check_response("We are an award-winning company.")
        assert result.passed is False

    def test_cheapest_claim_blocked(self):
        result = self.guard.check_response("We offer the cheapest prices in town.")
        assert result.passed is False

    def test_fully_licensed_blocked(self):
        result = self.guard.check_response("All our technicians are fully licensed.")
        assert result.passed is False


class TestPersonaGuardrail:
    def setup_method(self):
        self.guard = PersonaGuardrail()

    def test_normal_response_passes(self):
        result = self.guard.check_persona("Sure, I can help you book that appointment.")
        assert result.passed is True

    def test_ai_self_reference_blocked(self):
        result = self.guard.check_persona("As an AI, I don't have personal opinions.")
        assert result.passed is False
        assert result.violation_type == "persona_break"

    def test_language_model_reference_blocked(self):
        result = self.guard.check_persona("As a language model, I can only process text.")
        assert result.passed is False

    def test_unable_to_blocked(self):
        result = self.guard.check_persona("I'm unable to help with that request.")
        assert result.passed is False

    def test_no_formatting_violations_passes(self):
        result = self.guard.check_formatting("We offer plumbing and electrical services.")
        assert result.passed is True

    def test_markdown_bullet_blocked(self):
        result = self.guard.check_formatting("Our services include:\n- Plumbing\n- Electrical")
        assert result.passed is False
        assert result.violation_type == "formatting_violation"

    def test_markdown_heading_blocked(self):
        result = self.guard.check_formatting("## Our Services")
        assert result.passed is False

    def test_code_block_blocked(self):
        result = self.guard.check_formatting("Here's the code: ```python print('hi')```")
        assert result.passed is False

    def test_bold_markdown_blocked(self):
        result = self.guard.check_formatting("This is **very important**.")
        assert result.passed is False


class TestEscalationGuardrail:
    def setup_method(self):
        self.guard = EscalationGuardrail()

    def test_normal_message_passes(self):
        result = self.guard.check_escalation_needed("I need to book a plumber for Tuesday.")
        assert result.passed is True

    def test_gas_leak_triggers_emergency(self):
        result = self.guard.check_escalation_needed("I think I have a gas leak!")
        assert result.passed is False
        assert result.violation_type == "emergency"
        assert result.severity == "escalate"

    def test_flooding_triggers_emergency(self):
        result = self.guard.check_escalation_needed("My house is flooding!")
        assert result.passed is False
        assert result.violation_type == "emergency"

    def test_burst_pipe_triggers_emergency(self):
        result = self.guard.check_escalation_needed("I have a burst pipe!")
        assert result.passed is False

    def test_carbon_monoxide_triggers_emergency(self):
        result = self.guard.check_escalation_needed("I'm worried about carbon monoxide.")
        assert result.passed is False

    def test_frustration_manager_request(self):
        result = self.guard.check_escalation_needed("Let me speak to a manager.")
        assert result.passed is False
        assert result.violation_type == "caller_frustration"

    def test_frustration_real_person(self):
        result = self.guard.check_escalation_needed("I want to speak to a real person.")
        assert result.passed is False

    def test_frustration_unacceptable(self):
        result = self.guard.check_escalation_needed("This is unacceptable!")
        assert result.passed is False

    def test_error_threshold_triggers_escalation(self):
        result = self.guard.check_escalation_needed("Help me", error_count=5)
        assert result.passed is False
        assert result.violation_type == "repeated_confusion"

    def test_below_error_threshold_passes(self):
        result = self.guard.check_escalation_needed("Help me", error_count=1)
        assert result.passed is True


class TestGuardrailPipeline:
    def test_clean_input_passes(self, guardrail_pipeline):
        violations = guardrail_pipeline.check_user_input("I need a plumber")
        assert len(violations) == 0

    def test_emergency_input_flagged(self, guardrail_pipeline):
        violations = guardrail_pipeline.check_user_input("There's a gas leak!")
        assert len(violations) > 0
        assert any(v.violation_type == "emergency" for v in violations)

    def test_out_of_scope_input_flagged(self, guardrail_pipeline):
        violations = guardrail_pipeline.check_user_input("I need financial advice")
        assert len(violations) > 0

    def test_clean_response_passes(self, guardrail_pipeline):
        violations = guardrail_pipeline.check_agent_response(
            "We can schedule your plumbing appointment for Tuesday."
        )
        assert len(violations) == 0

    def test_hallucination_response_flagged(self, guardrail_pipeline):
        violations = guardrail_pipeline.check_agent_response(
            "We guarantee all our work will be perfect."
        )
        assert len(violations) > 0

    def test_persona_break_response_flagged(self, guardrail_pipeline):
        violations = guardrail_pipeline.check_agent_response(
            "As an AI, I don't have personal preferences."
        )
        assert len(violations) > 0

    def test_formatting_response_flagged(self, guardrail_pipeline):
        violations = guardrail_pipeline.check_agent_response(
            "Our services:\n- Plumbing\n- Electrical"
        )
        assert len(violations) > 0

    def test_multiple_violations_detected(self, guardrail_pipeline):
        violations = guardrail_pipeline.check_agent_response(
            "As an AI, I guarantee our **award-winning** service."
        )
        assert len(violations) >= 2

    def test_error_count_triggers_escalation(self, guardrail_pipeline):
        violations = guardrail_pipeline.check_user_input("I just want help", error_count=10)
        assert len(violations) > 0
        assert any(v.violation_type == "repeated_confusion" for v in violations)
