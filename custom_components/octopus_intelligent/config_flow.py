"""Config flow for Octopus Intelligent integration."""
from collections import OrderedDict
import logging

from .graphql_client import OctopusEnergyGraphQLClient

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import (
    CONF_ID,
    CONF_API_KEY,
)
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
)

try:  # SelectSelectorOption is missing on older HA cores
    from homeassistant.helpers.selector import SelectSelectorOption  # type: ignore
    SELECTOR_OPTION_SUPPORTED = True
except ImportError:  # pragma: no cover - compatibility shim
    SelectSelectorOption = None  # type: ignore
    SELECTOR_OPTION_SUPPORTED = False

from .const import (
    DOMAIN,
    CONF_ACCOUNT_ID,
    CONF_OFFPEAK_START,
    CONF_OFFPEAK_START_DEFAULT,
    CONF_OFFPEAK_END,
    CONF_OFFPEAK_END_DEFAULT,
    CONF_PRIMARY_EQUIPMENT_ID,
    INTELLIGENT_24HR_TIMES
)
from .graphql_util import InvalidAuthError, validate_octopus_account
from .util import format_equipment_name, is_supported_equipment

_LOGGER = logging.getLogger(__name__)

class OctopusIntelligentConfigFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_PUSH

    async def _show_setup_form(self, errors=None):
        """Show the setup form to the user."""
        errors = errors or {}

        fields = OrderedDict()
        fields[vol.Required(CONF_API_KEY)] = str
        fields[vol.Required(CONF_ACCOUNT_ID)] = str
        fields[vol.Required(
                CONF_OFFPEAK_START,
                default=CONF_OFFPEAK_START_DEFAULT,
            )] = vol.In(INTELLIGENT_24HR_TIMES)
        fields[vol.Required(
                CONF_OFFPEAK_END,
                default=CONF_OFFPEAK_END_DEFAULT,
            )] = vol.In(INTELLIGENT_24HR_TIMES)
            

        return self.async_show_form(
            step_id="user", data_schema=vol.Schema(fields), errors=errors
        )

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return await self._show_setup_form()

        errors = {}
        try:
            await try_connection(user_input[CONF_API_KEY], user_input[CONF_ACCOUNT_ID])
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.error(ex)
            if isinstance(ex, InvalidAuthError):
                errors["base"] = "invalid_auth"
            else:
                errors["base"] = "unknown"
            return await self._show_setup_form(errors)

        unique_id = user_input[CONF_ACCOUNT_ID]

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title="",
            data={
                CONF_ID: unique_id,
                CONF_API_KEY: user_input[CONF_API_KEY],
                CONF_ACCOUNT_ID: user_input[CONF_ACCOUNT_ID],
                CONF_OFFPEAK_START: user_input[CONF_OFFPEAK_START],
                CONF_OFFPEAK_END: user_input[CONF_OFFPEAK_END],
            })

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return OctopusIntelligentOptionsFlowHandler(config_entry)


class OctopusIntelligentOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Octopus Intelligent integration."""

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}
        devices = None

        form_values = {
            CONF_API_KEY: self.config_entry.data.get(CONF_API_KEY, ""),
            CONF_ACCOUNT_ID: self.config_entry.data.get(CONF_ACCOUNT_ID, ""),
            CONF_OFFPEAK_START: self.config_entry.data.get(
                CONF_OFFPEAK_START, CONF_OFFPEAK_START_DEFAULT
            ),
            CONF_OFFPEAK_END: self.config_entry.data.get(
                CONF_OFFPEAK_END, CONF_OFFPEAK_END_DEFAULT
            ),
            CONF_PRIMARY_EQUIPMENT_ID: self.config_entry.options.get(
                CONF_PRIMARY_EQUIPMENT_ID, ""
            ),
        }

        if user_input is not None:
            form_values.update(user_input)

            try:
                client = await try_connection(
                    user_input[CONF_API_KEY], user_input[CONF_ACCOUNT_ID]
                )
                devices = await client.async_get_devices(user_input[CONF_ACCOUNT_ID])
            except InvalidAuthError as ex:
                _LOGGER.warning("Invalid Octopus credentials provided: %s", ex)
                errors["base"] = "invalid_auth"
            except Exception as ex:  # pylint: disable=broad-except
                _LOGGER.error("Unable to validate Octopus credentials: %s", ex)
                errors["base"] = "unknown"
            else:
                primary_value = user_input.get(CONF_PRIMARY_EQUIPMENT_ID, "") or ""
                valid_ids = {device.get("id") for device in devices or [] if device.get("id")}
                if primary_value and primary_value not in valid_ids:
                    errors[CONF_PRIMARY_EQUIPMENT_ID] = "device_not_found"

                if not errors:
                    new_data = {
                        CONF_ID: self.config_entry.data.get(CONF_ID),
                        CONF_API_KEY: user_input[CONF_API_KEY],
                        CONF_ACCOUNT_ID: user_input[CONF_ACCOUNT_ID],
                        CONF_OFFPEAK_START: user_input[CONF_OFFPEAK_START],
                        CONF_OFFPEAK_END: user_input[CONF_OFFPEAK_END],
                    }

                    new_options = dict(self.config_entry.options)
                    if primary_value:
                        new_options[CONF_PRIMARY_EQUIPMENT_ID] = primary_value
                    else:
                        new_options.pop(CONF_PRIMARY_EQUIPMENT_ID, None)

                    self.hass.config_entries.async_update_entry(
                        self.config_entry, data=new_data, options=new_options
                    )

                    return self.async_create_entry(title="", data={})

        device_selector_options = await self._async_build_device_selector_options(
            form_values[CONF_API_KEY],
            form_values[CONF_ACCOUNT_ID],
            preset_devices=devices,
            suppress_errors=user_input is None,
        )

        fields = OrderedDict()
        fields[vol.Required(CONF_API_KEY, default=form_values[CONF_API_KEY])] = str
        fields[vol.Required(CONF_ACCOUNT_ID, default=form_values[CONF_ACCOUNT_ID])] = str
        fields[vol.Required(
            CONF_OFFPEAK_START,
            default=form_values[CONF_OFFPEAK_START],
        )] = vol.In(INTELLIGENT_24HR_TIMES)
        fields[vol.Required(
            CONF_OFFPEAK_END,
            default=form_values[CONF_OFFPEAK_END],
        )] = vol.In(INTELLIGENT_24HR_TIMES)

        if device_selector_options:
            selector_field = self._build_device_selector_field(device_selector_options)
            fields[vol.Optional(
                CONF_PRIMARY_EQUIPMENT_ID,
                default=form_values.get(CONF_PRIMARY_EQUIPMENT_ID, ""),
            )] = selector_field

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(fields),
            errors=errors,
        )

    def _build_device_selector_field(self, options: list[dict[str, str]]):
        """Return a selector field or a simple fallback validator."""
        if SELECTOR_OPTION_SUPPORTED and SelectSelectorOption is not None:
            selector_options = [
                SelectSelectorOption(value=opt["value"], label=opt.get("label"))
                for opt in options
            ]
            return SelectSelector(
                SelectSelectorConfig(
                    options=selector_options,
                    mode="dropdown",
                )
            )

        allowed_values = [opt["value"] for opt in options]
        return vol.In(allowed_values)

    async def _async_build_device_selector_options(
        self,
        api_key: str,
        account_id: str,
        preset_devices=None,
        suppress_errors: bool = False,
    ) -> list[dict[str, str]]:
        if not api_key or not account_id:
            return []

        devices = preset_devices
        if devices is None:
            try:
                client = await try_connection(api_key, account_id)
                devices = await client.async_get_devices(account_id)
            except InvalidAuthError as ex:
                if suppress_errors:
                    _LOGGER.debug(
                        "Skipping device selector options because credentials are invalid: %s",
                        ex,
                    )
                    return []
                raise
            except Exception as ex:  # pylint: disable=broad-except
                if suppress_errors:
                    _LOGGER.debug(
                        "Failed to load Octopus Intelligent equipment list: %s",
                        ex,
                    )
                    return []
                raise

        options: list[dict[str, str]] = []
        for device in devices or []:
            device_id = device.get("id")
            if not device_id:
                continue
            if not is_supported_equipment(device):
                continue
            label = format_equipment_name(device, fallback="Unknown equipment")
            options.append({"value": device_id, "label": label})

        if not options:
            return []

        default_option = {
            "value": "",
            "label": "Auto (use first detected device)",
        }
        return [
            default_option,
            *sorted(options, key=lambda opt: (opt.get("label") or opt["value"])),
        ]


async def try_connection(api_key: str, account_id: str):
    """Try connecting to the Octopus API and validating the given account_id."""
    _LOGGER.debug("Trying to connect to Octopus during setup")
    client = OctopusEnergyGraphQLClient(api_key)
    await validate_octopus_account(client, account_id)
    _LOGGER.debug("Successfully connected to Octopus during setup")
    return client
