"""Support for Octopus Intelligent Tariff in the UK."""
from datetime import timedelta, datetime, timezone
from typing import Any
import asyncio
import logging

import homeassistant.util.dt as dt_util

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .graphql_client import OctopusEnergyGraphQLClient
from .graphql_util import validate_octopus_account
from .persistent_data import PersistentData, PersistentDataStore
from .util import *

_LOGGER = logging.getLogger(__name__)

class OctopusIntelligentSystem(DataUpdateCoordinator):
    def __init__(
        self,
        hass,
        *,
        api_key,
        account_id,
        off_peak_start,
        off_peak_end,
        primary_equipment_id=None,
    ):
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Octopus Intelligent",
            # Polling interval. Will only be polled if there are subscribers.
            update_interval=timedelta(seconds=300),
        )
        self._hass = hass
        self._api_key = api_key
        self._account_id = account_id

        self._off_peak_start = off_peak_start
        self._off_peak_end = off_peak_end
        self._primary_equipment_id = primary_equipment_id
        
        self.client = OctopusEnergyGraphQLClient(self._api_key)
        self._persistent_data = PersistentData()
        self._store = PersistentDataStore(self._persistent_data, hass, account_id)

    @property
    def account_id(self):
        return self._account_id

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.

        Returns:
            dict: The data received from the Octopus API, for example:
            {
                'completedDispatches': [{
                    'chargeKwh': '-0.58',
                    'startDtUtc': '2024-02-25 02:00:00+00:00',
                    'endDtUtc': '2024-02-25 02:30:00+00:00',
                    'meta': {'location': 'AT_HOME', 'source': None},
                }, {
                    'chargeKwh': '-0.58',
                    'startDtUtc': '2024-02-25 03:30:00+00:00',
                    'endDtUtc': '2024-02-25 04:00:00+00:00',
                    'meta': {'location': 'AT_HOME', 'source': None},
                }],
                'plannedDispatches': [{
                    'chargeKwh': '-0.67',
                    'startDtUtc': '2024-02-25 23:30:00+00:00',
                    'endDtUtc': '2024-02-26 00:00:00+00:00',
                    'meta': {'location': None, 'source': 'smart-charge'},
                }, {
                    'chargeKwh': '-1.12',
                    'startDtUtc': '2024-02-26 03:00:00+00:00',
                    'endDtUtc': '2024-02-26 04:00:00+00:00',
                    'meta': {'location': None, 'source': 'smart-charge'},
                }],
                'vehicleChargingPreferences': {
                    'weekdayTargetSoc': 80,
                    'weekdayTargetTime': '08:00',
                    'weekendTargetSoc': 80,
                    'weekendTargetTime': '08:00',
                },
                'registeredKrakenflexDevice': { ... },
            }
        """
        try:
            async with asyncio.timeout(90):
                devices = await self.client.async_get_devices(self._account_id)
                if not devices:
                    raise UpdateFailed("No intelligent equipment found for account")

                device_states: dict[str, Any] = {}
                union_planned: list[dict[str, Any]] = []
                union_completed: list[dict[str, Any]] = []

                for device in devices:
                    device_id = device.get("id")
                    if not device_id:
                        continue

                    preferences = await self.client.async_get_device_preferences(
                        self._account_id, device_id
                    )
                    dispatches = await self.client.async_get_device_dispatches(
                        self._account_id, device_id
                    )
                    preferences = preferences or {}
                    dispatches = dispatches or {}

                    planned = self._normalise_planned_dispatches(
                        device_id, dispatches.get("flexPlannedDispatches", [])
                    )
                    completed = self._normalise_completed_dispatches(
                        device_id, dispatches.get("completedDispatches", [])
                    )

                    union_planned.extend(planned)
                    union_completed.extend(completed)

                    device_states[device_id] = {
                        "device": device,
                        "preferences": (preferences or {}).get(
                            "chargingPreferences", {}
                        ),
                        "plannedDispatches": planned,
                        "completedDispatches": completed,
                        "status": self._build_device_status(
                            device, preferences, dispatches
                        ),
                    }

                union_planned.sort(key=lambda item: item.get("startDtUtc", ""))
                union_completed.sort(key=lambda item: item.get("startDtUtc", ""))

                primary_equipment_id = self._resolve_primary_equipment(device_states)
                vehicle_preferences = (
                    device_states.get(primary_equipment_id, {}).get("preferences", {})
                    if primary_equipment_id
                    else {}
                )

                return {
                    "devices": device_states,
                    "plannedDispatches": union_planned,
                    "completedDispatches": union_completed,
                    "primary_equipment_id": primary_equipment_id,
                    "vehicleChargingPreferences": vehicle_preferences,
                }
        except Exception as err:
            raise UpdateFailed(f"Error communicating with Octopus GraphQL API: {err}") from err

    def _update_planned_dispatch_sources(
        self, device_id: str, dispatches: list[dict[str, Any]]
    ) -> None:
        """Workaround for issue #35: missing dispatch sources in Octopus API response."""
        if not dispatches:
            return

        all_sources = [disp.get("meta", {}).get("source", "") for disp in dispatches]
        good_sources: set[str] = {src for src in all_sources if src}
        selected_source = ""

        if good_sources:
            if len(good_sources) > 1:
                _LOGGER.warning(
                    "Unexpected mix of planned dispatch sources for %s: %s",
                    device_id,
                    good_sources,
                )
            else:
                selected_source = next(iter(good_sources))

        if selected_source:
            self._persistent_data.last_seen_planned_dispatch_sources[device_id] = (
                selected_source
            )
            self._persistent_data.last_seen_planned_dispatch_source = selected_source

        fallback_source = self._persistent_data.last_seen_planned_dispatch_sources.get(
            device_id,
            self._persistent_data.last_seen_planned_dispatch_source,
        )

        if fallback_source and any(not src for src in all_sources):
            _LOGGER.debug(
                "Missing planned dispatch source in Octopus API response for %s, assuming '%s'",
                device_id,
                fallback_source,
            )
            for dispatch in dispatches:
                meta = dispatch.setdefault("meta", {})
                meta.setdefault("source", fallback_source)

    def _normalise_planned_dispatches(
        self, device_id: str, dispatches: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        normalised: list[dict[str, Any]] = []
        for dispatch in dispatches or []:
            entry = {
                "chargeKwh": self._format_energy(dispatch.get("energyAddedKwh")),
                "startDtUtc": self._format_dispatch_time(dispatch.get("start")),
                "endDtUtc": self._format_dispatch_time(dispatch.get("end")),
                "meta": {
                    "source": dispatch.get("type") or dispatch.get("meta", {}).get("source"),
                    "location": dispatch.get("meta", {}).get("location"),
                    "deviceId": device_id,
                },
            }
            normalised.append(entry)

        self._update_planned_dispatch_sources(device_id, normalised)
        return normalised

    def _normalise_completed_dispatches(
        self, device_id: str, dispatches: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        normalised: list[dict[str, Any]] = []
        for dispatch in dispatches or []:
            entry = {
                "chargeKwh": self._format_energy(dispatch.get("delta")),
                "startDtUtc": self._format_dispatch_time(dispatch.get("start")),
                "endDtUtc": self._format_dispatch_time(dispatch.get("end")),
                "meta": {
                    **(dispatch.get("meta") or {}),
                    "deviceId": device_id,
                },
            }
            normalised.append(entry)

        return normalised

    def _build_device_status(self, device, preferences, dispatches):
        status = dict((device or {}).get("status") or {})
        pref_status = (preferences or {}).get("status") or {}
        dispatch_devices = (dispatches or {}).get("devices") or []
        dispatch_status = (dispatch_devices[0] or {}).get("status") if dispatch_devices else {}

        if isinstance(pref_status, dict) and "isSuspended" in pref_status:
            status["isSuspended"] = pref_status["isSuspended"]
        if isinstance(dispatch_status, dict) and dispatch_status.get("currentState"):
            status["currentState"] = dispatch_status["currentState"]

        return status

    def _resolve_primary_equipment(self, devices: dict[str, Any]) -> str | None:
        if self._primary_equipment_id and self._primary_equipment_id in devices:
            return self._primary_equipment_id

        first_device_id = next(iter(devices), None)
        self._primary_equipment_id = first_device_id
        return self._primary_equipment_id

    def _get_device_state(self, device_id: str | None = None):
        devices = (self.data or {}).get("devices", {})
        lookup_id = device_id or self.get_primary_equipment_id()
        if lookup_id and lookup_id in devices:
            return devices[lookup_id]
        return None

    def get_primary_equipment_id(self) -> str | None:
        data_primary = (self.data or {}).get("primary_equipment_id") if self.data else None
        return data_primary or self._primary_equipment_id

    def set_primary_equipment_id(self, equipment_id: str | None):
        self._primary_equipment_id = equipment_id

    @staticmethod
    def _format_dispatch_time(value: Any) -> str | None:
        if not value:
            return None
        if isinstance(value, str):
            try:
                cleaned = value.replace("Z", "+00:00")
                dt_value = datetime.fromisoformat(cleaned)
                return dt_value.strftime("%Y-%m-%d %H:%M:%S%z")
            except ValueError:
                return value.replace("T", " ")
        return None

    @staticmethod
    def _format_energy(value: Any) -> Any:
        if value is None:
            return None
        return f"{value}"

    def is_smart_charging_enabled(self, device_id: str | None = None):
        device_state = self._get_device_state(device_id)
        if not device_state:
            return False
        return not device_state.get("status", {}).get("isSuspended", False)

    async def async_suspend_smart_charging(self, device_id: str | None = None):
        target_device = device_id or self.get_primary_equipment_id()
        await self.client.async_suspend_smart_charging(self._account_id, target_device)

    async def async_resume_smart_charging(self, device_id: str | None = None):
        target_device = device_id or self.get_primary_equipment_id()
        await self.client.async_resume_smart_charging(self._account_id, target_device)

    def is_boost_charging_now(self):
        return self.is_charging_now('bump-charge')

    def is_off_peak_charging_now(self, minutes_offset: int = 0):
        return self.is_charging_now('smart-charge', minutes_offset=minutes_offset)

    def next_offpeak_start_utc(self, minutes_offset: int = 0):
        offpeak_range = self.next_offpeak_range_utc(minutes_offset=minutes_offset)
        return offpeak_range["start"] if offpeak_range is not None else None

    def next_offpeak_end_utc(self, minutes_offset: int = 0):
        offpeak_range = self.next_offpeak_range_utc(minutes_offset=minutes_offset)
        return offpeak_range["end"] if offpeak_range is not None else None

    def next_offpeak_range_utc(self, minutes_offset: int = 0):
        utcnow = dt_util.utcnow() + timedelta(minutes=minutes_offset)
        localdate = dt_util.start_of_local_day(dt_util.as_local(utcnow))
        fixed_start_b1 = dt_util.as_utc(localdate - timedelta(days=1) + self._off_peak_start)
        fixed_end_b1 = dt_util.as_utc(localdate - timedelta(days=1) + self._off_peak_end)
        fixed_start_0 = dt_util.as_utc(localdate + self._off_peak_start)
        fixed_end_0 = dt_util.as_utc(localdate + self._off_peak_end)
        fixed_start_a1 = dt_util.as_utc(localdate + timedelta(days=1) + self._off_peak_start)
        fixed_end_a1 = dt_util.as_utc(localdate + timedelta(days=1) + self._off_peak_end)
        #fixed_start_a2 = dt_util.as_utc(localdate + timedelta(days=2) + self._off_peak_start)
        fixed_end_a2 = dt_util.as_utc(localdate + timedelta(days=2) + self._off_peak_end)

        if fixed_start_b1 > fixed_end_b1:
            all_offpeak_ranges = [
                {"start": fixed_start_b1, "end": fixed_end_0},
                {"start": fixed_start_0, "end": fixed_end_a1},
                {"start": fixed_start_a1, "end": fixed_end_a2}
            ]
        else:
            all_offpeak_ranges = [
                {"start": fixed_start_b1, "end": fixed_end_b1},
                {"start": fixed_start_0, "end": fixed_end_0},
                {"start": fixed_start_a1, "end": fixed_end_a1},
            ]

        for state in (self.data or {}).get('plannedDispatches', []):
            if state.get('meta', {}).get('source', '') == 'smart-charge':
                startUtc = datetime.strptime(state.get('startDtUtc'), '%Y-%m-%d %H:%M:%S%z').astimezone(timezone.utc)
                endUtc = datetime.strptime(state.get('endDtUtc'), '%Y-%m-%d %H:%M:%S%z').astimezone(timezone.utc)
                all_offpeak_ranges.append({"start": startUtc, "end": endUtc})

        # merge overlapping ones:
        offpeak_ranges = merge_and_sort_time_ranges(all_offpeak_ranges)

        for offpeak_range in offpeak_ranges:
            startUtc = offpeak_range["start"]
            endUtc = offpeak_range["end"]
            if startUtc <= utcnow <= endUtc or utcnow <= startUtc:
                return offpeak_range
        return None


    def is_charging_now(
        self,
        source=None,
        minutes_offset: int = 0,
        device_id: str | None = None,
    ):
        utcnow = dt_util.utcnow() + timedelta(minutes=minutes_offset)
        dispatches = (self.data or {}).get('plannedDispatches', [])
        if device_id:
            dispatches = [
                state
                for state in dispatches
                if state.get('meta', {}).get('deviceId') == device_id
            ]

        for state in dispatches:
            if source is None or state.get('meta', {}).get('source', '') == source:
                startUtc = datetime.strptime(state.get('startDtUtc'), '%Y-%m-%d %H:%M:%S%z').astimezone(timezone.utc)
                endUtc = datetime.strptime(state.get('endDtUtc'), '%Y-%m-%d %H:%M:%S%z').astimezone(timezone.utc)
                if startUtc <= utcnow <= endUtc:
                    return True
        return False

    def is_off_peak_time_now(self, minutes_offset: int = 0):
        now = dt_util.now() + timedelta(minutes=minutes_offset)
        offpeak_start_mins = self._off_peak_start.seconds // 60
        offpeak_end_mins = self._off_peak_end.seconds // 60
        now_mins = now.hour * 60 + now.minute
        if (offpeak_end_mins < offpeak_start_mins):
            return now_mins >= offpeak_start_mins or now_mins <= offpeak_end_mins
        else:
            return offpeak_start_mins <= now_mins <= offpeak_end_mins

    def is_off_peak_now(self, minutes_offset: int = 0):
        return self.is_off_peak_time_now(minutes_offset) or self.is_charging_now('smart-charge', minutes_offset)

    def get_target_soc(self, device_id: str | None = None):
        device_state = self._get_device_state(device_id)
        if not device_state:
            return None
        return device_state.get('preferences', {}).get('weekdayTargetSoc')

    def get_target_time(self, device_id: str | None = None):
        device_state = self._get_device_state(device_id)
        if not device_state:
            return None
        return device_state.get('preferences', {}).get('weekdayTargetTime')

    async def async_set_target_soc(self, target_soc: int, device_id: str | None = None):
        target_time_str = self.get_target_time(device_id)
        if target_time_str is None:
            _LOGGER.warn("Octopus Intelligent System could not set target SOC because data is not available yet")
            return
        target_time = to_hours_after_midnight(target_time_str)
        await self.client.async_set_charge_preferences(
            self._account_id,
            target_time,
            target_soc,
            device_id=device_id or self.get_primary_equipment_id(),
        )
        await self.async_refresh()

    async def async_set_target_time(self, target_time: str, device_id: str | None = None):
        target_soc = self.get_target_soc(device_id)
        if (target_soc is None):
            _LOGGER.warn("Octopus Intelligent System could not set target time because data is not available yet")
            return
        target_time = to_hours_after_midnight(target_time)
        await self.client.async_set_charge_preferences(
            self._account_id,
            target_time,
            target_soc,
            device_id=device_id or self.get_primary_equipment_id(),
        )
        await self.async_refresh()

    async def async_start_boost_charge(self):
        await self.client.async_trigger_boost_charge(self._account_id)
    async def async_cancel_boost_charge(self):
        await self.client.async_cancel_boost_charge(self._account_id)

    async def async_remove_entry(self):
        """Called when the integration (config entry) is removed from Home Assistant."""
        await self._store.remove()

    async def start(self):
        _LOGGER.debug("Starting OctopusIntelligentSystem")
        await validate_octopus_account(self.client, self._account_id)

        await self._store.load()

    async def stop(self):
        _LOGGER.debug("Stopping OctopusIntelligentSystem")
