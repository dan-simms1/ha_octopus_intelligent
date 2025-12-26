from __future__ import annotations

from typing import Any

from .const import DOMAIN
from .util import format_equipment_name


class OctopusIntelligentPerDeviceEntityMixin:
    """Helper mixin that provides per-device lookups shared by entities."""

    _octopus_system: Any
    _device_id: str | None

    def _equipment_state(self) -> dict[str, Any] | None:
        if not getattr(self, "_device_id", None):
            return None
        devices = (self._octopus_system.data or {}).get("devices") or {}
        return devices.get(self._device_id)

    def _equipment_label(self, *, fallback: str | None = None) -> str:
        label_fallback = fallback or (
            f"Equipment {self._device_id}" if self._device_id else "Equipment"
        )
        device_state = self._equipment_state() or {}
        device = device_state.get("device")
        return format_equipment_name(device, fallback=label_fallback)

    def _name_prefix(self) -> str:
        if getattr(self, "_is_combined", False):
            return "Intelligent"
        label = self._equipment_label()
        return label or "Intelligent"

    def _prefixed_name(self, suffix: str) -> str:
        prefix = self._name_prefix()
        suffix_value = (suffix or "").strip()
        if not prefix:
            return suffix_value
        if not suffix_value:
            return prefix
        return f"{prefix} {suffix_value}"

    def _device_info(self) -> dict[str, Any]:
        device_state = self._equipment_state() or {}
        device = device_state.get("device") or {}
        manufacturer = device.get("provider") or "Octopus"
        identifier = f"{self._octopus_system.account_id}_{self._device_id}"
        return {
            "identifiers": {(DOMAIN, identifier)},
            "name": self._equipment_label(),
            "manufacturer": manufacturer,
        }
