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
from .const import (
    DOMAIN,
    CONF_ACCOUNT_ID,
    CONF_OFFPEAK_START,
    CONF_OFFPEAK_START_DEFAULT,
    CONF_OFFPEAK_END,
    CONF_OFFPEAK_END_DEFAULT,
    CONF_POLL_INTERVAL,
    CONF_POLL_INTERVAL_DEFAULT,
    CONF_POLL_INTERVAL_MIN,
    INTELLIGENT_24HR_TIMES
)
from .graphql_util import InvalidAuthError, validate_octopus_account

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

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Store the config entry being edited."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        form_values = {
            CONF_API_KEY: self.config_entry.options.get(
                CONF_API_KEY,
                self.config_entry.data.get(CONF_API_KEY, ""),
            ) or "",
            CONF_ACCOUNT_ID: self.config_entry.options.get(
                CONF_ACCOUNT_ID,
                self.config_entry.data.get(CONF_ACCOUNT_ID, ""),
            ) or "",
            CONF_OFFPEAK_START: self.config_entry.options.get(
                CONF_OFFPEAK_START,
                self.config_entry.data.get(CONF_OFFPEAK_START, CONF_OFFPEAK_START_DEFAULT),
            ),
            CONF_OFFPEAK_END: self.config_entry.options.get(
                CONF_OFFPEAK_END,
                self.config_entry.data.get(CONF_OFFPEAK_END, CONF_OFFPEAK_END_DEFAULT),
            ),
            CONF_POLL_INTERVAL: self.config_entry.options.get(
                CONF_POLL_INTERVAL, CONF_POLL_INTERVAL_DEFAULT
            ),
        }
        existing_api_key = form_values[CONF_API_KEY]
        existing_account_id = form_values[CONF_ACCOUNT_ID]

        if user_input is not None:
            sanitized_input = dict(user_input)
            sanitized_input[CONF_API_KEY] = sanitized_input[CONF_API_KEY].strip()
            sanitized_input[CONF_ACCOUNT_ID] = sanitized_input[CONF_ACCOUNT_ID].strip()
            form_values.update(sanitized_input)

            credentials_changed = (
                sanitized_input[CONF_API_KEY] != existing_api_key
                or sanitized_input[CONF_ACCOUNT_ID] != existing_account_id
            )

            if credentials_changed:
                try:
                    await try_connection(
                        sanitized_input[CONF_API_KEY],
                        sanitized_input[CONF_ACCOUNT_ID],
                    )
                except InvalidAuthError:
                    errors["base"] = "invalid_auth"
                except Exception as ex:  # pylint: disable=broad-exception-caught
                    _LOGGER.error("Error validating Octopus credentials: %s", ex)
                    errors["base"] = "unknown"

            if not errors:
                new_options = dict(self.config_entry.options)
                new_options[CONF_API_KEY] = form_values[CONF_API_KEY]
                new_options[CONF_ACCOUNT_ID] = form_values[CONF_ACCOUNT_ID]
                new_options[CONF_OFFPEAK_START] = form_values[CONF_OFFPEAK_START]
                new_options[CONF_OFFPEAK_END] = form_values[CONF_OFFPEAK_END]
                new_options[CONF_POLL_INTERVAL] = form_values.get(
                    CONF_POLL_INTERVAL,
                    CONF_POLL_INTERVAL_DEFAULT,
                )

                return self.async_create_entry(title="", data=new_options)

        fields = OrderedDict()
        fields[vol.Required(
            CONF_API_KEY,
            default=form_values[CONF_API_KEY],
        )] = str
        fields[vol.Required(
            CONF_ACCOUNT_ID,
            default=form_values[CONF_ACCOUNT_ID],
        )] = str
        fields[vol.Required(
            CONF_OFFPEAK_START,
            default=form_values[CONF_OFFPEAK_START],
        )] = vol.In(INTELLIGENT_24HR_TIMES)
        fields[vol.Required(
            CONF_OFFPEAK_END,
            default=form_values[CONF_OFFPEAK_END],
        )] = vol.In(INTELLIGENT_24HR_TIMES)
        fields[vol.Required(
            CONF_POLL_INTERVAL,
            default=form_values[CONF_POLL_INTERVAL],
        )] = vol.All(
            vol.Coerce(int),
            vol.Range(min=CONF_POLL_INTERVAL_MIN, max=7200),
        )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(fields),
            errors=errors,
        )


async def try_connection(api_key: str, account_id: str):
    """Try connecting to the Octopus API and validating the given account_id."""
    _LOGGER.debug("Trying to connect to Octopus during setup")
    client = OctopusEnergyGraphQLClient(api_key)
    await validate_octopus_account(client, account_id)
    _LOGGER.debug("Successfully connected to Octopus during setup")
    return client
