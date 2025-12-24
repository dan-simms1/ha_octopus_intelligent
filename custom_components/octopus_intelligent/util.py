from datetime import timedelta
from typing import Any, Mapping

from .const import (
    SUPPORTED_DEVICE_TYPES,
    UNSUPPORTED_DEVICE_KEYWORDS,
    UNSUPPORTED_DEVICE_PROVIDERS,
)


def to_timedelta(str_time: str) -> timedelta:
    """Convert a time string to a timedelta."""
    hours, minutes = str_time.split(":")
    return timedelta(hours=int(hours), minutes=int(minutes))

def to_time_string(td: timedelta) -> str:
    """Convert a timedelta to a HH:mm time string."""
    return f"{td.seconds // 3600:02}:{td.seconds // 60 % 60:02}"

def to_hours_after_midnight(str_time: str) -> float:
    td = to_timedelta(str_time)
    return td.seconds / 3600


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
    label = device.get("label")
    if isinstance(label, str) and label.strip():
        parts.append(label.strip())

    make = device.get("make") or device.get("vehicleMake") or device.get("chargePointMake")
    model = device.get("model") or device.get("vehicleModel") or device.get("chargePointModel")
    name = " ".join(part for part in [make, model] if isinstance(part, str) and part.strip())
    if name:
        parts.append(name)

    provider = device.get("provider")
    if isinstance(provider, str) and provider.strip():
        provider_value = provider.strip()
        if provider_value not in parts:
            parts.append(provider_value)

    if parts:
        return " - ".join(parts)

    fallback_value = fallback or device.get("id")
    if isinstance(fallback_value, str) and fallback_value.strip():
        return fallback_value.strip()

    return "Octopus Intelligent Equipment"


def is_supported_equipment(device: Mapping[str, Any] | None) -> bool:
    """Return True if the device represents a controllable vehicle or charger."""
    if not isinstance(device, Mapping):
        return False

    provider = device.get("provider")
    if isinstance(provider, str) and provider.strip():
        if provider.strip().upper() in UNSUPPORTED_DEVICE_PROVIDERS:
            return False

    label = device.get("label")
    if isinstance(label, str) and label.strip():
        if label.strip().upper() in UNSUPPORTED_DEVICE_PROVIDERS:
            return False

    device_type = device.get("deviceType")
    if isinstance(device_type, str) and device_type.strip():
        normalized = device_type.strip().upper()
        if any(keyword in normalized for keyword in UNSUPPORTED_DEVICE_KEYWORDS):
            return False
        if normalized in SUPPORTED_DEVICE_TYPES:
            return True

    indicative_fields = (
        "make",
        "model",
        "vehicleMake",
        "vehicleModel",
        "chargePointMake",
        "chargePointModel",
    )
    return any(
        isinstance(device.get(field), str) and device.get(field).strip()
        for field in indicative_fields
    )
