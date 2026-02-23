"""
Slot-filling manager with three-phase pattern: Collect -> Validate -> Confirm.

Implements confirmation gates that prevent premature booking execution.
Tracks correction history and retry counts for evaluation analysis.

Usage:
    manager = SlotManager()
    success, msg = manager.set_slot("customer_name", "John Smith")
    if manager.all_required_filled():
        summary = manager.get_confirmation_summary()
        # ... caller confirms ...
        manager.confirm_all()
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from src.config import settings
from src.tools.services import get_valid_service_terms
from src.utils import normalize_phone

logger = logging.getLogger(__name__)

# Validation thresholds
MIN_NAME_LENGTH = 2
MIN_PHONE_DIGITS = 7
MAX_PHONE_DIGITS = 15
MIN_ADDRESS_LENGTH = 5


class SlotStatus(str, Enum):
    """Lifecycle status of a slot value."""

    EMPTY = "empty"
    COLLECTED = "collected"
    VALIDATED = "validated"
    CONFIRMED = "confirmed"
    CORRECTED = "corrected"


def _validate_name(value: str) -> bool:
    return len(value.strip()) >= MIN_NAME_LENGTH


def _validate_phone(value: str) -> bool:
    digits = re.sub(r"[^\d]", "", value)
    return MIN_PHONE_DIGITS <= len(digits) <= MAX_PHONE_DIGITS


def _validate_service(value: str) -> bool:
    normalized = value.lower().strip()
    return any(svc in normalized or normalized in svc for svc in get_valid_service_terms())


def _validate_date(value: str) -> bool:
    """Validate date is in YYYY-MM-DD format."""
    try:
        datetime.strptime(value.strip(), "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _validate_time(value: str) -> bool:
    """Validate time is in HH:MM format."""
    try:
        datetime.strptime(value.strip(), "%H:%M")
        return True
    except ValueError:
        return False


def _validate_address(value: str) -> bool:
    return len(value.strip()) >= MIN_ADDRESS_LENGTH


@dataclass(frozen=True)
class SlotDefinition:
    """Schema for a single slot to collect."""

    name: str
    display_name: str
    required: bool = True
    validator: Optional[Callable[[str], bool]] = None
    prompt_hint: str = ""
    max_retries: int = settings.guardrails.max_slot_retries
    confirmation_required: bool = True


@dataclass
class SlotValue:
    """Current state and history of a collected slot."""

    raw_value: Optional[str] = None
    normalized_value: Optional[str] = None
    status: SlotStatus = SlotStatus.EMPTY
    attempts: int = 0
    correction_history: list[str] = field(default_factory=list)


class SlotManager:
    """
    Manages slot collection with validation and confirmation gates.

    The booking tool refuses to execute unless all required slots
    have reached CONFIRMED status via the explicit confirmation gate.
    """

    SLOT_DEFINITIONS: list[SlotDefinition] = [
        SlotDefinition(
            name="customer_name",
            display_name="name",
            prompt_hint="Ask for their full name",
            validator=_validate_name,
        ),
        SlotDefinition(
            name="customer_phone",
            display_name="phone number",
            prompt_hint="Ask for a callback number",
            validator=_validate_phone,
        ),
        SlotDefinition(
            name="service_type",
            display_name="type of service",
            prompt_hint="Ask what service they need",
            validator=_validate_service,
        ),
        SlotDefinition(
            name="preferred_date",
            display_name="preferred date",
            prompt_hint="Ask when they'd like the appointment",
            validator=_validate_date,
        ),
        SlotDefinition(
            name="preferred_time",
            display_name="preferred time",
            prompt_hint="Ask what time works best",
            validator=_validate_time,
        ),
        SlotDefinition(
            name="customer_address",
            display_name="service address",
            prompt_hint="Ask for the address where the service is needed",
            validator=_validate_address,
        ),
        SlotDefinition(
            name="job_description",
            display_name="job description",
            required=False,
            prompt_hint="Ask them to briefly describe the issue",
            confirmation_required=False,
        ),
    ]

    def __init__(self) -> None:
        self.slots: dict[str, SlotValue] = {
            defn.name: SlotValue() for defn in self.SLOT_DEFINITIONS
        }

    def _get_definition(self, name: str) -> SlotDefinition:
        for defn in self.SLOT_DEFINITIONS:
            if defn.name == name:
                return defn
        raise ValueError(f"Unknown slot: {name}")

    def _normalize(self, name: str, value: str) -> str:
        """Apply slot-specific normalization rules."""
        value = value.strip()
        if name == "customer_phone":
            return normalize_phone(value)
        if name == "service_type":
            return value.lower()
        if name == "customer_name":
            return value.title()
        return value

    def set_slot(self, name: str, raw_value: str) -> tuple[bool, str]:
        """
        Set a slot value with validation.

        Returns:
            (success, message) — success=True if validation passed.
        """
        defn = self._get_definition(name)
        slot = self.slots[name]
        slot.raw_value = raw_value
        slot.attempts += 1

        if defn.validator and not defn.validator(raw_value):
            slot.status = SlotStatus.COLLECTED
            logger.debug("Slot '%s' validation failed: '%s'", name, raw_value)
            return False, f"The {defn.display_name} '{raw_value}' doesn't look right."

        slot.normalized_value = self._normalize(name, raw_value)
        slot.status = SlotStatus.VALIDATED
        logger.debug("Slot '%s' set to '%s'", name, slot.normalized_value)
        return True, f"Got {defn.display_name}: {slot.normalized_value}"

    def correct_slot(self, name: str, new_value: str) -> tuple[bool, str]:
        """Handle a correction, preserving the previous value in history."""
        slot = self.slots[name]
        if slot.raw_value is not None:
            slot.correction_history.append(slot.raw_value)
        return self.set_slot(name, new_value)

    def confirm_all(self) -> None:
        """Mark all validated/corrected slots as confirmed after explicit caller approval."""
        for slot in self.slots.values():
            if slot.status in (SlotStatus.VALIDATED, SlotStatus.CORRECTED):
                slot.status = SlotStatus.CONFIRMED
        logger.info("All slots confirmed by caller")

    def get_confirmation_summary(self) -> str:
        """Generate read-back text for the confirmation gate."""
        lines = []
        for defn in self.SLOT_DEFINITIONS:
            if not defn.confirmation_required:
                continue
            slot = self.slots[defn.name]
            if slot.normalized_value:
                lines.append(f"  {defn.display_name}: {slot.normalized_value}")
        return "Here's what I have:\n" + "\n".join(lines)

    def get_next_empty_slot(self) -> Optional[SlotDefinition]:
        """Get the next required slot that hasn't been filled."""
        for defn in self.SLOT_DEFINITIONS:
            if defn.required and self.slots[defn.name].status == SlotStatus.EMPTY:
                return defn
        return None

    def get_missing_slots(self) -> list[SlotDefinition]:
        """Get all required slots still unfilled."""
        return [
            defn
            for defn in self.SLOT_DEFINITIONS
            if defn.required and self.slots[defn.name].status == SlotStatus.EMPTY
        ]

    def all_required_filled(self) -> bool:
        """Check if all required slots have at least been validated."""
        filled = {SlotStatus.VALIDATED, SlotStatus.CONFIRMED, SlotStatus.CORRECTED}
        return all(self.slots[d.name].status in filled for d in self.SLOT_DEFINITIONS if d.required)

    def all_confirmed(self) -> bool:
        """Check if all required slots passed the confirmation gate."""
        return all(
            self.slots[d.name].status == SlotStatus.CONFIRMED
            for d in self.SLOT_DEFINITIONS
            if d.required
        )

    def has_exceeded_retries(self, name: str) -> bool:
        """Check if a slot has exceeded its retry limit."""
        defn = self._get_definition(name)
        return self.slots[name].attempts >= defn.max_retries

    def get_slot_value(self, name: str) -> Optional[str]:
        """Get the normalized value of a slot."""
        return self.slots[name].normalized_value

    def to_dict(self) -> dict[str, Any]:
        """Export collected slot values as a flat dict."""
        return {
            d.name: self.slots[d.name].normalized_value
            for d in self.SLOT_DEFINITIONS
            if self.slots[d.name].normalized_value is not None
        }

    def get_stats(self) -> dict[str, Any]:
        """Get slot collection statistics for evaluation."""
        total_attempts = sum(s.attempts for s in self.slots.values())
        corrections = sum(len(s.correction_history) for s in self.slots.values())
        filled = sum(
            1
            for d in self.SLOT_DEFINITIONS
            if d.required and self.slots[d.name].status != SlotStatus.EMPTY
        )
        required = sum(1 for d in self.SLOT_DEFINITIONS if d.required)
        return {
            "total_attempts": total_attempts,
            "total_corrections": corrections,
            "slots_filled": filled,
            "slots_required": required,
            "fill_rate": filled / required if required else 0,
        }
