from dataclasses import dataclass
from datetime import datetime, timezone

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
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.util import dt as dt_util
from .const import DOMAIN, OCTOPUS_SYSTEM
from .entity import OctopusIntelligentPerDeviceEntityMixin
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback, HomeAssistant
from homeassistant.util import slugify
import logging
_LOGGER = logging.getLogger(__name__)


SLOT_MODE_SMART_CHARGE = "smart_charge"
SLOT_MODE_OFFPEAK = "offpeak_window"


@dataclass(frozen=True)
class SlotDefinition:
    unique_id_source: str
    combined_name: str
    suffix: str
    store_attributes: bool
    look_ahead_mins: int


SMART_CHARGE_SLOT_DEFINITIONS: tuple[SlotDefinition, ...] = (
    SlotDefinition(
        unique_id_source="Octopus Intelligent Slot",
        combined_name="Smart-Charge Slot",
        suffix="Smart-Charge Slot",
        store_attributes=True,
        look_ahead_mins=0,
    ),
    SlotDefinition(
        unique_id_source="Octopus Intelligent Slot (next 1 hour)",
        combined_name="Smart-Charge Slot (next 1 hour)",
        suffix="Smart-Charge Slot (next 1 hour)",
        store_attributes=False,
        look_ahead_mins=60,
    ),
    SlotDefinition(
        unique_id_source="Octopus Intelligent Slot (next 2 hours)",
        combined_name="Smart-Charge Slot (next 2 hours)",
        suffix="Smart-Charge Slot (next 2 hours)",
        store_attributes=False,
        look_ahead_mins=120,
    ),
    SlotDefinition(
        unique_id_source="Octopus Intelligent Slot (next 3 hours)",
        combined_name="Smart-Charge Slot (next 3 hours)",
        suffix="Smart-Charge Slot (next 3 hours)",
        store_attributes=False,
        look_ahead_mins=180,
    ),
)


OFFPEAK_WINDOW_DEFINITIONS: tuple[SlotDefinition, ...] = (
    SlotDefinition(
        unique_id_source="Intelligent Offpeak Window",
        combined_name="Offpeak Window",
        suffix="Offpeak Window",
        store_attributes=False,
        look_ahead_mins=0,
    ),
    SlotDefinition(
        unique_id_source="Intelligent Offpeak Window (next 1 hour)",
        combined_name="Offpeak Window (next 1 hour)",
        suffix="Offpeak Window (next 1 hour)",
        store_attributes=False,
        look_ahead_mins=60,
    ),
    SlotDefinition(
        unique_id_source="Intelligent Offpeak Window (next 2 hours)",
        combined_name="Offpeak Window (next 2 hours)",
        suffix="Offpeak Window (next 2 hours)",
        store_attributes=False,
        look_ahead_mins=120,
    ),
    SlotDefinition(
        unique_id_source="Intelligent Offpeak Window (next 3 hours)",
        combined_name="Offpeak Window (next 3 hours)",
        suffix="Offpeak Window (next 3 hours)",
        store_attributes=False,
        look_ahead_mins=180,
    ),
)


def _is_slot_mode_active(
    octopus_system,
    slot_mode: str,
    device_id: str | None,
    minutes_offset: int,
):
    return octopus_system.is_slot_mode_active(
        slot_mode,
        device_id=device_id,
        minutes_offset=minutes_offset,
    )


def _parse_dispatch_datetime(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if not isinstance(value, str):
        return None

    cleaned = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(cleaned)
    except ValueError:
        cleaned = cleaned.replace("T", " ")
        try:
            parsed = datetime.fromisoformat(cleaned)
        except ValueError:
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _filter_future_dispatches(dispatches, *, now=None):
    if not dispatches:
        return []

    current = now or dt_util.utcnow()
    future: list[dict] = []
    for dispatch in dispatches:
        end_value = dispatch.get("endDtUtc") or dispatch.get("end")
        end_utc = _parse_dispatch_datetime(end_value)
        if end_utc and end_utc <= current:
            continue
        future.append(dispatch)
    return future


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    octopus_system = hass.data[DOMAIN][config_entry.entry_id][OCTOPUS_SYSTEM]
    device_ids = octopus_system.get_supported_device_ids()

    entities: list[BinarySensorEntity] = []

    def _add_slot_entities(
        definitions: tuple[SlotDefinition, ...],
        slot_mode: str,
        *,
        device_id: str | None = None,
    ) -> None:
        for definition in definitions:
            entities.append(
                OctopusIntelligentSlot(
                    hass,
                    octopus_system,
                    definition.unique_id_source,
                    definition.combined_name,
                    definition.suffix,
                    slot_mode,
                    definition.store_attributes if device_id is None else False,
                    definition.look_ahead_mins,
                    device_id=device_id,
                )
            )

    _add_slot_entities(SMART_CHARGE_SLOT_DEFINITIONS, SLOT_MODE_SMART_CHARGE)
    _add_slot_entities(OFFPEAK_WINDOW_DEFINITIONS, SLOT_MODE_OFFPEAK)

    entities.append(
        OctopusIntelligentPlannedDispatchSlot(
            hass,
            octopus_system,
            "Planned Dispatch Slot",
            "Planned Dispatch Slot",
            unique_id_source="Octopus Intelligent Planned Dispatch Slot",
        )
    )

    for device_id in device_ids:
        _add_slot_entities(SMART_CHARGE_SLOT_DEFINITIONS, SLOT_MODE_SMART_CHARGE, device_id=device_id)
        _add_slot_entities(OFFPEAK_WINDOW_DEFINITIONS, SLOT_MODE_OFFPEAK, device_id=device_id)

        entities.append(
            OctopusIntelligentPlannedDispatchSlot(
                hass,
                octopus_system,
                "Planned Dispatch Slot",
                "Planned Dispatch Slot",
                device_id=device_id,
                unique_id_source="Octopus Intelligent Planned Dispatch Slot",
            )
        )

    async_add_entities(entities, False)  # False: data was already fetched by __init__.py async_setup_entry()


class _OctopusBinaryEntityBase(OctopusIntelligentPerDeviceEntityMixin):
    def _account_device_info(self):
        return {
            "identifiers": {
                ("AccountID", self._octopus_system.account_id),
            },
            "name": "Intelligent Tariff",
            "manufacturer": "Octopus",
            "entry_type": DeviceEntryType.SERVICE,
        }

    def _slot_device_info(self):
        if self._is_combined:
            return self._account_device_info()
        info = self._device_info()
        info["via_device"] = ("AccountID", self._octopus_system.account_id)
        return info


class OctopusIntelligentSlot(
    _OctopusBinaryEntityBase, CoordinatorEntity, BinarySensorEntity
):
    def __init__(
        self,
        hass,
        octopus_system,
        unique_id_source: str,
        combined_name: str,
        name_suffix: str,
        slot_mode: str,
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
        slug_source = unique_id_source or combined_name
        self._combined_name = combined_name
        self._name_suffix = name_suffix
        self._unique_id = (
            slugify(slug_source)
            if self._is_combined
            else slugify(f"{slug_source}_{device_id}")
        )
        self._slot_mode = slot_mode
        self._store_attributes = store_attributes
        self._look_ahead_mins = look_ahead_mins
        self._attributes = {}
        self._is_on = self._is_slot_active()

        self._timer = async_track_utc_time_change(
            hass, self.timer_update, minute=range(0, 60, 30), second=1)

    def _is_slot_active(self):
        mins_looked = 0
        while mins_looked <= self._look_ahead_mins:
            if not self._is_active_at_offset(mins_looked):
                return False
            mins_looked += 30
        return True

    def _is_active_at_offset(self, minutes_offset: int) -> bool:
        return _is_slot_mode_active(
            self._octopus_system,
            self._slot_mode,
            self._device_id,
            minutes_offset,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._is_on = self._is_slot_active()
        if (self._store_attributes):
            if self._is_combined:
                self._attributes = self.coordinator.data
            else:
                self._attributes = self._octopus_system.get_device_state(self._device_id) or {}
        self.async_write_ha_state()

    @callback
    async def timer_update(self, time):
        """Refresh state when timer is fired."""
        self._is_on = self._is_slot_active()
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
        return self._slot_device_info()
    @property
    def icon(self):
        """Icon of the entity."""
        return "mdi:home-lightning-bolt-outline"

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._timer()


class OctopusIntelligentPlannedDispatchSlot(
    _OctopusBinaryEntityBase, CoordinatorEntity, BinarySensorEntity
):
    def __init__(
        self,
        hass,
        octopus_system,
        combined_name: str,
        name_suffix: str,
        *,
        device_id: str | None = None,
        unique_id_source: str | None = None,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(octopus_system)
        self._octopus_system = octopus_system
        self._device_id = device_id
        self._is_combined = device_id is None
        self._combined_name = combined_name
        self._name_suffix = name_suffix
        slug_source = unique_id_source or combined_name
        self._unique_id = (
            slugify(slug_source)
            if self._is_combined
            else slugify(f"{slug_source}_{device_id}")
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
            planned = data.get("plannedDispatches", [])
        else:
            device_state = self._octopus_system.get_device_state(self._device_id) or {}
            planned = device_state.get("plannedDispatches", [])
        return _filter_future_dispatches(planned)

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
        return self._slot_device_info()
    @property
    def icon(self):
        """Icon of the entity."""
        return "mdi:ev-station"

    async def async_will_remove_from_hass(self):
        """Unsubscribe when removed."""
        self._timer()
