"""Config flow for Wevolor Control for Levolor Motorized Blinds integration."""

from __future__ import annotations

import logging
from typing import Any

from pywevolor import Wevolor
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONFIG_HOST,
    CONFIG_CHANNEL_1,
    CONFIG_CHANNEL_2,
    CONFIG_CHANNEL_3,
    CONFIG_CHANNEL_4,
    CONFIG_CHANNEL_5,
    CONFIG_CHANNEL_6,
    CONFIG_NAME,
    CONFIG_TILT,
    DEFAULT_EXPERIMENTAL_POSITIONING,
    DOMAIN,
    OPTION_EXPERIMENTAL_POSITIONING,
    OPTION_FULL_TRAVEL_TIME_SECS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONFIG_HOST): str,
        vol.Required(CONFIG_CHANNEL_1, default=False): bool,
        vol.Required(CONFIG_CHANNEL_2, default=False): bool,
        vol.Required(CONFIG_CHANNEL_3, default=False): bool,
        vol.Required(CONFIG_CHANNEL_4, default=False): bool,
        vol.Required(CONFIG_CHANNEL_5, default=False): bool,
        vol.Required(CONFIG_CHANNEL_6, default=False): bool,
        vol.Required(CONFIG_TILT, default=False): bool,
        vol.Required(CONFIG_NAME): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""

    wevolor = Wevolor(data[CONFIG_HOST])
    status = await wevolor.get_status()

    if not status:
        raise CannotConnect

    return status


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore
    """Handle a config flow for Wevolor Control for Levolor Motorized Blinds."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> WevolorOptionsFlowHandler:
        """Return the options flow handler."""
        return WevolorOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception: %s", err)
            errors["base"] = "unknown"
        else:
            await self.async_set_unique_id(user_input[CONFIG_NAME])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=info["remote"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class WevolorOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for the Wevolor integration."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the integration options."""
        if user_input is not None:
            if (
                user_input.get(OPTION_EXPERIMENTAL_POSITIONING)
                and OPTION_FULL_TRAVEL_TIME_SECS not in user_input
            ):
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._build_options_schema(
                        experimental_positioning=True,
                    ),
                )
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self._build_options_schema(),
        )

    def _build_options_schema(
        self,
        experimental_positioning: bool | None = None,
    ) -> vol.Schema:
        """Build the options schema."""
        if experimental_positioning is None:
            experimental_positioning = self._config_entry.options.get(
                OPTION_EXPERIMENTAL_POSITIONING,
                DEFAULT_EXPERIMENTAL_POSITIONING,
            )

        schema: dict[vol.Marker, object] = {
            vol.Required(
                OPTION_EXPERIMENTAL_POSITIONING,
                default=experimental_positioning,
            ): bool,
        }

        if experimental_positioning:
            schema[
                vol.Required(
                    OPTION_FULL_TRAVEL_TIME_SECS,
                    default=self._config_entry.options.get(
                        OPTION_FULL_TRAVEL_TIME_SECS,
                    ),
                )
            ] = vol.All(vol.Coerce(float), vol.Range(min=0.1))

        return self.add_suggested_values_to_schema(
            vol.Schema(schema),
            self._config_entry.options,
        )
