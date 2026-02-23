"""Shared utilities used across the voice agent orchestrator."""

import re


def normalize_phone(value: str) -> str:
    """Normalize a phone number by stripping everything except digits and a leading +.

    Examples:
        >>> normalize_phone("0412 345 678")
        '0412345678'
        >>> normalize_phone("+61 (412) 345-678")
        '+61412345678'
    """
    value = value.strip()
    if value.startswith("+"):
        return "+" + re.sub(r"[^\d]", "", value[1:])
    return re.sub(r"[^\d]", "", value)
