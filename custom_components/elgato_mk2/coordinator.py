"""DataUpdateCoordinator for the Elgato Key Light MK.2."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import ElgatoMK2Client, ElgatoMK2Error
from .const import DOMAIN, UPDATE_INTERVAL_SECONDS

_LOGGER = logging.getLogger(__name__)


class ElgatoMK2Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls the light for its current state."""

    def __init__(self, hass: HomeAssistant, client: ElgatoMK2Client, host: str) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {host}",
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self.client = client
        self.info: dict[str, Any] = {}

    async def _async_setup(self) -> None:
        try:
            self.info = await self.client.async_get_info()
        except ElgatoMK2Error as err:
            raise UpdateFailed(f"Error fetching accessory-info: {err}") from err

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            state = await self.client.async_get_lights()
        except ElgatoMK2Error as err:
            raise UpdateFailed(f"Error fetching lights: {err}") from err
        return state["lights"][0]
