from datetime import timedelta
from typing import Any, Mapping


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
    # Sort the time ranges by start time
    date_ranges.sort(key=lambda r: r["start"])
    
    # initialize the list of merged date ranges
    merged_date_ranges = []
    
    # initialize the current date range with the first date range in the list
    current_date_range = date_ranges[0]
    
    # iterate through the rest of the date ranges
    for i in range(1, len(date_ranges)):
        # if the current date range overlaps with the next date range, update the end date of the current date range
        if current_date_range["end"] >= date_ranges[i]["start"]:
            current_date_range["end"] = max(current_date_range["end"], date_ranges[i]["end"])
        # if the current date range does not overlap with the next date range, add the current date range to the list of merged date ranges and update the current date range
        else:
            merged_date_ranges.append(current_date_range)
            current_date_range = date_ranges[i]
    
    # add the final date range to the list of merged date ranges
    merged_date_ranges.append(current_date_range)
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
