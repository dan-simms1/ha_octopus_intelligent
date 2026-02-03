from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)
from homeassistant.const import PERCENTAGE
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    async_track_utc_time_change
)
from homeassistant.helpers.device_registry import DeviceEntryType
from .const import DOMAIN, OCTOPUS_SYSTEM
from .entity import OctopusIntelligentPerDeviceEntityMixin
from .util import format_equipment_name, normalize_time_string
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.util import slugify
import homeassistant.util.dt as dt_util

import logging
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    octopus_system = hass.data[DOMAIN][config_entry.entry_id][OCTOPUS_SYSTEM]
    device_ids = octopus_system.get_supported_device_ids()

    entities: list[SensorEntity] = [
        OctopusIntelligentNextOffpeakTime(hass, octopus_system),
        OctopusIntelligentOffpeakEndTime(hass, octopus_system),
        OctopusIntelligentChargingStartSensor(hass, octopus_system),
    ]

    for device_id in device_ids:
        entities.append(
            OctopusIntelligentNextOffpeakTime(hass, octopus_system, device_id=device_id)
        )
        entities.append(
            OctopusIntelligentOffpeakEndTime(hass, octopus_system, device_id=device_id)
        )
        entities.append(
            OctopusIntelligentChargingStartSensor(
                hass,
                octopus_system,
                device_id=device_id,
            )
        )
        entities.append(
            OctopusIntelligentTargetReadyTimeSensor(
                octopus_system,
                device_id=device_id,
            )
        )
        entities.append(
            OctopusIntelligentTargetSocSensor(
                octopus_system,
                device_id=device_id,
            )
        )

    async_add_entities(entities, False)


class OctopusIntelligentNextOffpeakTime(
    OctopusIntelligentPerDeviceEntityMixin, CoordinatorEntity, SensorEntity
):
    def __init__(self, hass, octopus_system, *, device_id: str | None = None) -> None:
        """Initialize the sensor."""
        super().__init__(octopus_system)
        self._octopus_system = octopus_system
        self._device_id = device_id
        self._is_combined = device_id is None
        base_unique_id = "octopus_intelligent_next_offpeak_start"
        self._unique_id = (
            base_unique_id
            if self._is_combined
            else f"{base_unique_id}_{slugify(device_id)}"
        )
        self._timer = async_track_utc_time_change(
            hass, self.timer_update, minute=range(0, 60, 30), second=1
        )
        self._attributes = {}
        self._native_value = None
        self._set_native_value(log_on_error=False)

    def _set_native_value(self, log_on_error: bool = True):
        try:
            self._native_value = self._octopus_system.next_offpeak_start_utc(
                device_id=self._device_id
            )
            return True
        except Exception:  # pylint: disable=broad-except
            if log_on_error:
                _LOGGER.exception("Could not set native_value")
        return False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._set_native_value():
            self.async_write_ha_state()

    @callback
    async def timer_update(self, time):
        """Refresh state when timer is fired."""
        if self._set_native_value():
            self.async_write_ha_state()

    @property
    def name(self):
        return self._prefixed_name("Next Offpeak Start")

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def native_value(self):
        return self._native_value

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def device_class(self):
        return SensorDeviceClass.TIMESTAMP

    @property
    def device_info(self):
        if self._is_combined:
            return {
                "identifiers": {
                    ("AccountID", self._octopus_system.account_id),
                },
                "name": "Octopus Intelligent Tariff",
                "manufacturer": "Octopus",
                "entry_type": DeviceEntryType.SERVICE,
            }

        info = self._device_info()
        info["via_device"] = ("AccountID", self._octopus_system.account_id)
        return info

    @property
    def icon(self):
        return "mdi:home-clock-outline"

    async def async_will_remove_from_hass(self):
        self._timer()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._handle_coordinator_update()


class OctopusIntelligentOffpeakEndTime(
    OctopusIntelligentPerDeviceEntityMixin, CoordinatorEntity, SensorEntity
):
    def __init__(self, hass, octopus_system, *, device_id: str | None = None) -> None:
        """Initialize the sensor."""
        super().__init__(octopus_system)
        self._octopus_system = octopus_system
        self._device_id = device_id
        self._is_combined = device_id is None
        base_unique_id = "octopus_intelligent_offpeak_end"
        self._unique_id = (
            base_unique_id
            if self._is_combined
            else f"{base_unique_id}_{slugify(device_id)}"
        )
        self._timer = async_track_utc_time_change(
            hass, self.timer_update, minute=range(0, 60, 30), second=1
        )
        self._attributes = {}
        self._native_value = None
        self._set_native_value(log_on_error=False)

    def _set_native_value(self, log_on_error: bool = True):
        utcnow = dt_util.utcnow()
        offpeak_range = self._octopus_system.next_offpeak_range_utc(
            device_id=self._device_id
        )
        if not offpeak_range:
            return False

        if offpeak_range["start"] <= utcnow:
            try:
                self._native_value = offpeak_range["end"]
                return True
            except Exception:  # pylint: disable=broad-except
                if log_on_error:
                    _LOGGER.exception("Could not set native_value")
        return False

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._set_native_value():
            self.async_write_ha_state()

    @callback
    async def timer_update(self, time):
        if self._set_native_value():
            self.async_write_ha_state()

    @property
    def name(self):
        return self._prefixed_name("Offpeak End")

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def native_value(self):
        return self._native_value

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def device_class(self):
        return SensorDeviceClass.TIMESTAMP

    @property
    def device_info(self):
        if self._is_combined:
            return {
                "identifiers": {
                    ("AccountID", self._octopus_system.account_id),
                },
                "name": "Octopus Intelligent Tariff",
                "manufacturer": "Octopus",
                "entry_type": DeviceEntryType.SERVICE,
            }

        info = self._device_info()
        info["via_device"] = ("AccountID", self._octopus_system.account_id)
        return info

    @property
    def icon(self):
        return "mdi:timelapse"

    async def async_will_remove_from_hass(self):
        self._timer()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._handle_coordinator_update()


class OctopusIntelligentChargingStartSensor(
    OctopusIntelligentPerDeviceEntityMixin, CoordinatorEntity, SensorEntity
):
    def __init__(
        self,
        hass,
        octopus_system,
        *,
        device_id: str | None = None,
    ) -> None:
        super().__init__(octopus_system)
        self._octopus_system = octopus_system
        self._device_id = device_id
        self._is_combined = device_id is None
        base_unique_id = "octopus_intelligent_charging_start"
        self._unique_id = (
            base_unique_id
            if self._is_combined
            else f"{base_unique_id}_{slugify(device_id)}"
        )
        self._timer = async_track_utc_time_change(
            hass, self.timer_update, minute=range(0, 60, 30), second=1
        )
        self._native_value = None
        self._set_native_value(log_on_error=False)

    def _set_native_value(self, log_on_error: bool = True):
        try:
            self._native_value = (
                self._octopus_system.current_intelligent_charge_start_utc(
                    device_id=self._device_id
                )
            )
            return True
        except Exception:  # pylint: disable=broad-except
            if log_on_error:
                _LOGGER.exception("Could not set native_value")
        return False

    @callback
    def _handle_coordinator_update(self) -> None:
        if self._set_native_value():
            self.async_write_ha_state()

    @callback
    async def timer_update(self, time):
        if self._set_native_value():
            self.async_write_ha_state()

    @property
    def name(self):
        return self._prefixed_name("Charging Start")

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def native_value(self):
        return self._native_value

    @property
    def device_class(self):
        return SensorDeviceClass.TIMESTAMP

    @property
    def device_info(self):
        if self._is_combined:
            return {
                "identifiers": {
                    ("AccountID", self._octopus_system.account_id),
                },
                "name": "Octopus Intelligent Tariff",
                "manufacturer": "Octopus",
                "entry_type": DeviceEntryType.SERVICE,
            }

        info = self._device_info()
        info["via_device"] = ("AccountID", self._octopus_system.account_id)
        return info

    @property
    def icon(self):
        return "mdi:clock-start"

    async def async_will_remove_from_hass(self):
        self._timer()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._handle_coordinator_update()


class OctopusIntelligentTargetReadyTimeSensor(
    OctopusIntelligentPerDeviceEntityMixin, CoordinatorEntity, SensorEntity
):
    def __init__(
        self,
        octopus_system,
        *,
        device_id: str | None = None,
    ) -> None:
        super().__init__(octopus_system)
        self._octopus_system = octopus_system
        self._device_id = device_id
        self._is_combined = device_id is None
        base_unique_id = "octopus_intelligent_target_ready_time"
        self._unique_id = (
            base_unique_id
            if self._is_combined
            else f"{base_unique_id}_{slugify(device_id)}"
        )
        self._native_value: str | None = None
        self._attributes: dict[str, Any] = {}
        self._set_native_value()

    def _set_native_value(self) -> None:
        summary = self._octopus_system.get_ready_time_summary(
            None if self._is_combined else self._device_id
        )
        self._native_value = normalize_time_string(summary.active_target_time)

        if self._is_combined:
            self._attributes = summary.as_combined_attributes()
            return

        device_entry = summary.first_target()
        if device_entry:
            self._attributes = device_entry.as_device_attributes(summary.mode)
        else:
            self._attributes = {"mode": summary.mode}

    @callback
    def _handle_coordinator_update(self) -> None:
        self._set_native_value()
        self.async_write_ha_state()

    @property
    def name(self):
        return self._prefixed_name("Target Ready Time")

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def native_value(self):
        return self._native_value

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def device_info(self):
        if self._is_combined:
            return {
                "identifiers": {
                    ("AccountID", self._octopus_system.account_id),
                },
                "name": "Octopus Intelligent Tariff",
                "manufacturer": "Octopus",
                "entry_type": DeviceEntryType.SERVICE,
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
        return "mdi:clock-check"


class OctopusIntelligentTargetSocSensor(
    OctopusIntelligentPerDeviceEntityMixin, CoordinatorEntity, SensorEntity
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
        base_unique_id = "octopus_intelligent_target_soc_state"
        self._unique_id = f"{base_unique_id}_{slugify(device_id)}"
        self._native_value: int | None = None
        self._attributes: dict[str, Any] = {}
        self._set_native_value()

    def _select_target_soc(self, summary_mode: str, entry: Any | None) -> int | None:
        if not entry:
            return None
        if summary_mode == "weekend":
            return entry.weekend_target_soc or entry.weekday_target_soc
        return entry.weekday_target_soc or entry.weekend_target_soc

    def _set_native_value(self) -> None:
        summary = self._octopus_system.get_ready_time_summary(self._device_id)
        device_entry = summary.first_target()
        self._native_value = self._select_target_soc(summary.mode, device_entry)
        if device_entry:
            self._attributes = device_entry.as_device_attributes(summary.mode)
        else:
            self._attributes = {"mode": summary.mode}

    @callback
    def _handle_coordinator_update(self) -> None:
        previous = self._native_value
        self._set_native_value()
        if self._native_value != previous:
            self.async_write_ha_state()

    @property
    def name(self):
        return f"{self._equipment_label()} Target State of Charge"

    @property
    def unique_id(self) -> str:
        return self._unique_id

    @property
    def native_value(self):
        return self._native_value

    @property
    def extra_state_attributes(self):
        return self._attributes

    @property
    def native_unit_of_measurement(self):
        return PERCENTAGE

    @property
    def device_info(self):
        return self._device_info()

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        return bool(self._equipment_state())

    @property
    def icon(self):
        return "mdi:battery-check-outline"

