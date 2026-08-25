"""The Elgato Key Light MK.2 (local) integration."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ElgatoMK2Client
from .coordinator import ElgatoMK2Coordinator

PLATFORMS: list[Platform] = [Platform.LIGHT]


@dataclass
class ElgatoMK2Data:
    """Runtime data stored on the config entry."""

    coordinator: ElgatoMK2Coordinator


type ElgatoMK2ConfigEntry = ConfigEntry[ElgatoMK2Data]


async def async_setup_entry(hass: HomeAssistant, entry: ElgatoMK2ConfigEntry) -> bool:
    """Set up Elgato Key Light MK.2 from a config entry."""
    host = entry.data[CONF_HOST]
    session = async_get_clientsession(hass)
    client = ElgatoMK2Client(host, session)
    coordinator = ElgatoMK2Coordinator(hass, client, host)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = ElgatoMK2Data(coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ElgatoMK2ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
