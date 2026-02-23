"""Service catalog with pricing, durations, and descriptions."""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

SERVICE_CATALOG: dict[str, dict] = {
    "plumbing": {
        "name": "Plumbing Service",
        "description": "All plumbing repairs, installations, and maintenance including taps, toilets, pipes, and hot water systems.",
        "price_range": "$120 - $350",
        "call_out_fee": "$89",
        "typical_duration": "1-3 hours",
        "emergency_available": True,
    },
    "electrical": {
        "name": "Electrical Service",
        "description": "Electrical repairs, installations, safety inspections, switchboard upgrades, and lighting.",
        "price_range": "$150 - $400",
        "call_out_fee": "$99",
        "typical_duration": "1-4 hours",
        "emergency_available": True,
    },
    "hvac": {
        "name": "HVAC Service",
        "description": "Heating, ventilation, and air conditioning installation, repair, and maintenance.",
        "price_range": "$150 - $500",
        "call_out_fee": "$99",
        "typical_duration": "1-4 hours",
        "emergency_available": False,
    },
    "general handyman": {
        "name": "General Handyman",
        "description": "General repairs, furniture assembly, painting, door and window repairs.",
        "price_range": "$80 - $250",
        "call_out_fee": "$69",
        "typical_duration": "1-2 hours",
        "emergency_available": False,
    },
    "drain cleaning": {
        "name": "Drain Cleaning",
        "description": "Blocked drains, CCTV drain inspection, and high-pressure jet cleaning.",
        "price_range": "$150 - $400",
        "call_out_fee": "$89",
        "typical_duration": "1-2 hours",
        "emergency_available": True,
    },
    "emergency repair": {
        "name": "Emergency Repair",
        "description": "24/7 emergency service for burst pipes, gas leaks, electrical faults, and flooding.",
        "price_range": "$250 - $600",
        "call_out_fee": "$149",
        "typical_duration": "1-4 hours",
        "emergency_available": True,
    },
}

SERVICE_ALIASES: dict[str, str] = {
    "plumber": "plumbing", "pipes": "plumbing", "toilet": "plumbing",
    "tap": "plumbing", "hot water": "plumbing", "water heater": "plumbing",
    "electrician": "electrical", "wiring": "electrical", "power": "electrical",
    "lights": "electrical", "switchboard": "electrical",
    "heating": "hvac", "cooling": "hvac", "air conditioning": "hvac",
    "aircon": "hvac", "ac": "hvac",
    "handyman": "general handyman", "painting": "general handyman",
    "drain": "drain cleaning", "blocked drain": "drain cleaning", "clogged": "drain cleaning",
    "emergency": "emergency repair", "urgent": "emergency repair",
    "burst pipe": "emergency repair", "gas leak": "emergency repair",
    "flooding": "emergency repair",
}


def get_valid_service_terms() -> list[str]:
    """Return all recognized service terms (catalog IDs + alias keys).

    This is the single source of truth for service validation across
    slot_manager, guardrails, and any other module that needs to check
    whether a user query refers to a valid service.
    """
    return list(SERVICE_CATALOG.keys()) + list(SERVICE_ALIASES.keys())


def get_all_services() -> list[dict]:
    """Return all services with basic info."""
    return [
        {"id": sid, "name": info["name"], "price_range": info["price_range"]}
        for sid, info in SERVICE_CATALOG.items()
    ]


def get_service_details(service_id: str) -> Optional[dict]:
    """Get full details for a specific service."""
    normalized = service_id.lower().strip()
    for sid, info in SERVICE_CATALOG.items():
        if sid == normalized or normalized in sid or sid in normalized:
            return {"id": sid, **info}
    return None


def match_service(query: str) -> Optional[str]:
    """Match a user query to a service ID. Returns None if no match."""
    normalized = query.lower().strip()
    for alias, service_id in SERVICE_ALIASES.items():
        if alias in normalized:
            return service_id
    for sid in SERVICE_CATALOG:
        if sid in normalized or normalized in sid:
            return sid
    return None
