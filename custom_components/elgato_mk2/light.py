"""Light platform for the Elgato Key Light MK.2 (local)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import ElgatoMK2ConfigEntry
from .api import ElgatoMK2Error
from .const import DOMAIN, MAX_MIRED, MIN_MIRED
from .coordinator import ElgatoMK2Coordinator


def _mired_to_kelvin(mired: int) -> int:
    return round(1_000_000 / mired)


def _kelvin_to_mired(kelvin: int) -> int:
    return max(MIN_MIRED, min(MAX_MIRED, round(1_000_000 / kelvin)))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ElgatoMK2ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the light entity."""
    async_add_entities([ElgatoMK2Light(entry.runtime_data.coordinator)])


class ElgatoMK2Light(CoordinatorEntity[ElgatoMK2Coordinator], LightEntity):
    """A single Elgato Key Light MK.2."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_color_modes = {ColorMode.COLOR_TEMP}
    _attr_color_mode = ColorMode.COLOR_TEMP
    # Elgato mired 143 (cool) .. 344 (warm)
    _attr_max_color_temp_kelvin = _mired_to_kelvin(MIN_MIRED)
    _attr_min_color_temp_kelvin = _mired_to_kelvin(MAX_MIRED)

    def __init__(self, coordinator: ElgatoMK2Coordinator) -> None:
        super().__init__(coordinator)
        info = coordinator.info
        mac = info.get("macAddress", "")
        self._attr_unique_id = mac or coordinator.name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="Elgato",
            name=info.get("displayName") or info.get("productName", "Key Light MK.2"),
            model=info.get("productName", "Key Light MK.2"),
            sw_version=str(info.get("firmwareVersion", "")),
            connections={("mac", mac)} if mac else set(),
        )

    @property
    def is_on(self) -> bool | None:
        return bool(self.coordinator.data.get("on"))

    @property
    def brightness(self) -> int | None:
        pct = self.coordinator.data.get("brightness")
        return None if pct is None else round(pct * 255 / 100)

    @property
    def color_temp_kelvin(self) -> int | None:
        mired = self.coordinator.data.get("temperature")
        return None if mired is None else _mired_to_kelvin(mired)

    async def async_turn_on(self, **kwargs: Any) -> None:
        params: dict[str, Any] = {"on": True}
        if ATTR_BRIGHTNESS in kwargs:
            params["brightness"] = round(kwargs[ATTR_BRIGHTNESS] * 100 / 255)
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            params["temperature"] = _kelvin_to_mired(kwargs[ATTR_COLOR_TEMP_KELVIN])
        await self._send(params)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._send({"on": False})

    async def _send(self, params: dict[str, Any]) -> None:
        try:
            await self.coordinator.client.async_set_lights(**params)
        except ElgatoMK2Error as err:
            raise HomeAssistantError(f"Failed to control Elgato light: {err}") from err
        await self.coordinator.async_request_refresh()
