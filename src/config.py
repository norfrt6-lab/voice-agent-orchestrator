"""
Centralized configuration with environment variable overrides.

All business-specific values, thresholds, and model settings are
configurable here. Nothing is hardcoded in agent or tool logic.
"""

import logging
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _safe_int(env_var: str, default: str) -> int:
    """Parse an integer from an env var with a clear error on bad values."""
    raw = os.getenv(env_var, default)
    try:
        return int(raw)
    except (ValueError, TypeError):
        raise ValueError(
            f"Invalid integer for {env_var}: {raw!r}"
        ) from None


def _safe_float(env_var: str, default: str) -> float:
    """Parse a float from an env var with a clear error on bad values."""
    raw = os.getenv(env_var, default)
    try:
        return float(raw)
    except (ValueError, TypeError):
        raise ValueError(
            f"Invalid float for {env_var}: {raw!r}"
        ) from None


@dataclass(frozen=True)
class BusinessConfig:
    """Business-specific settings loaded from environment or defaults."""

    name: str = os.getenv("BUSINESS_NAME", "Reliable Home Services")
    hours_weekday: str = os.getenv("BUSINESS_HOURS_WEEKDAY", "Monday to Friday 8am to 6pm")
    hours_weekend: str = os.getenv(
        "BUSINESS_HOURS_WEEKEND", "Saturday 9am to 2pm, closed Sunday"
    )
    emergency_hours: str = os.getenv("EMERGENCY_HOURS", "Available 24/7 at premium rates")
    service_area: str = os.getenv("SERVICE_AREA", "Greater Melbourne metro area")
    emergency_line: str = os.getenv("EMERGENCY_LINE", "1300-555-000")
    callback_sla_minutes: int = _safe_int("CALLBACK_SLA_MINUTES", "30")


@dataclass(frozen=True)
class ModelConfig:
    """LLM and voice pipeline model settings."""

    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    llm_temperature: float = _safe_float("LLM_TEMPERATURE", "0.3")
    stt_model: str = os.getenv("STT_MODEL", "nova-3")
    stt_language: str = os.getenv("STT_LANGUAGE", "en")
    tts_model: str = os.getenv("TTS_MODEL", "sonic-2")
    tts_voice_id: str = os.getenv("TTS_VOICE_ID", "79a125e8-cd45-4c13-8a67-188112f4dd22")


@dataclass(frozen=True)
class GuardrailConfig:
    """Thresholds for escalation and guardrail triggers."""

    confusion_threshold: int = _safe_int("CONFUSION_THRESHOLD", "3")
    max_slot_retries: int = _safe_int("MAX_SLOT_RETRIES", "3")
    max_confirmation_attempts: int = _safe_int("MAX_CONFIRMATION_ATTEMPTS", "2")
    slow_response_threshold_sec: float = _safe_float("SLOW_RESPONSE_THRESHOLD", "8.0")


@dataclass(frozen=True)
class EvalConfig:
    """Evaluation framework thresholds and targets."""

    target_success_rate: float = _safe_float("TARGET_SUCCESS_RATE", "0.70")
    target_containment_rate: float = _safe_float("TARGET_CONTAINMENT_RATE", "0.85")
    target_escalation_rate: float = _safe_float("TARGET_ESCALATION_RATE", "0.15")
    target_max_turns: int = _safe_int("TARGET_MAX_TURNS", "16")
    target_slot_fill_rate: float = _safe_float("TARGET_SLOT_FILL_RATE", "0.80")


@dataclass(frozen=True)
class AppConfig:
    """Root configuration aggregating all sub-configs."""

    business: BusinessConfig = field(default_factory=BusinessConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    guardrails: GuardrailConfig = field(default_factory=GuardrailConfig)
    evaluation: EvalConfig = field(default_factory=EvalConfig)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    agent_name: str = os.getenv("AGENT_NAME", "voice-receptionist")


def _validate_config(config: AppConfig) -> None:
    """Validate configuration values are within acceptable ranges."""
    if not 0.0 <= config.model.llm_temperature <= 2.0:
        raise ValueError(
            f"LLM_TEMPERATURE must be between 0.0 and 2.0, got {config.model.llm_temperature}"
        )
    if config.guardrails.confusion_threshold < 1:
        raise ValueError(
            f"CONFUSION_THRESHOLD must be >= 1, got {config.guardrails.confusion_threshold}"
        )
    if config.guardrails.max_slot_retries < 1:
        raise ValueError(
            f"MAX_SLOT_RETRIES must be >= 1, got {config.guardrails.max_slot_retries}"
        )
    if config.guardrails.max_confirmation_attempts < 1:
        raise ValueError(
            "MAX_CONFIRMATION_ATTEMPTS must be >= 1, "
            f"got {config.guardrails.max_confirmation_attempts}"
        )
    if config.guardrails.slow_response_threshold_sec <= 0:
        raise ValueError(
            "SLOW_RESPONSE_THRESHOLD must be > 0, "
            f"got {config.guardrails.slow_response_threshold_sec}"
        )
    if config.business.callback_sla_minutes < 1:
        raise ValueError(
            f"CALLBACK_SLA_MINUTES must be >= 1, got {config.business.callback_sla_minutes}"
        )

    for rate_name, rate_value in [
        ("TARGET_SUCCESS_RATE", config.evaluation.target_success_rate),
        ("TARGET_CONTAINMENT_RATE", config.evaluation.target_containment_rate),
        ("TARGET_ESCALATION_RATE", config.evaluation.target_escalation_rate),
        ("TARGET_SLOT_FILL_RATE", config.evaluation.target_slot_fill_rate),
    ]:
        if not 0.0 <= rate_value <= 1.0:
            raise ValueError(f"{rate_name} must be between 0.0 and 1.0, got {rate_value}")

    if config.evaluation.target_max_turns < 1:
        raise ValueError(
            f"TARGET_MAX_TURNS must be >= 1, got {config.evaluation.target_max_turns}"
        )


def load_config() -> AppConfig:
    """Load and validate application configuration."""
    config = AppConfig()
    _validate_config(config)
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("Configuration loaded for '%s'", config.business.name)
    return config


# Singleton instance
settings = load_config()
