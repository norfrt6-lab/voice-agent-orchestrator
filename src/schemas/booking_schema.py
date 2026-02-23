"""Booking and availability data models."""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class BookingRequest(BaseModel):
    """Validated booking request data."""
    customer_name: str
    customer_phone: str
    customer_address: str
    service_type: str
    preferred_date: str
    preferred_time: str
    job_description: Optional[str] = None


class BookingResponse(BaseModel):
    """Booking creation result."""
    success: bool
    booking_ref: Optional[str] = None
    message: str
    service_name: str = ""
    date: str = ""
    time: str = ""
    technician: Optional[str] = None
    created_at: Optional[datetime] = None


class AvailabilitySlot(BaseModel):
    """Single available time slot."""
    date: str
    time: str
    technician: str
    duration_minutes: int = 60


class AvailabilityResponse(BaseModel):
    """Calendar availability check result."""
    available: bool
    slots: list[AvailabilitySlot] = Field(default_factory=list)
    next_available: Optional[str] = None
    message: str = ""
