"""Add 'favorite' button entities for all the shades.

N.b. this is a workaround pending https://github.com/home-assistant/architecture/issues/698
"""

from __future__ import annotations

from pywevolor import Wevolor

from homeassistant.components.button import ButtonEntity

from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up buttons for each Wevolor shade."""

    entities = []
    wevolor = hass.data[DOMAIN][config_entry.entry_id]

    channel_ids = range(1, config_entry.data["channel_count"] + 1)

    for channel_id in channel_ids:
        entity = WevolorFavoriteButton(wevolor, channel_id)
        entities.append(entity)

    async_add_entities(entities, True)


class WevolorFavoriteButton(ButtonEntity):
    """Button entity to set a wevolor blind to favorite position."""

    _channel: int | None = None
    _wevolor: Wevolor | None = None

    def __init__(self, wevolor: Wevolor, channel: int):
        """Set up wevolor and channel properties."""
        self._wevolor = wevolor
        self._channel = channel

    @property
    def name(self):
        """Return the name of the device."""
        return f"Set favorite for Wevolor channel #{self._channel}"

    @property
    def icon(self) -> str:
        """Return the name of the icon to use in the UI."""
        return "mdi:heart"

    async def async_press(self) -> None:
        """Set this channel to favorite position."""
        if self._wevolor:
            await self._wevolor.favorite_blind(self._channel)
