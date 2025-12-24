from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import (
    DOMAIN,
    OCTOPUS_SYSTEM,
    INTELLIGENT_CHARGE_TIMES,
    INTELLIGENT_SOC_OPTIONS,
)
from .util import format_equipment_name

import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    octopus_system = hass.data[DOMAIN][config_entry.entry_id][OCTOPUS_SYSTEM]
    device_ids = octopus_system.get_supported_device_ids()

    entities: list[SelectEntity] = []
    for device_id in device_ids:
        entities.append(OctopusIntelligentTargetSoc(octopus_system, device_id=device_id))
        entities.append(OctopusIntelligentTargetTime(octopus_system, device_id=device_id))

    if entities:
        async_add_entities(entities, False)


class OctopusIntelligentTargetSoc(CoordinatorEntity, SelectEntity):
    def __init__(
        self,
        octopus_system,
        *,
        device_id: str,
    ) -> None:
        super().__init__(octopus_system)
        self._octopus_system = octopus_system
        self._device_id = device_id
        base_unique_id = "octopus_intelligent_target_soc"
        self._unique_id = f"{base_unique_id}_{slugify(device_id)}"
        self._options = [f"{value}" for value in INTELLIGENT_SOC_OPTIONS]
        self._current_option: str | None = None
        self._refresh_current_option()

    def _equipment_state(self) -> dict[str, Any] | None:
        if not self._device_id:
            return None
        devices = (self._octopus_system.data or {}).get("devices") or {}
        return devices.get(self._device_id)

    def _equipment_label(self) -> str:
        device_state = self._equipment_state() or {}
        device = device_state.get("device")
        fallback = f"Equipment {self._device_id}"
        return format_equipment_name(device, fallback=fallback)

    @property
    def name(self) -> str:
        return f"{self._equipment_label()} Target State of Charge"

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def options(self) -> list[str]:
        return self._options

    @property
    def current_option(self) -> str | None:
        return self._current_option

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        return bool(self._equipment_state())

    @property
    def device_info(self):
        device_state = self._equipment_state() or {}
        device = device_state.get("device") or {}
        manufacturer = device.get("provider") or "Octopus"
        identifier = f"{self._octopus_system.account_id}_{self._device_id}"
        return {
            "identifiers": {(DOMAIN, identifier)},
            "name": self._equipment_label(),
            "manufacturer": manufacturer,
            "via_device": ("AccountID", self._octopus_system.account_id),
        }

    @property
    def unit_of_measurement(self) -> str:
        return PERCENTAGE

    @property
    def icon(self) -> str:
        return "mdi:battery-charging-medium"

    @callback
    def _handle_coordinator_update(self) -> None:
        previous = self._current_option
        self._refresh_current_option()
        if self._current_option != previous:
            self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        try:
            selected_target = int(option.replace("%", ""))
        except ValueError:
            _LOGGER.warning("Invalid target SOC option %s", option)
            return
        await self._octopus_system.async_set_target_soc(selected_target, self._device_id)
        self._current_option = option
        self.async_write_ha_state()

    def _refresh_current_option(self) -> None:
        target_soc = self._octopus_system.get_target_soc(self._device_id)
        self._current_option = f"{target_soc}" if target_soc is not None else None


class OctopusIntelligentTargetTime(CoordinatorEntity, SelectEntity):
    def __init__(
        self,
        octopus_system,
        *,
        device_id: str,
    ) -> None:
        super().__init__(octopus_system)
        self._octopus_system = octopus_system
        self._device_id = device_id
        base_unique_id = "octopus_intelligent_target_time"
        self._unique_id = f"{base_unique_id}_{slugify(device_id)}"
        self._options = list(INTELLIGENT_CHARGE_TIMES)
        self._current_option: str | None = None
        self._refresh_current_option()

    def _equipment_state(self) -> dict[str, Any] | None:
        if not self._device_id:
            return None
        devices = (self._octopus_system.data or {}).get("devices") or {}
        return devices.get(self._device_id)

    def _equipment_label(self) -> str:
        device_state = self._equipment_state() or {}
        device = device_state.get("device")
        fallback = f"Equipment {self._device_id}"
        return format_equipment_name(device, fallback=fallback)

    @property
    def name(self) -> str:
        return f"{self._equipment_label()} Target Ready By Time"

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def options(self) -> list[str]:
        return self._options

    @property
    def current_option(self) -> str | None:
        return self._current_option

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        return bool(self._equipment_state())

    @property
    def device_info(self):
        device_state = self._equipment_state() or {}
        device = device_state.get("device") or {}
        manufacturer = device.get("provider") or "Octopus"
        identifier = f"{self._octopus_system.account_id}_{self._device_id}"
        return {
            "identifiers": {(DOMAIN, identifier)},
            "name": self._equipment_label(),
            "manufacturer": manufacturer,
            "via_device": ("AccountID", self._octopus_system.account_id),
        }

    @property
    def icon(self) -> str:
        return "mdi:clock-time-seven-outline"

    @callback
    def _handle_coordinator_update(self) -> None:
        previous = self._current_option
        self._refresh_current_option()
        if self._current_option != previous:
            self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        await self._octopus_system.async_set_target_time(option, self._device_id)
        self._current_option = option
        self.async_write_ha_state()

    def _refresh_current_option(self) -> None:
        self._current_option = self._octopus_system.get_target_time(self._device_id)

