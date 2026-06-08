"""The Wevolor Control for Levolor Motorized Blinds integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pywevolor import Wevolor

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .calibration import WevolorCalibrationCoordinator
from .const import CONFIG_HOST, DOMAIN

PLATFORMS: list[str] = [
    Platform.COVER,
    Platform.BUTTON,
    Platform.NUMBER,
]


@dataclass
class WevolorRuntimeData:
    """Runtime data for a Wevolor config entry."""

    client: Wevolor
    entry: ConfigEntry
    calibration: WevolorCalibrationCoordinator | None = None

    def get(self, key: str, default: Any | None = None) -> Any:
        """Return a merged config value, preferring options over entry data."""
        if key in self.entry.options:
            return self.entry.options[key]
        return self.entry.data.get(key, default)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Wevolor Control for Levolor Motorized Blinds from a config entry."""
    runtime_data = WevolorRuntimeData(
        client=Wevolor(host=entry.data[CONFIG_HOST]),
        entry=entry,
    )
    runtime_data.calibration = WevolorCalibrationCoordinator(hass, runtime_data)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime_data
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when config-entry options change."""
    await hass.config_entries.async_reload(entry.entry_id)
