from __future__ import annotations

from datetime import timedelta
from typing import Any, Mapping

from .const import (
    ALLOWED_DEVICE_TYPES,
    UNSUPPORTED_DEVICE_KEYWORDS,
    UNSUPPORTED_DEVICE_PROVIDERS,
    UNSUPPORTED_DEVICE_IDENTIFIERS,
)


def to_timedelta(str_time: str) -> timedelta:
    """Convert a time string to a timedelta."""
    parts = str_time.split(":")
    if len(parts) == 2:
        hours, minutes = parts
        seconds = 0
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        raise ValueError(f"Invalid time string '{str_time}'")

    return timedelta(hours=int(hours), minutes=int(minutes), seconds=int(seconds))

def to_time_string(td: timedelta) -> str:
    """Convert a timedelta to a HH:mm time string."""
    return f"{td.seconds // 3600:02}:{td.seconds // 60 % 60:02}"

def to_hours_after_midnight(str_time: str) -> float:
    td = to_timedelta(str_time)
    return td.seconds / 3600

def normalize_time_string(value: str | None) -> str | None:
    """Return HH:MM even if API provides HH:MM:SS."""
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    parts = trimmed.split(":")
    if len(parts) == 3 and parts[2] == "00":
        return f"{parts[0]}:{parts[1]}"
    return trimmed


def merge_and_sort_time_ranges(date_ranges: list) -> list:
    if not date_ranges:
        return []

    sorted_ranges = sorted(date_ranges, key=lambda r: r["start"])
    merged_date_ranges = [sorted_ranges[0]]

    for next_range in sorted_ranges[1:]:
        current = merged_date_ranges[-1]
        if current["end"] >= next_range["start"]:
            current["end"] = max(current["end"], next_range["end"])
        else:
            merged_date_ranges.append(next_range)

    return merged_date_ranges


def format_equipment_name(device: Mapping[str, Any] | None, fallback: str | None = None) -> str:
    """Return a friendly label for an Octopus Intelligent device."""
    if not isinstance(device, Mapping):
        device = {}

    parts: list[str] = []
    seen: set[str] = set()

    def _add_part(raw_value: str | None) -> None:
        if not isinstance(raw_value, str):
            return
        trimmed = raw_value.strip()
        if not trimmed:
            return
        normalized = " ".join(trimmed.upper().split())
        if normalized in seen:
            return
        seen.add(normalized)
        parts.append(trimmed)

    def _looks_like_identifier(raw_value: str | None) -> bool:
        if not isinstance(raw_value, str):
            return False
        value = raw_value.strip()
        if not value:
            return False
        has_lower = any(ch.islower() for ch in value)
        has_identifier_chars = any(ch.isdigit() or ch in {"_", "-"} for ch in value)
        return not has_lower and has_identifier_chars

    label_value = device.get("label")
    label_is_identifier = _looks_like_identifier(label_value)
    if isinstance(label_value, str) and label_value.strip() and not label_is_identifier:
        return label_value.strip()

    if label_value and not label_is_identifier:
        _add_part(label_value)

    make = device.get("make") or device.get("vehicleMake") or device.get("chargePointMake")
    model = device.get("model") or device.get("vehicleModel") or device.get("chargePointModel")
    name = " ".join(part for part in [make, model] if isinstance(part, str) and part.strip())
    _add_part(name if name else None)

    provider_value = device.get("provider")
    if not _looks_like_identifier(provider_value):
        _add_part(provider_value)

    if parts:
        return " - ".join(parts)

    if label_value and isinstance(label_value, str) and label_value.strip():
        return label_value.strip()

    fallback_value = fallback or device.get("id")
    if isinstance(fallback_value, str) and fallback_value.strip():
        return fallback_value.strip()

    return "Octopus Intelligent Equipment"

def _normalize_identifier(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    uppercase = value.upper()
    normalized = [
        ch
        for ch in uppercase
        if ch.isalnum()
    ]
    return "".join(normalized)


def is_supported_equipment(device: Mapping[str, Any] | None) -> bool:
    """Return True if the device represents a controllable vehicle or charger."""
    if not isinstance(device, Mapping):
        return False

    provider = _normalize_identifier(device.get("provider"))
    if provider and provider in UNSUPPORTED_DEVICE_PROVIDERS:
        return False

    label = _normalize_identifier(device.get("label"))
    if label and label in UNSUPPORTED_DEVICE_IDENTIFIERS:
        return False

    device_identifier = _normalize_identifier(device.get("id"))
    if device_identifier and device_identifier in UNSUPPORTED_DEVICE_IDENTIFIERS:
        return False

    device_type = device.get("deviceType")
    if not isinstance(device_type, str) or not device_type.strip():
        return False

    normalized = device_type.strip().upper()
    if normalized not in ALLOWED_DEVICE_TYPES:
        return False

    if any(keyword in normalized for keyword in UNSUPPORTED_DEVICE_KEYWORDS):
        return False

    return True
