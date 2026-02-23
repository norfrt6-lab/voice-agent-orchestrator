"""Dynamic prompt construction for context-aware agent instructions."""

from typing import Optional


def build_slot_collection_prompt(missing_slots: list[str], collected: dict[str, str]) -> str:
    """Build a dynamic instruction for the next slot to collect."""
    parts: list[str] = []
    if collected:
        parts.append("Information collected so far:")
        for key, value in collected.items():
            parts.append(f"  {key}: {value}")

    if missing_slots:
        parts.append(f"\nNow ask for their {missing_slots[0]}. Keep it natural and brief.")
    else:
        parts.append("\nAll details collected. Confirm the booking details with the caller.")

    return "\n".join(parts)


def build_confirmation_prompt(booking_details: dict[str, Optional[str]]) -> str:
    """Build the read-back confirmation prompt."""
    lines = ["Read back these details to the caller and ask them to confirm:"]
    for key, value in booking_details.items():
        if value is not None:
            display_key = key.replace("_", " ").replace("customer ", "")
            lines.append(f"  {display_key}: {value}")
    lines.append('\nAsk: "Does everything sound correct?"')
    return "\n".join(lines)


def build_alternative_times_prompt(
    original_date: str,
    original_time: str,
    alternatives: list[dict[str, str]],
) -> str:
    """Build prompt for offering alternative appointment times."""
    lines = [
        f"The requested time ({original_date} at {original_time}) is not available.",
        "Offer these alternatives to the caller:",
    ]
    for alt in alternatives[:3]:
        lines.append(f"  {alt['date']} at {alt['time']} with {alt['technician']}")
    lines.append("\nAsk which option works for them, or if they'd prefer a different day.")
    return "\n".join(lines)
