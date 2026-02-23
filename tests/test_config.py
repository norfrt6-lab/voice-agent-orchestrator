"""Tests for configuration loading and validation."""

import pytest

from src.config import AppConfig, _validate_config


class TestConfigValidation:
    def test_default_config_passes_validation(self):
        config = AppConfig()
        _validate_config(config)  # should not raise

    def test_invalid_temperature_too_high(self):
        from src.config import BusinessConfig, EvalConfig, GuardrailConfig, ModelConfig

        model = ModelConfig.__new__(ModelConfig)
        object.__setattr__(model, "llm_model", "gpt-4o-mini")
        object.__setattr__(model, "llm_temperature", 3.0)
        object.__setattr__(model, "stt_model", "nova-3")
        object.__setattr__(model, "stt_language", "en")
        object.__setattr__(model, "tts_model", "sonic-2")
        object.__setattr__(model, "tts_voice_id", "test")

        config = AppConfig.__new__(AppConfig)
        object.__setattr__(config, "business", BusinessConfig())
        object.__setattr__(config, "model", model)
        object.__setattr__(config, "guardrails", GuardrailConfig())
        object.__setattr__(config, "evaluation", EvalConfig())
        object.__setattr__(config, "log_level", "INFO")
        object.__setattr__(config, "agent_name", "test")

        with pytest.raises(ValueError, match="LLM_TEMPERATURE"):
            _validate_config(config)

    def test_invalid_temperature_negative(self):
        from src.config import BusinessConfig, EvalConfig, GuardrailConfig, ModelConfig

        model = ModelConfig.__new__(ModelConfig)
        object.__setattr__(model, "llm_model", "gpt-4o-mini")
        object.__setattr__(model, "llm_temperature", -0.5)
        object.__setattr__(model, "stt_model", "nova-3")
        object.__setattr__(model, "stt_language", "en")
        object.__setattr__(model, "tts_model", "sonic-2")
        object.__setattr__(model, "tts_voice_id", "test")

        config = AppConfig.__new__(AppConfig)
        object.__setattr__(config, "business", BusinessConfig())
        object.__setattr__(config, "model", model)
        object.__setattr__(config, "guardrails", GuardrailConfig())
        object.__setattr__(config, "evaluation", EvalConfig())
        object.__setattr__(config, "log_level", "INFO")
        object.__setattr__(config, "agent_name", "test")

        with pytest.raises(ValueError, match="LLM_TEMPERATURE"):
            _validate_config(config)

    def test_invalid_confusion_threshold(self):
        from src.config import BusinessConfig, EvalConfig, GuardrailConfig, ModelConfig

        guardrails = GuardrailConfig.__new__(GuardrailConfig)
        object.__setattr__(guardrails, "confusion_threshold", 0)
        object.__setattr__(guardrails, "max_slot_retries", 3)
        object.__setattr__(guardrails, "max_confirmation_attempts", 2)
        object.__setattr__(guardrails, "slow_response_threshold_sec", 8.0)

        config = AppConfig.__new__(AppConfig)
        object.__setattr__(config, "business", BusinessConfig())
        object.__setattr__(config, "model", ModelConfig())
        object.__setattr__(config, "guardrails", guardrails)
        object.__setattr__(config, "evaluation", EvalConfig())
        object.__setattr__(config, "log_level", "INFO")
        object.__setattr__(config, "agent_name", "test")

        with pytest.raises(ValueError, match="CONFUSION_THRESHOLD"):
            _validate_config(config)

    def test_invalid_target_rate_above_one(self):
        from src.config import BusinessConfig, EvalConfig, GuardrailConfig, ModelConfig

        evaluation = EvalConfig.__new__(EvalConfig)
        object.__setattr__(evaluation, "target_success_rate", 1.5)
        object.__setattr__(evaluation, "target_containment_rate", 0.85)
        object.__setattr__(evaluation, "target_escalation_rate", 0.15)
        object.__setattr__(evaluation, "target_max_turns", 16)
        object.__setattr__(evaluation, "target_slot_fill_rate", 0.80)

        config = AppConfig.__new__(AppConfig)
        object.__setattr__(config, "business", BusinessConfig())
        object.__setattr__(config, "model", ModelConfig())
        object.__setattr__(config, "guardrails", GuardrailConfig())
        object.__setattr__(config, "evaluation", evaluation)
        object.__setattr__(config, "log_level", "INFO")
        object.__setattr__(config, "agent_name", "test")

        with pytest.raises(ValueError, match="TARGET_SUCCESS_RATE"):
            _validate_config(config)

    def test_safe_int_parsing(self):
        from src.config import _safe_int

        assert _safe_int("NONEXISTENT_VAR_12345", "42") == 42

    def test_safe_float_parsing(self):
        from src.config import _safe_float

        assert _safe_float("NONEXISTENT_VAR_12345", "3.14") == pytest.approx(3.14)
