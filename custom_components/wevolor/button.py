"""Add 'favorite' button entities for all the shades."""

from __future__ import annotations

from pywevolor import Wevolor
from homeassistant.helpers.entity import generate_entity_id

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONFIG_CHANNEL_, CONFIG_NAME


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up buttons for each Wevolor shade."""

    wevolor = hass.data[DOMAIN][config_entry.entry_id]

    channels = [i for i in range(1, 6) if config_entry.data[f"{CONFIG_CHANNEL_}{i}"]]

    entities = [
        WevolorFavoriteButton(
            hass,
            wevolor,
            channels,
            config_entry.data[CONFIG_NAME],
        )
    ]
    async_add_entities(entities, True)


class WevolorFavoriteButton(ButtonEntity):
    """Button entity to set a wevolor blind to favorite position."""

    _channels: list[int]
    _wevolor: Wevolor

    def __init__(
        self, hass: HomeAssistant, wevolor: Wevolor, channels: list[int], name: str
    ):
        super().__init__()
        """Set up wevolor and channel properties."""
        self._wevolor = wevolor
        self._channels = channels
        self._attr_name = f"Wevolor {name} to Favorite Position"
        self._attr_icon = "mdi:heart"
        self._attr_unique_id = generate_entity_id("button.wevolor_{}", name, None, hass)

    async def async_press(self) -> None:
        """Set this channel to favorite position."""
        if self._wevolor:
            await self._wevolor.favorite_blinds(self._channels)
