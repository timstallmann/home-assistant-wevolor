"""Add 'favorite' button entities for all the shades."""

from __future__ import annotations

from pywevolor import Wevolor

from homeassistant.components.button import ButtonEntity

from .const import DOMAIN, CONFIG_CHANNELS


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up buttons for each Wevolor shade."""

    wevolor = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        WevolorFavoriteButton(wevolor, channel_id)
        for channel_id in range(1, config_entry.data[CONFIG_CHANNELS] + 1)
    ]
    async_add_entities(entities, True)


class WevolorFavoriteButton(ButtonEntity):
    """Button entity to set a wevolor blind to favorite position."""

    _channel: int
    _wevolor: Wevolor

    def __init__(self, wevolor: Wevolor, channel: int):
        """Set up wevolor and channel properties."""
        self._wevolor = wevolor
        self._channel = channel
        self._attr_name = f"Wevolor Channel #{channel} Favorite Position"
        self._attr_icon = "mdi:heart"

    async def async_press(self) -> None:
        """Set this channel to favorite position."""
        if self._wevolor:
            await self._wevolor.favorite_blind(self._channel)
