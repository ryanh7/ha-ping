from __future__ import annotations
import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_NAME,
    CONF_HOST,
    CONF_SCAN_INTERVAL,
    CONF_PLATFORM
)
from .const import (
    DOMAIN,
    BINARY_SENSOR,
    DEVICE_TRACKER
)

SUPPORTED_PLATFORMS = {
    BINARY_SENSOR: "Binary Sensor",
    DEVICE_TRACKER: "Device Tracker"
}


_LOGGER = logging.getLogger(__name__)


class PingFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Met Eireann component."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                    {
                        vol.Required(CONF_NAME, default="Ping"): cv.string,
                        vol.Required(CONF_HOST): cv.string,
                        vol.Required(CONF_SCAN_INTERVAL, default=5): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=1,
                                max=7200,
                                step=1,
                                mode=selector.NumberSelectorMode.BOX,
                            ),
                        ),
                        vol.Required(CONF_PLATFORM, default=list(SUPPORTED_PLATFORMS.keys())): cv.multi_select(SUPPORTED_PLATFORMS),
                    }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self.config = dict(config_entry.data)

    async def async_step_init(self, user_input=None):
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            self.config.update(user_input)
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=self.config
            )
            await self.hass.config_entries.async_reload(self.config_entry.entry_id)
            return self.async_create_entry(title="", data=self.config)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                    {
                        vol.Required(CONF_NAME, default=self.config.get(CONF_NAME)): cv.string,
                        vol.Required(CONF_HOST, default=self.config.get(CONF_HOST)): cv.string,
                        vol.Required(CONF_SCAN_INTERVAL, default=self.config.get(CONF_SCAN_INTERVAL)): selector.NumberSelector(
                            selector.NumberSelectorConfig(
                                min=1,
                                max=7200,
                                step=1,
                                mode=selector.NumberSelectorMode.BOX,
                            ),
                        ),
                        vol.Required(CONF_PLATFORM, default=self.config.get(CONF_PLATFORM)): cv.multi_select(SUPPORTED_PLATFORMS),
                    }
            ),
            errors=errors,
        )
