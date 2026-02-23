"""Customer data models and per-session state."""

from pydantic import BaseModel
from typing import Optional
from dataclasses import dataclass, field


class Customer(BaseModel):
    """Customer record from CRM."""
    name: str
    phone: str
    email: Optional[str] = None
    address: Optional[str] = None
    previous_bookings: int = 0
    notes: Optional[str] = None


@dataclass
class SessionData:
    """
    Per-session structured data shared across all agents.

    Persists on `session.userdata` throughout the conversation lifecycle.
    Every agent reads and writes to this instead of parsing chat history.
    """
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_address: Optional[str] = None
    customer_email: Optional[str] = None
    service_type: Optional[str] = None
    preferred_date: Optional[str] = None
    preferred_time: Optional[str] = None
    job_description: Optional[str] = None
    intent: Optional[str] = None
    booking_ref: Optional[str] = None
    error_count: int = 0
    slot_attempts: dict = field(default_factory=dict)
