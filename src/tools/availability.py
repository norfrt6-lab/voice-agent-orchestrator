"""
Mock calendar availability system.

In production, this would integrate with ServiceTitan, Jobber, Housecall Pro,
or a custom scheduling API via HTTP client.
"""

import logging
import random
from datetime import datetime, timedelta
from typing import Optional, TypedDict

logger = logging.getLogger(__name__)


class TimeSlot(TypedDict):
    """A single available time slot."""

    time: str
    technician: str
    date: str


class AvailabilityResult(TypedDict):
    """Result from check_availability."""

    available: bool
    slots: list[TimeSlot]
    next_available: Optional[str]
    message: str


class DateAvailability(TypedDict):
    """Summary of availability for a single date."""

    date: str
    day_name: str
    slot_count: int

# Schedule generation parameters
SCHEDULE_DAYS = 14
AVAILABILITY_PROBABILITY = 0.7
SCHEDULE_SEED = 42
MAX_SLOTS_RETURNED = 5

TECHNICIANS: dict[str, list[str]] = {
    "plumbing": ["Mike T.", "Sarah L."],
    "electrical": ["James K.", "Priya M."],
    "hvac": ["Dave W.", "Lisa C."],
    "general handyman": ["Tom R.", "Alex B."],
    "drain cleaning": ["Mike T.", "Dave W."],
    "emergency repair": ["Mike T.", "James K.", "Dave W."],
}


def _generate_schedule() -> dict[str, dict]:
    """Generate a realistic 14-day schedule with ~70% availability."""
    schedule: dict[str, dict] = {}
    base = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    for day_offset in range(1, SCHEDULE_DAYS + 1):
        date = base + timedelta(days=day_offset)
        if date.weekday() == 6:  # Sunday closed
            continue

        date_str = date.strftime("%Y-%m-%d")
        day_name = date.strftime("%A")

        hours = [9, 10, 11, 12, 13] if date.weekday() == 5 else [8, 9, 10, 11, 13, 14, 15, 16, 17]

        available_times = [
            f"{h:02d}:00" for h in hours if random.random() < AVAILABILITY_PROBABILITY
        ]
        schedule[date_str] = {"day_name": day_name, "times": available_times}

    return schedule


random.seed(SCHEDULE_SEED)
MOCK_SCHEDULE = _generate_schedule()


def check_availability(
    service_type: str, date: str, preferred_time: Optional[str] = None
) -> AvailabilityResult:
    """
    Check appointment availability for a service on a given date.

    Returns a structured dict with availability status, available slots,
    and next-available fallback when the requested date is unavailable.
    """
    techs = TECHNICIANS.get(service_type, TECHNICIANS["general handyman"])

    if date not in MOCK_SCHEDULE:
        next_date = _find_next_available()
        return {
            "available": False,
            "slots": [],
            "next_available": next_date,
            "message": f"No availability on {date}.",
        }

    day_data = MOCK_SCHEDULE[date]

    if preferred_time and preferred_time in day_data["times"]:
        tech = random.choice(techs)
        return {
            "available": True,
            "slots": [{"time": preferred_time, "technician": tech, "date": date}],
            "next_available": None,
            "message": f"Available on {date} at {preferred_time} with {tech}.",
        }

    if day_data["times"]:
        slots = [
            {"time": t, "technician": random.choice(techs), "date": date}
            for t in day_data["times"][:MAX_SLOTS_RETURNED]
        ]
        return {
            "available": True,
            "slots": slots,
            "next_available": None,
            "message": f"{len(slots)} time slots available on {date}.",
        }

    next_date = _find_next_available()
    return {
        "available": False,
        "slots": [],
        "next_available": next_date,
        "message": f"No slots available on {date}.",
    }


def get_available_dates(service_type: str, limit: int = 5) -> list[DateAvailability]:
    """Get the next N dates with available slots."""
    results = []
    for date_str, day_data in sorted(MOCK_SCHEDULE.items()):
        if day_data["times"]:
            results.append(
                {
                    "date": date_str,
                    "day_name": day_data["day_name"],
                    "slot_count": len(day_data["times"]),
                }
            )
        if len(results) >= limit:
            break
    return results


def _find_next_available() -> Optional[str]:
    for date_str, day_data in sorted(MOCK_SCHEDULE.items()):
        if day_data["times"]:
            return f"{date_str} {day_data['times'][0]}"
    return None


def reset() -> None:
    """Re-seed random state for deterministic tests."""
    random.seed(SCHEDULE_SEED)
