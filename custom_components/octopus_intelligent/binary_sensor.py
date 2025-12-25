from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)
from homeassistant.helpers.event import (
    async_track_utc_time_change
)
from .const import DOMAIN, OCTOPUS_SYSTEM
from .entity import OctopusIntelligentPerDeviceEntityMixin
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.util import slugify
import logging
_LOGGER = logging.getLogger(__name__)


SLOT_DEFINITIONS: tuple[tuple[str, str, bool, int], ...] = (
    ("Octopus Intelligent Slot", "Slot", True, 0),
    ("Octopus Intelligent Slot (next 1 hour)", "Slot (next 1 hour)", False, 60),
    ("Octopus Intelligent Slot (next 2 hours)", "Slot (next 2 hours)", False, 120),
    ("Octopus Intelligent Slot (next 3 hours)", "Slot (next 3 hours)", False, 180),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    octopus_system = hass.data[DOMAIN][config_entry.entry_id][OCTOPUS_SYSTEM]
    device_ids = octopus_system.get_supported_device_ids()

    entities: list[BinarySensorEntity] = []

    for combined_name, suffix, store_attrs, look_ahead in SLOT_DEFINITIONS:
        entities.append(
            OctopusIntelligentSlot(
                hass,
                octopus_system,
                combined_name,
                suffix,
                store_attrs,
                look_ahead,
            )
        )

    entities.append(
        OctopusIntelligentPlannedDispatchSlot(
            hass,
            octopus_system,
            "Octopus Intelligent Planned Dispatch Slot",
            "Planned Dispatch Slot",
        )
    )

    for device_id in device_ids:
        for combined_name, suffix, _store_attrs, look_ahead in SLOT_DEFINITIONS:
            entities.append(
                OctopusIntelligentSlot(
                    hass,
                    octopus_system,
                    combined_name,
                    suffix,
                    False,
                    look_ahead,
                    device_id=device_id,
                )
            )

        entities.append(
            OctopusIntelligentPlannedDispatchSlot(
                hass,
                octopus_system,
                "Octopus Intelligent Planned Dispatch Slot",
                "Planned Dispatch Slot",
                device_id=device_id,
            )
        )

    async_add_entities(entities, False)  # False: data was already fetched by __init__.py async_setup_entry()


class OctopusIntelligentSlot(
    OctopusIntelligentPerDeviceEntityMixin, CoordinatorEntity, BinarySensorEntity
):
    def __init__(
        self,
        hass,
        octopus_system,
        combined_name: str,
        name_suffix: str,
        store_attributes: bool = False,
        look_ahead_mins: int = 0,
        *,
        device_id: str | None = None,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(octopus_system)
        self._octopus_system = octopus_system
        self._device_id = device_id
        self._is_combined = device_id is None
        self._combined_name = combined_name
        self._name_suffix = name_suffix
        self._unique_id = (
            slugify(combined_name)
            if self._is_combined
            else slugify(f"{combined_name}_{device_id}")
        )
        self._store_attributes = store_attributes
        self._look_ahead_mins = look_ahead_mins
        self._attributes = {}
        self._is_on = self._is_off_peak()

        self._timer = async_track_utc_time_change(
            hass, self.timer_update, minute=range(0, 60, 30), second=1)

    def _is_off_peak(self):
        mins_looked = 0
        while (mins_looked <= self._look_ahead_mins):
            if self._device_id:
                if not self._octopus_system.is_device_off_peak_now(self._device_id, mins_looked):
                    return False
            else:
                if not self._octopus_system.is_off_peak_now(mins_looked):
                    return False
            mins_looked += 30
        return True

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._is_on = self._is_off_peak()
        if (self._store_attributes):
            if self._is_combined:
                self._attributes = self.coordinator.data
            else:
                self._attributes = self._octopus_system.get_device_state(self._device_id) or {}
        self.async_write_ha_state()

    @callback
    async def timer_update(self, time):
        """Refresh state when timer is fired."""
        self._is_on = self._is_off_peak()
        self.async_write_ha_state()

    @property
    def name(self):
        """Return the name of the device."""
        if self._is_combined:
            return self._combined_name
        return self._prefixed_name(self._name_suffix)

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def is_on(self) -> bool:
        """Return the status of the binary sensor."""
        return self._is_on

    @property
    def extra_state_attributes(self):
        """Attributes of the sensor."""
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
            }
        info = self._device_info()
        info["via_device"] = ("AccountID", self._octopus_system.account_id)
        return info
    @property
    def icon(self):
        """Icon of the entity."""
        return "mdi:home-lightning-bolt-outline"

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._timer()


class OctopusIntelligentPlannedDispatchSlot(
    OctopusIntelligentPerDeviceEntityMixin, CoordinatorEntity, BinarySensorEntity
):
    def __init__(
        self,
        hass,
        octopus_system,
        combined_name: str,
        name_suffix: str,
        *,
        device_id: str | None = None,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(octopus_system)
        self._octopus_system = octopus_system
        self._device_id = device_id
        self._is_combined = device_id is None
        self._combined_name = combined_name
        self._name_suffix = name_suffix
        self._unique_id = (
            slugify(combined_name)
            if self._is_combined
            else slugify(f"{combined_name}_{device_id}")
        )
        self._attributes = {}
        self._is_on = False
        self._update_state()

        self._timer = async_track_utc_time_change(
            hass, self.timer_update, minute=range(0, 60, 30), second=1)
        
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_state()
        self.async_write_ha_state()

    @callback
    async def timer_update(self, time):
        """Refresh state when timer is fired."""
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self):
        planned = self._get_planned_dispatches()
        self._is_on = bool(planned)
        self._attributes = self._build_attributes(planned)

    def _get_planned_dispatches(self):
        if self._is_combined:
            data = self.coordinator.data or {}
            return data.get("plannedDispatches", [])
        device_state = self._octopus_system.get_device_state(self._device_id) or {}
        return device_state.get("plannedDispatches", [])

    def _build_attributes(self, planned_dispatches):
        if self._is_combined:
            data = self.coordinator.data or {}
            return {
                "planned_dispatches": planned_dispatches,
                "completed_dispatches": data.get("completedDispatches", []),
            }
        device_state = self._octopus_system.get_device_state(self._device_id) or {}
        return {
            "planned_dispatches": planned_dispatches,
            "completed_dispatches": device_state.get("completedDispatches", []),
            "status": device_state.get("status", {}),
        }

    @property
    def name(self):
        """Return the name of the device."""
        if self._is_combined:
            return self._combined_name
        return self._prefixed_name(self._name_suffix)

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return self._unique_id

    @property
    def is_on(self) -> bool:
        """Return the status of the binary sensor."""
        return self._is_on

    @property
    def extra_state_attributes(self):
        """Expose planned/completed dispatch details for dashboards/automations."""
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
            }
        info = self._device_info()
        info["via_device"] = ("AccountID", self._octopus_system.account_id)
        return info
    @property
    def icon(self):
        """Icon of the entity."""
        return "mdi:ev-station"

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._timer()

