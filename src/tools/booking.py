"""
Mock booking creation system.

In production, this would integrate with a CRM / scheduling platform
(ServiceTitan, Jobber, Housecall Pro, or a custom backend).
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, TypedDict

logger = logging.getLogger(__name__)


class BookingRecord(TypedDict):
    """Full booking record stored in the system."""

    booking_ref: str
    customer_name: str
    customer_phone: str
    service_type: str
    date: str
    time: str
    address: str
    job_description: str
    technician: str
    status: str
    created_at: str


class BookingResult(TypedDict, total=False):
    """Result from create_booking, cancel_booking, or reschedule_booking."""

    success: bool
    message: str
    booking_ref: str
    details: BookingRecord

_bookings: dict[str, BookingRecord] = {}


def create_booking(
    name: str,
    phone: str,
    service: str,
    date: str,
    time: str,
    address: str,
    description: Optional[str] = None,
    technician: Optional[str] = None,
) -> BookingResult:
    """Create a new booking and return the confirmation details."""
    missing = [
        field_name
        for field_name, value in [
            ("name", name),
            ("phone", phone),
            ("service", service),
            ("date", date),
            ("time", time),
            ("address", address),
        ]
        if not value or not value.strip()
    ]
    if missing:
        return {
            "success": False,
            "message": f"Cannot create booking - missing required fields: {', '.join(missing)}.",
        }

    ref = f"BK-{uuid.uuid4().hex[:6].upper()}"

    booking = {
        "booking_ref": ref,
        "customer_name": name,
        "customer_phone": phone,
        "service_type": service,
        "date": date,
        "time": time,
        "address": address,
        "job_description": description or "",
        "technician": technician or "To be assigned",
        "status": "confirmed",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    _bookings[ref] = booking
    logger.info("Booking created: %s for %s on %s at %s", ref, name, date, time)

    return {
        "success": True,
        "booking_ref": ref,
        "message": f"Booking confirmed. Reference number: {ref}. {service} on {date} at {time}.",
        "details": booking,
    }


def cancel_booking(booking_ref: str) -> BookingResult:
    """Cancel an existing booking by reference number."""
    if booking_ref not in _bookings:
        return {"success": False, "message": f"Booking {booking_ref} not found."}
    _bookings[booking_ref]["status"] = "cancelled"
    logger.info("Booking cancelled: %s", booking_ref)
    return {"success": True, "message": f"Booking {booking_ref} has been cancelled."}


def reschedule_booking(booking_ref: str, new_date: str, new_time: str) -> BookingResult:
    """Reschedule an existing booking to a new date/time."""
    if booking_ref not in _bookings:
        return {"success": False, "message": f"Booking {booking_ref} not found."}
    _bookings[booking_ref].update(date=new_date, time=new_time, status="rescheduled")
    logger.info("Booking rescheduled: %s to %s %s", booking_ref, new_date, new_time)
    return {
        "success": True,
        "message": f"Booking {booking_ref} rescheduled to {new_date} at {new_time}.",
        "details": _bookings[booking_ref],
    }


def get_booking(booking_ref: str) -> Optional[BookingRecord]:
    """Retrieve a booking by reference number."""
    return _bookings.get(booking_ref)


def reset() -> None:
    """Clear all bookings. Used by test fixtures for isolation."""
    _bookings.clear()
