"""Tests for BookingAgent tool methods using stub RunContext."""

import pytest

from src.agents.booking_agent import BookingAgent
from src.agents.compat import RunContext
from src.schemas.customer_schema import SessionData


def _make_context() -> RunContext[SessionData]:
    ctx = RunContext()
    ctx.userdata = SessionData()
    return ctx


class TestRecordSlots:
    def setup_method(self):
        self.agent = BookingAgent()
        self.ctx = _make_context()

    @pytest.mark.asyncio
    async def test_record_customer_name(self):
        result = await self.agent.record_customer_name(self.ctx, "john smith")
        assert "John Smith" in result
        assert self.ctx.userdata.customer_name == "John Smith"

    @pytest.mark.asyncio
    async def test_record_phone_number_valid(self):
        result = await self.agent.record_phone_number(self.ctx, "0412 345 678")
        assert "0412345678" in result
        assert self.ctx.userdata.customer_phone == "0412345678"

    @pytest.mark.asyncio
    async def test_record_phone_number_invalid(self):
        result = await self.agent.record_phone_number(self.ctx, "12")
        assert "doesn't look right" in result
        assert self.ctx.userdata.customer_phone is None

    @pytest.mark.asyncio
    async def test_record_service_type_matched(self):
        result = await self.agent.record_service_type(self.ctx, "plumbing")
        assert "plumbing" in result.lower()
        assert self.ctx.userdata.service_type == "plumbing"

    @pytest.mark.asyncio
    async def test_record_preferred_date_valid(self):
        result = await self.agent.record_preferred_date(self.ctx, "2025-04-01")
        assert "2025-04-01" in result

    @pytest.mark.asyncio
    async def test_record_preferred_date_invalid(self):
        result = await self.agent.record_preferred_date(self.ctx, "next Tuesday")
        assert "doesn't look right" in result

    @pytest.mark.asyncio
    async def test_record_preferred_time_valid(self):
        result = await self.agent.record_preferred_time(self.ctx, "10:00")
        assert "10:00" in result

    @pytest.mark.asyncio
    async def test_record_preferred_time_invalid(self):
        result = await self.agent.record_preferred_time(self.ctx, "ten am")
        assert "doesn't look right" in result

    @pytest.mark.asyncio
    async def test_record_address(self):
        result = await self.agent.record_address(
            self.ctx, "42 Oak Avenue, Richmond"
        )
        assert "42 Oak Avenue, Richmond" in result

    @pytest.mark.asyncio
    async def test_record_job_description(self):
        result = await self.agent.record_job_description(
            self.ctx, "Leaky kitchen tap"
        )
        assert "Leaky kitchen tap" in result


class TestCorrectDetail:
    def setup_method(self):
        self.agent = BookingAgent()
        self.ctx = _make_context()

    @pytest.mark.asyncio
    async def test_correct_known_field(self):
        await self.agent.record_customer_name(self.ctx, "John Smith")
        result = await self.agent.correct_detail(
            self.ctx, "customer_name", "Jane Doe"
        )
        assert "Jane Doe" in result
        assert self.ctx.userdata.customer_name == "Jane Doe"

    @pytest.mark.asyncio
    async def test_correct_unknown_field_rejected(self):
        result = await self.agent.correct_detail(
            self.ctx, "favorite_color", "blue"
        )
        assert "Unknown field" in result


class TestConfirmBookingDetails:
    def setup_method(self):
        self.agent = BookingAgent()
        self.ctx = _make_context()

    @pytest.mark.asyncio
    async def test_confirm_when_slots_missing(self):
        result = await self.agent.confirm_booking_details(self.ctx)
        assert "Still need" in result

    @pytest.mark.asyncio
    async def test_confirm_when_all_filled(self):
        await self.agent.record_customer_name(self.ctx, "John Smith")
        await self.agent.record_phone_number(self.ctx, "0412345678")
        await self.agent.record_service_type(self.ctx, "plumbing")
        await self.agent.record_preferred_date(self.ctx, "2025-04-01")
        await self.agent.record_preferred_time(self.ctx, "10:00")
        await self.agent.record_address(self.ctx, "42 Oak Avenue, Richmond VIC")
        result = await self.agent.confirm_booking_details(self.ctx)
        assert "John Smith" in result
        assert "Does everything sound correct?" in result


class TestCheckAndBook:
    def setup_method(self):
        self.agent = BookingAgent()
        self.ctx = _make_context()

    @pytest.mark.asyncio
    async def test_book_when_slots_missing(self):
        result = await self.agent.check_and_book(self.ctx)
        assert "missing" in result.lower()

    @pytest.mark.asyncio
    async def test_book_happy_path(self):
        await self.agent.record_customer_name(self.ctx, "John Smith")
        await self.agent.record_phone_number(self.ctx, "0412345678")
        await self.agent.record_service_type(self.ctx, "plumbing")
        await self.agent.record_preferred_date(self.ctx, "2025-04-01")
        await self.agent.record_preferred_time(self.ctx, "10:00")
        await self.agent.record_address(self.ctx, "42 Oak Avenue, Richmond VIC")
        result = await self.agent.check_and_book(self.ctx)
        # Should either book successfully or offer alternatives
        lower = result.lower()
        assert "booking" in lower or "available" in lower
