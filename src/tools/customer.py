"""
Mock customer lookup system.

In production, this would query a CRM database (e.g. HubSpot, Salesforce,
ServiceTitan customer records) to identify returning callers.
"""

import logging
from typing import Optional, TypedDict

from src.utils import normalize_phone

logger = logging.getLogger(__name__)


class CustomerRecord(TypedDict):
    """Customer record stored in the system."""

    name: str
    phone: str
    email: str
    address: str
    previous_bookings: int
    notes: str

_customers: dict[str, CustomerRecord] = {
    "0412345678": {
        "name": "John Smith",
        "phone": "0412345678",
        "email": "john.smith@email.com",
        "address": "42 Oak Avenue, Richmond VIC 3121",
        "previous_bookings": 3,
        "notes": "Preferred morning appointments. Has a large dog.",
    },
    "0498765432": {
        "name": "Sarah Johnson",
        "phone": "0498765432",
        "email": "sarah.j@email.com",
        "address": "15 Elm Street, South Yarra VIC 3141",
        "previous_bookings": 1,
        "notes": "",
    },
}


def lookup_customer(phone: str) -> Optional[CustomerRecord]:
    """Look up a customer by phone number. Returns None if not found."""
    cleaned = normalize_phone(phone)
    if cleaned.startswith("+61"):
        cleaned = "0" + cleaned[3:]
    result = _customers.get(cleaned)
    if result:
        logger.debug("Returning customer found: %s", result["name"])
    return result


def create_customer(
    name: str, phone: str, email: Optional[str] = None, address: Optional[str] = None
) -> CustomerRecord:
    """Create a new customer record."""
    cleaned = normalize_phone(phone)
    customer = {
        "name": name,
        "phone": cleaned,
        "email": email or "",
        "address": address or "",
        "previous_bookings": 0,
        "notes": "",
    }
    _customers[cleaned] = customer
    logger.info("New customer created: %s (%s)", name, cleaned)
    return customer
