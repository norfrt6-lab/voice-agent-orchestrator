"""
Centralized configuration with environment variable overrides.

All business-specific values, thresholds, and model settings are
configurable here. Nothing is hardcoded in agent or tool logic.
"""

import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BusinessConfig:
    """Business-specific settings loaded from environment or defaults."""

    name: str = os.getenv("BUSINESS_NAME", "Reliable Home Services")
    hours_weekday: str = os.getenv("BUSINESS_HOURS_WEEKDAY", "Monday to Friday 8am to 6pm")
    hours_weekend: str = os.getenv("BUSINESS_HOURS_WEEKEND", "Saturday 9am to 2pm, closed Sunday")
    emergency_hours: str = os.getenv("EMERGENCY_HOURS", "Available 24/7 at premium rates")
    service_area: str = os.getenv("SERVICE_AREA", "Greater Melbourne metro area")
    emergency_line: str = os.getenv("EMERGENCY_LINE", "1300-555-000")
    callback_sla_minutes: int = int(os.getenv("CALLBACK_SLA_MINUTES", "30"))


@dataclass(frozen=True)
class ModelConfig:
    """LLM and voice pipeline model settings."""

    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    stt_model: str = os.getenv("STT_MODEL", "nova-3")
    stt_language: str = os.getenv("STT_LANGUAGE", "en")
    tts_model: str = os.getenv("TTS_MODEL", "sonic-2")
    tts_voice_id: str = os.getenv("TTS_VOICE_ID", "79a125e8-cd45-4c13-8a67-188112f4dd22")


@dataclass(frozen=True)
class GuardrailConfig:
    """Thresholds for escalation and guardrail triggers."""

    confusion_threshold: int = int(os.getenv("CONFUSION_THRESHOLD", "3"))
    max_slot_retries: int = int(os.getenv("MAX_SLOT_RETRIES", "3"))
    max_confirmation_attempts: int = int(os.getenv("MAX_CONFIRMATION_ATTEMPTS", "2"))
    slow_response_threshold_sec: float = float(os.getenv("SLOW_RESPONSE_THRESHOLD", "8.0"))


@dataclass(frozen=True)
class EvalConfig:
    """Evaluation framework thresholds and targets."""

    target_success_rate: float = float(os.getenv("TARGET_SUCCESS_RATE", "0.70"))
    target_containment_rate: float = float(os.getenv("TARGET_CONTAINMENT_RATE", "0.85"))
    target_escalation_rate: float = float(os.getenv("TARGET_ESCALATION_RATE", "0.15"))
    target_max_turns: int = int(os.getenv("TARGET_MAX_TURNS", "16"))
    target_slot_fill_rate: float = float(os.getenv("TARGET_SLOT_FILL_RATE", "0.80"))


@dataclass(frozen=True)
class AppConfig:
    """Root configuration aggregating all sub-configs."""

    business: BusinessConfig = field(default_factory=BusinessConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    guardrails: GuardrailConfig = field(default_factory=GuardrailConfig)
    evaluation: EvalConfig = field(default_factory=EvalConfig)
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    agent_name: str = os.getenv("AGENT_NAME", "voice-receptionist")


def load_config() -> AppConfig:
    """Load and validate application configuration."""
    config = AppConfig()
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logger.info("Configuration loaded for '%s'", config.business.name)
    return config


# Singleton instance
settings = load_config()
