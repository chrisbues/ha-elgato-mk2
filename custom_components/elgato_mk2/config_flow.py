"""Config flow for the Elgato Key Light MK.2 (local)."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ElgatoMK2Client, ElgatoMK2Error
from .const import DOMAIN


class ElgatoMK2ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Elgato Key Light MK.2."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST]
            session = async_get_clientsession(self.hass)
            client = ElgatoMK2Client(host, session)
            try:
                info = await client.async_get_info()
            except ElgatoMK2Error:
                errors["base"] = "cannot_connect"
            else:
                mac = info.get("macAddress")
                if mac:
                    await self.async_set_unique_id(mac)
                    self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info.get("displayName")
                    or info.get("productName", "Key Light MK.2"),
                    data={CONF_HOST: host},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=errors,
        )
