"""Add 'favorite' button entities for all the shades."""

from __future__ import annotations

from pywevolor import Wevolor
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import generate_entity_id

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant

from . import WevolorRuntimeData
from .const import CONFIG_CHANNEL_, CONFIG_HOST, CONFIG_NAME, DOMAIN


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up buttons for each Wevolor shade."""

    runtime_data: WevolorRuntimeData = hass.data[DOMAIN][config_entry.entry_id]

    channels = [i for i in range(1, 7) if runtime_data.get(f"{CONFIG_CHANNEL_}{i}")]

    entities = [
        WevolorFavoriteButton(
            hass,
            runtime_data.client,
            runtime_data.get(CONFIG_HOST),
            channels,
            runtime_data.get(CONFIG_NAME),
        )
    ]
    async_add_entities(entities)


class WevolorFavoriteButton(ButtonEntity):
    """Button entity to set a wevolor blind to favorite position."""

    _channels: list[int]
    _wevolor: Wevolor

    def __init__(
        self,
        hass: HomeAssistant,
        wevolor: Wevolor,
        host: str,
        channels: list[int],
        name: str,
    ):
        super().__init__()
        """Set up wevolor and channel properties."""
        self._wevolor = wevolor
        self._channels = channels
        self._attr_name = f"Wevolor {name} to Favorite Position"
        self._attr_icon = "mdi:heart"
        self._attr_unique_id = generate_entity_id("button.wevolor_{}", name, None, hass)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{host}:{name}")},
            manufacturer="Wevolor",
            model="Levolor Blind Group",
            name=f"Wevolor {name}",
            configuration_url=f"http://{host}",
        )

    async def async_press(self) -> None:
        """Set this channel to favorite position."""
        if self._wevolor:
            await self._wevolor.favorite_blinds(self._channels)
