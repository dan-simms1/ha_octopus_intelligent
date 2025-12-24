from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN, OCTOPUS_SYSTEM
from .util import format_equipment_name

import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    octopus_system = hass.data[DOMAIN][config_entry.entry_id][OCTOPUS_SYSTEM]
    devices = list(((octopus_system.data or {}).get("devices") or {}).keys())

    entities: list[SwitchEntity] = [
        OctopusIntelligentBumpChargeSwitch(octopus_system),
        OctopusIntelligentSmartChargeSwitch(octopus_system, legacy=True),
    ]

    for device_id in devices:
        entities.append(
            OctopusIntelligentSmartChargeSwitch(octopus_system, device_id=device_id)
        )

    async_add_entities(entities, False)


class OctopusIntelligentBumpChargeSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(self, octopus_system) -> None:
        super().__init__(octopus_system)
        self._unique_id = "octopus_intelligent_bump_charge"
        self._name = "Octopus Bump Charge"
        self._octopus_system = octopus_system
        self._is_on = octopus_system.is_boost_charging_now()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._is_on = self._octopus_system.is_boost_charging_now()
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        await self._octopus_system.async_start_boost_charge()
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        await self._octopus_system.async_cancel_boost_charge()
        self._is_on = False
        self.async_write_ha_state()

    @property
    def is_on(self):
        return self._is_on

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def device_info(self):
        return {
            "identifiers": {
                ("AccountID", self._octopus_system.account_id),
            },
            "name": "Octopus Intelligent Tariff",
            "manufacturer": "Octopus",
        }

    @property
    def icon(self):
        return "mdi:car-electric-outline"


class OctopusIntelligentSmartChargeSwitch(CoordinatorEntity, SwitchEntity):
    def __init__(
        self,
        octopus_system,
        *,
        device_id: str | None = None,
        legacy: bool = False,
    ) -> None:
        super().__init__(octopus_system)
        self._octopus_system = octopus_system
        self._device_id = device_id
        self._legacy = legacy or device_id is None
        base_unique_id = "octopus_intelligent_smart_charging"
        self._unique_id = (
            base_unique_id
            if self._legacy or not device_id
            else f"{base_unique_id}_{slugify(device_id)}"
        )
        self._is_on = octopus_system.is_smart_charging_enabled(device_id)

    def _equipment_state(self) -> dict[str, Any] | None:
        if not self._device_id:
            return None
        devices = (self._octopus_system.data or {}).get("devices") or {}
        return devices.get(self._device_id)

    def _equipment_label(self) -> str:
        device_state = self._equipment_state() or {}
        device = device_state.get("device")
        fallback = f"Equipment {self._device_id}" if self._device_id else "Equipment"
        return format_equipment_name(device, fallback=fallback)

    @property
    def name(self):
        if self._legacy or not self._device_id:
            return "Octopus Smart Charging"
        return f"{self._equipment_label()} Smart Charging"

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        if self._device_id and not self._equipment_state():
            return False
        return True

    @property
    def is_on(self):
        return self._is_on

    @property
    def device_info(self):
        if self._legacy or not self._device_id:
            return {
                "identifiers": {
                    ("AccountID", self._octopus_system.account_id),
                },
                "name": "Octopus Intelligent Tariff",
                "manufacturer": "Octopus",
            }

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
    def icon(self):
        return "mdi:flash-auto"

    @callback
    def _handle_coordinator_update(self) -> None:
        self._is_on = self._octopus_system.is_smart_charging_enabled(self._device_id)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        await self._octopus_system.async_resume_smart_charging(self._device_id)
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        await self._octopus_system.async_suspend_smart_charging(self._device_id)
        self._is_on = False
        self.async_write_ha_state()

