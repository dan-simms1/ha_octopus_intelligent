"""Support for Octopus Intelligent Tariff in the UK."""
import logging
from .octopus_intelligent_system import OctopusIntelligentSystem


import homeassistant.util.dt as dt_util

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, device_registry as dr

from .const import(
    DOMAIN,
    OCTOPUS_SYSTEM,

    CONF_ACCOUNT_ID,
    CONF_OFFPEAK_START,
    CONF_OFFPEAK_END,
    CONF_OFFPEAK_START_DEFAULT,
    CONF_OFFPEAK_END_DEFAULT,
    CONF_PRIMARY_EQUIPMENT_ID,
    CONF_POLL_INTERVAL,
    CONF_POLL_INTERVAL_DEFAULT,
    UNSUPPORTED_DEVICE_PROVIDERS,
)
from .util import to_timedelta, format_equipment_name

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "binary_sensor", "select", "sensor"]

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Octopus Intelligent System integration."""

    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    _LOGGER.debug("Setting up Octopus Intelligent System component")

    poll_interval = entry.options.get(CONF_POLL_INTERVAL, CONF_POLL_INTERVAL_DEFAULT)
    try:
        poll_interval = int(poll_interval)
    except (TypeError, ValueError):
        poll_interval = CONF_POLL_INTERVAL_DEFAULT
    if poll_interval < 1:
        poll_interval = CONF_POLL_INTERVAL_DEFAULT

    off_peak_start_str = entry.options.get(
        CONF_OFFPEAK_START,
        entry.data.get(CONF_OFFPEAK_START),
    ) or CONF_OFFPEAK_START_DEFAULT
    off_peak_end_str = entry.options.get(
        CONF_OFFPEAK_END,
        entry.data.get(CONF_OFFPEAK_END),
    ) or CONF_OFFPEAK_END_DEFAULT

    api_key = entry.options.get(CONF_API_KEY) or entry.data.get(CONF_API_KEY)
    account_id = entry.options.get(CONF_ACCOUNT_ID) or entry.data.get(CONF_ACCOUNT_ID)

    if not api_key or not account_id:
        _LOGGER.error("Missing Octopus Intelligent credentials; aborting setup")
        return False

    octopus_system = OctopusIntelligentSystem(
        hass,
        api_key=api_key,
        account_id=account_id,
        off_peak_start=to_timedelta(off_peak_start_str),
        off_peak_end=to_timedelta(off_peak_end_str),
        primary_equipment_id=entry.options.get(CONF_PRIMARY_EQUIPMENT_ID),
        update_interval_seconds=poll_interval,
    )

    try:
        await octopus_system.start()
    except Exception as ex:
        _LOGGER.error("Got error when setting up Octopus Intelligent Integration: %s", ex)
        return False

    if entry.entry_id not in hass.data[DOMAIN]:
        hass.data[DOMAIN][entry.entry_id] = {}

    hass.data[DOMAIN][entry.entry_id][OCTOPUS_SYSTEM] = octopus_system

    await octopus_system.async_config_entry_first_refresh()

    await _async_cleanup_legacy_controls(hass)
    await _async_remove_unsupported_devices(hass)
    await _async_update_vehicle_device_icons(hass, entry, octopus_system)

    #hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, lambda event: octopus_system.stop())

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.debug("Octopus Intelligent System component setup finished")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Octopus Intelligent config entry."""
    _LOGGER.debug("Unloading Octopus Intelligent System component")
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Clean up the system instance
        if entry.entry_id in hass.data[DOMAIN]:
            octopus_system: OctopusIntelligentSystem = (
                hass.data[DOMAIN][entry.entry_id].get(OCTOPUS_SYSTEM)
            )
            if octopus_system:
                try:
                    await octopus_system.async_remove_entry()
                except Exception as ex:  # pylint: disable=broad-exception-caught
                    _LOGGER.error("Error during unload: %s", ex)
            
            # Remove the entry data
            hass.data[DOMAIN].pop(entry.entry_id)
    
    _LOGGER.debug("Octopus Intelligent System component unload finished")
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Called when the config entry is removed (the integration is deleted)."""
    octopus_system: OctopusIntelligentSystem = (
        hass.data[DOMAIN][entry.entry_id][OCTOPUS_SYSTEM]
    )
    try:
        await octopus_system.async_remove_entry()
    except Exception as ex:  # pylint: disable=broad-exception-caught
        _LOGGER.error(ex)


async def _async_cleanup_legacy_controls(hass: HomeAssistant) -> None:
    """Remove legacy account-level control entities if they still exist."""
    registry = er.async_get(hass)
    legacy_unique_ids = {
        "octopus_intelligent_bump_charge",
        "octopus_intelligent_smart_charging",
        "octopus_intelligent_target_soc",
        "octopus_intelligent_target_time",
    }

    to_remove: list[str] = []
    for entity_id, entry in registry.entities.items():
        if entry.platform != DOMAIN:
            continue
        if entry.unique_id in legacy_unique_ids:
            to_remove.append(entity_id)

    for entity_id in to_remove:
        _LOGGER.debug("Removing legacy Octopus control entity %s", entity_id)
        registry.async_remove(entity_id)


def _normalize_identifier(value: str | None) -> str:
    if not isinstance(value, str):
        return ""
    uppercase = value.upper()
    normalized = [
        ch
        for ch in uppercase
        if ch.isalnum()
    ]
    return "".join(normalized)


async def _async_remove_unsupported_devices(hass: HomeAssistant) -> None:
    """Remove old device entries such as OCTOPUS_ENERGY meters."""
    registry = dr.async_get(hass)
    provider_tokens = {
        _normalize_identifier(provider)
        for provider in UNSUPPORTED_DEVICE_PROVIDERS
    }

    to_remove: list[str] = []
    for device in list(registry.devices.values()):
        identifiers = device.identifiers or set()
        if not any(domain == DOMAIN for domain, _ in identifiers):
            continue

        candidates = {
            _normalize_identifier(device.name),
            _normalize_identifier(device.manufacturer),
            _normalize_identifier(device.model),
        }
        for _, identifier in identifiers:
            candidates.add(_normalize_identifier(identifier))

        if any(token and token in provider_tokens for token in candidates):
            to_remove.append(device.id)

    for device_id in to_remove:
        _LOGGER.debug(
            "Removing unsupported Octopus device entry %s from device registry",
            device_id,
        )
        registry.async_remove_device(device_id)


async def _async_update_vehicle_device_icons(
    hass: HomeAssistant,
    entry: ConfigEntry,
    octopus_system: OctopusIntelligentSystem,
) -> None:
    """Ensure EV devices show a car icon in the Integrations view."""
    registry = dr.async_get(hass)
    account_identifier = ("AccountID", octopus_system.account_id)

    for device_id in octopus_system.get_supported_device_ids():
        identifier = (DOMAIN, f"{octopus_system.account_id}_{device_id}")
        identifiers = {identifier}

        device_state = octopus_system.get_device_state(device_id) or {}
        device = device_state.get("device") or {}
        manufacturer = device.get("provider") or "Octopus"
        model = (
            device.get("model")
            or device.get("vehicleModel")
            or device.get("chargePointModel")
        )
        name = format_equipment_name(device, fallback=f"Equipment {device_id}")

        device_entry = registry.async_get_device(identifiers)
        if not device_entry:
            device_entry = registry.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers=identifiers,
                manufacturer=manufacturer,
                model=model,
                name=name,
                via_device=account_identifier,
            )

        current_icon = getattr(device_entry, "icon", None)
        if not device_entry or current_icon == "mdi:car-electric":
            continue

        update_fn = getattr(registry, "async_update_device", None)
        if not update_fn:
            continue

        accepts_icon = False
        code_obj = getattr(update_fn, "__code__", None)
        if code_obj:
            varnames = code_obj.co_varnames[: code_obj.co_argcount]
            accepts_icon = "icon" in varnames

        if accepts_icon:
            registry.async_update_device(device_entry.id, icon="mdi:car-electric")
