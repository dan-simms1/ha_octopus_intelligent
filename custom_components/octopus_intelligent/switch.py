from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN, OCTOPUS_SYSTEM
from .entity import OctopusIntelligentPerDeviceEntityMixin

import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    octopus_system = hass.data[DOMAIN][config_entry.entry_id][OCTOPUS_SYSTEM]
    devices = octopus_system.get_supported_device_ids()

    entities: list[SwitchEntity] = []
    for device_id in devices:
        entities.append(
            OctopusIntelligentSmartChargeSwitch(octopus_system, device_id=device_id)
        )
        entities.append(
            OctopusIntelligentBumpChargeSwitch(octopus_system, device_id=device_id)
        )

    if entities:
        async_add_entities(entities, False)


class OctopusIntelligentBumpChargeSwitch(
    OctopusIntelligentPerDeviceEntityMixin, CoordinatorEntity, SwitchEntity
):
    def __init__(self, octopus_system, *, device_id: str) -> None:
        super().__init__(octopus_system)
        self._octopus_system = octopus_system
        self._device_id = device_id
        base_unique_id = "octopus_intelligent_bump_charge"
        self._unique_id = f"{base_unique_id}_{slugify(device_id)}"
        self._is_on = octopus_system.is_boost_charging_now(device_id)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._is_on = self._octopus_system.is_boost_charging_now(self._device_id)
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        await self._octopus_system.async_start_boost_charge(self._device_id)
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        await self._octopus_system.async_cancel_boost_charge(self._device_id)
        self._is_on = False
        self.async_write_ha_state()

    @property
    def is_on(self):
        return self._is_on

    @property
    def name(self):
        return f"{self._equipment_label()} Bump Charge"

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        return bool(self._equipment_state())

    @property
    def device_info(self):
        return self._device_info()

    @property
    def icon(self):
        return "mdi:car-electric-outline"


class OctopusIntelligentSmartChargeSwitch(
    OctopusIntelligentPerDeviceEntityMixin, CoordinatorEntity, SwitchEntity
):
    def __init__(
        self,
        octopus_system,
        *,
        device_id: str,
    ) -> None:
        super().__init__(octopus_system)
        self._octopus_system = octopus_system
        self._device_id = device_id
        base_unique_id = "octopus_intelligent_smart_charging"
        self._unique_id = f"{base_unique_id}_{slugify(device_id)}"
        self._is_on = octopus_system.is_smart_charging_enabled(device_id)

    @property
    def name(self):
        return f"{self._equipment_label()} Octopus Smart Charging"

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        return bool(self._equipment_state())

    @property
    def is_on(self):
        return self._is_on

    @property
    def device_info(self):
        return self._device_info()

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

