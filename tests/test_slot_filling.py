"""Tests for the slot manager and slot-filling lifecycle."""

import pytest

from src.conversation.slot_manager import SlotStatus


class TestSlotSetAndValidation:
    def test_set_valid_name(self, slot_manager):
        ok, msg = slot_manager.set_slot("customer_name", "John Smith")
        assert ok is True
        assert slot_manager.get_slot_value("customer_name") == "John Smith"

    def test_set_name_normalizes_to_title_case(self, slot_manager):
        ok, _ = slot_manager.set_slot("customer_name", "john smith")
        assert ok is True
        assert slot_manager.get_slot_value("customer_name") == "John Smith"

    def test_set_invalid_name_too_short(self, slot_manager):
        ok, msg = slot_manager.set_slot("customer_name", "J")
        assert ok is False
        assert "doesn't look right" in msg

    def test_set_valid_phone(self, slot_manager):
        ok, _ = slot_manager.set_slot("customer_phone", "0412 345 678")
        assert ok is True
        assert slot_manager.get_slot_value("customer_phone") == "0412345678"

    def test_set_valid_phone_international(self, slot_manager):
        ok, _ = slot_manager.set_slot("customer_phone", "+61 412 345 678")
        assert ok is True
        assert slot_manager.get_slot_value("customer_phone") == "+61412345678"

    def test_set_invalid_phone_too_short(self, slot_manager):
        ok, msg = slot_manager.set_slot("customer_phone", "123")
        assert ok is False

    def test_set_invalid_phone_too_few_digits(self, slot_manager):
        ok, msg = slot_manager.set_slot("customer_phone", "12345")
        assert ok is False

    def test_set_valid_service(self, slot_manager):
        ok, _ = slot_manager.set_slot("service_type", "plumbing")
        assert ok is True

    def test_set_valid_service_partial_match(self, slot_manager):
        ok, _ = slot_manager.set_slot("service_type", "plumbing repair")
        assert ok is True

    def test_set_invalid_service(self, slot_manager):
        ok, msg = slot_manager.set_slot("service_type", "landscaping")
        assert ok is False

    def test_set_valid_address(self, slot_manager):
        ok, _ = slot_manager.set_slot("customer_address", "42 Oak Avenue, Richmond VIC 3121")
        assert ok is True

    def test_set_invalid_address_too_short(self, slot_manager):
        ok, msg = slot_manager.set_slot("customer_address", "42")
        assert ok is False

    def test_set_date_no_validator(self, slot_manager):
        ok, _ = slot_manager.set_slot("preferred_date", "2025-03-18")
        assert ok is True
        assert slot_manager.get_slot_value("preferred_date") == "2025-03-18"

    def test_set_time_no_validator(self, slot_manager):
        ok, _ = slot_manager.set_slot("preferred_time", "10:00")
        assert ok is True

    def test_set_optional_job_description(self, slot_manager):
        ok, _ = slot_manager.set_slot("job_description", "Kitchen sink is leaking")
        assert ok is True


class TestSlotStatus:
    def test_empty_slot_status(self, slot_manager):
        assert slot_manager.slots["customer_name"].status == SlotStatus.EMPTY

    def test_validated_slot_status(self, slot_manager):
        slot_manager.set_slot("customer_name", "John Smith")
        assert slot_manager.slots["customer_name"].status == SlotStatus.VALIDATED

    def test_failed_validation_status(self, slot_manager):
        slot_manager.set_slot("customer_name", "J")
        assert slot_manager.slots["customer_name"].status == SlotStatus.COLLECTED

    def test_confirmed_status_after_confirm_all(self, slot_manager):
        slot_manager.set_slot("customer_name", "John Smith")
        slot_manager.confirm_all()
        assert slot_manager.slots["customer_name"].status == SlotStatus.CONFIRMED


class TestCorrections:
    def test_correct_slot_preserves_history(self, slot_manager):
        slot_manager.set_slot("customer_name", "Emma Watson")
        slot_manager.correct_slot("customer_name", "Emma Wilson")
        assert slot_manager.get_slot_value("customer_name") == "Emma Wilson"
        assert "Emma Watson" in slot_manager.slots["customer_name"].correction_history

    def test_correct_slot_increments_attempts(self, slot_manager):
        slot_manager.set_slot("customer_name", "Emma Watson")
        slot_manager.correct_slot("customer_name", "Emma Wilson")
        assert slot_manager.slots["customer_name"].attempts == 2

    def test_multiple_corrections_tracked(self, slot_manager):
        slot_manager.set_slot("customer_phone", "0412345678")
        slot_manager.correct_slot("customer_phone", "0498765432")
        slot_manager.correct_slot("customer_phone", "0411222333")
        assert len(slot_manager.slots["customer_phone"].correction_history) == 2


class TestConfirmationGate:
    def _fill_required(self, sm):
        sm.set_slot("customer_name", "John Smith")
        sm.set_slot("customer_phone", "0412345678")
        sm.set_slot("service_type", "plumbing")
        sm.set_slot("preferred_date", "2025-03-18")
        sm.set_slot("preferred_time", "10:00")
        sm.set_slot("customer_address", "42 Oak Avenue, Richmond VIC 3121")

    def test_all_required_filled(self, slot_manager):
        self._fill_required(slot_manager)
        assert slot_manager.all_required_filled() is True

    def test_not_all_filled_when_missing(self, slot_manager):
        slot_manager.set_slot("customer_name", "John Smith")
        assert slot_manager.all_required_filled() is False

    def test_not_confirmed_before_confirm_all(self, slot_manager):
        self._fill_required(slot_manager)
        assert slot_manager.all_confirmed() is False

    def test_confirmed_after_confirm_all(self, slot_manager):
        self._fill_required(slot_manager)
        slot_manager.confirm_all()
        assert slot_manager.all_confirmed() is True

    def test_confirmation_summary_includes_all_fields(self, slot_manager):
        self._fill_required(slot_manager)
        summary = slot_manager.get_confirmation_summary()
        assert "John Smith" in summary
        assert "0412345678" in summary
        assert "plumbing" in summary
        assert "2025-03-18" in summary
        assert "10:00" in summary
        assert "42 Oak Avenue" in summary

    def test_confirmation_summary_excludes_optional(self, slot_manager):
        self._fill_required(slot_manager)
        summary = slot_manager.get_confirmation_summary()
        assert "job description" not in summary


class TestRetryTracking:
    def test_retry_count_increments(self, slot_manager):
        slot_manager.set_slot("customer_phone", "123")
        slot_manager.set_slot("customer_phone", "456")
        assert slot_manager.slots["customer_phone"].attempts == 2

    def test_not_exceeded_retries_initially(self, slot_manager):
        slot_manager.set_slot("customer_phone", "123")
        assert slot_manager.has_exceeded_retries("customer_phone") is False

    def test_exceeded_retries_at_limit(self, slot_manager):
        slot_manager.set_slot("customer_phone", "123")
        slot_manager.set_slot("customer_phone", "456")
        slot_manager.set_slot("customer_phone", "789")
        assert slot_manager.has_exceeded_retries("customer_phone") is True


class TestSlotNavigation:
    def test_get_next_empty_slot_returns_first(self, slot_manager):
        next_slot = slot_manager.get_next_empty_slot()
        assert next_slot is not None
        assert next_slot.name == "customer_name"

    def test_get_next_empty_slot_skips_filled(self, slot_manager):
        slot_manager.set_slot("customer_name", "John Smith")
        next_slot = slot_manager.get_next_empty_slot()
        assert next_slot is not None
        assert next_slot.name == "customer_phone"

    def test_get_next_empty_slot_none_when_full(self, slot_manager):
        slot_manager.set_slot("customer_name", "John Smith")
        slot_manager.set_slot("customer_phone", "0412345678")
        slot_manager.set_slot("service_type", "plumbing")
        slot_manager.set_slot("preferred_date", "2025-03-18")
        slot_manager.set_slot("preferred_time", "10:00")
        slot_manager.set_slot("customer_address", "42 Oak Avenue, Richmond VIC 3121")
        assert slot_manager.get_next_empty_slot() is None

    def test_get_missing_slots(self, slot_manager):
        slot_manager.set_slot("customer_name", "John Smith")
        missing = slot_manager.get_missing_slots()
        assert len(missing) == 5  # phone, service, date, time, address

    def test_unknown_slot_raises(self, slot_manager):
        with pytest.raises(ValueError, match="Unknown slot"):
            slot_manager.set_slot("unknown_field", "value")


class TestExport:
    def test_to_dict_returns_filled_slots(self, slot_manager):
        slot_manager.set_slot("customer_name", "John Smith")
        slot_manager.set_slot("customer_phone", "0412345678")
        data = slot_manager.to_dict()
        assert data["customer_name"] == "John Smith"
        assert data["customer_phone"] == "0412345678"
        assert "service_type" not in data

    def test_get_stats(self, slot_manager):
        slot_manager.set_slot("customer_name", "John Smith")
        slot_manager.set_slot("customer_phone", "0412345678")
        stats = slot_manager.get_stats()
        assert stats["slots_filled"] == 2
        assert stats["slots_required"] == 6
        assert stats["total_attempts"] == 2
        assert stats["fill_rate"] == pytest.approx(2 / 6)
