"""Cover component for shades controlled by the Wevolor controller."""

from __future__ import annotations

from pywevolor import Wevolor
from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant

from .const import CONFIG_TILT, DOMAIN, CONFIG_CHANNEL_, CONFIG_NAME


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up the Wevolor shades."""

    wevolor = hass.data[DOMAIN][config_entry.entry_id]
    channels = [i for i in range(1, 6) if config_entry.data[f"{CONFIG_CHANNEL_}{i}"]]

    entities = [
        WevolorShade(
            hass,
            wevolor,
            channels,
            config_entry.data[CONFIG_NAME],
            config_entry.data[CONFIG_TILT],
        )
    ]
    async_add_entities(entities)


class WevolorShade(CoverEntity):
    """Cover entity for control of Wevolor remote channel."""

    _attr_assumed_state = True
    _channels: list[int]
    _wevolor: Wevolor

    def __init__(
        self,
        hass: HomeAssistant,
        wevolor: Wevolor,
        channels: list[int],
        name: str,
        support_tilt: bool = False,
    ):
        """Create this wevolor shade cover entity."""
        super().__init__()
        self._wevolor = wevolor
        self._channels = channels
        self._attr_name = f"Wevolor {name}"
        self._attr_device_class = CoverDeviceClass.SHADE
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        )
        self._attr_unique_id = "cover.wevolor_" + name

        if support_tilt:
            self._attr_device_class = CoverDeviceClass.BLIND
            self._attr_supported_features |= (
                CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                | CoverEntityFeature.STOP_TILT
            )

    async def async_stop_cover(self, **kwargs):
        """Stop motion."""
        await self._wevolor.stop_blinds(self._channels)

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self._wevolor.open_blinds(self._channels)

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        await self._wevolor.close_blinds(self._channels)

    async def async_open_cover_tilt(self, **kwargs):
        """Open tilt."""
        await self._wevolor.open_blinds_tilt(self._channels)

    async def async_close_cover_tilt(self, **kwargs):
        """Close tilt."""
        await self._wevolor.close_blinds_tilt(self._channels)

    async def async_stop_cover_tilt(self, **kwargs):
        """Stop tilt."""
        await self._wevolor.stop_blinds_tilt(self._channels)

    @property
    def is_closed(self) -> bool | None:
        """Since Wevolor does not expose any status, return None here."""
        return None
