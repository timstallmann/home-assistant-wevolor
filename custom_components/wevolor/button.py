"""Add 'favorite' button entities for all the shades."""

from __future__ import annotations

from pywevolor import Wevolor
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import generate_entity_id

from homeassistant.core import HomeAssistant

from . import WevolorRuntimeData
from .const import (
    CONFIG_CHANNEL_,
    CONFIG_HOST,
    CONFIG_NAME,
    DOMAIN,
    OPTION_EXPERIMENTAL_POSITIONING,
    OPTION_FULL_TRAVEL_TIME_SECS,
)


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
    if (
        runtime_data.get(OPTION_EXPERIMENTAL_POSITIONING, False)
        and runtime_data.get(OPTION_FULL_TRAVEL_TIME_SECS) is not None
        and runtime_data.calibration is not None
    ):
        entities.append(
            WevolorStartCalibrationButton(
                runtime_data.get(CONFIG_HOST),
                runtime_data.get(CONFIG_NAME),
                runtime_data.calibration,
            )
        )
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


class WevolorStartCalibrationButton(ButtonEntity):
    """Button entity to start guided calibration."""

    def __init__(self, host: str, name: str, calibration) -> None:
        """Initialize the calibration button."""
        super().__init__()
        self._calibration = calibration
        self._remove_listener = None
        self._attr_name = f"Wevolor {name} Start Calibration"
        self._attr_icon = "mdi:tune-variant"
        self._attr_unique_id = f"button.wevolor_{name}_start_calibration"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{host}:{name}")},
            manufacturer="Wevolor",
            model="Levolor Blind Group",
            name=f"Wevolor {name}",
            configuration_url=f"http://{host}",
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to calibration state updates."""
        await super().async_added_to_hass()
        self._remove_listener = self._calibration.register_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Remove the calibration state subscription."""
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None
        await super().async_will_remove_from_hass()

    @property
    def available(self) -> bool:
        """Return whether calibration can be started."""
        return self._calibration.supports_calibration and not self._calibration.active

    @property
    def extra_state_attributes(self) -> dict[str, str | int | float | bool | None]:
        """Expose calibration status attributes."""
        return self._calibration.status_attributes

    async def async_press(self) -> None:
        """Start the calibration workflow."""
        await self._calibration.async_start()
