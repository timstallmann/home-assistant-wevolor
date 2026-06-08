"""Cover component for shades controlled by the Wevolor controller."""

from __future__ import annotations

from collections.abc import Callable
import time
from typing import Literal

from pywevolor import Wevolor
from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity

from . import WevolorRuntimeData
from .const import (
    CONFIG_CHANNEL_,
    CONFIG_NAME,
    CONFIG_TILT,
    DOMAIN,
    OPTION_EXPERIMENTAL_POSITIONING,
)

MovementDirection = Literal["opening", "closing"]
MIN_POSITION = 0
MAX_POSITION = 100


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up the Wevolor shades."""

    runtime_data: WevolorRuntimeData = hass.data[DOMAIN][config_entry.entry_id]
    channels = [i for i in range(1, 7) if runtime_data.get(f"{CONFIG_CHANNEL_}{i}")]

    entities = [
        WevolorShade(
            hass,
            runtime_data.client,
            channels,
            runtime_data.get(CONFIG_NAME),
            runtime_data.get(CONFIG_TILT, False),
            runtime_data.get(OPTION_EXPERIMENTAL_POSITIONING, False),
        )
    ]
    async_add_entities(entities)


class WevolorShade(CoverEntity, RestoreEntity):
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
        experimental_positioning: bool = False,
    ):
        """Create this wevolor shade cover entity."""
        super().__init__()
        self._wevolor = wevolor
        self._channels = channels
        self._experimental_positioning = experimental_positioning
        self._attr_name = f"Wevolor {name}"
        self._attr_device_class = CoverDeviceClass.SHADE
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        )
        self._attr_unique_id = "cover.wevolor_" + name
        self._current_position: int | None = MAX_POSITION if experimental_positioning else None
        self._target_position: int | None = None
        self._movement_direction: MovementDirection | None = None
        self._movement_started_monotonic: float | None = None
        self._movement_start_position: int | None = None
        self._scheduled_stop_unsub: Callable[[], None] | None = None

        if support_tilt:
            self._attr_device_class = CoverDeviceClass.BLIND
            self._attr_supported_features |= (
                CoverEntityFeature.OPEN_TILT
                | CoverEntityFeature.CLOSE_TILT
                | CoverEntityFeature.STOP_TILT
            )

    async def async_added_to_hass(self) -> None:
        """Restore the last implied position when experimental mode is enabled."""
        await super().async_added_to_hass()
        if not self._experimental_positioning:
            return

        last_state = await self.async_get_last_state()
        if last_state is None:
            return

        restored_position = last_state.attributes.get("current_position")
        if restored_position is None:
            restored_position = last_state.attributes.get("current_cover_position")

        if restored_position is not None:
            self._current_position = max(
                MIN_POSITION,
                min(MAX_POSITION, round(float(restored_position))),
            )

    async def async_stop_cover(self, **kwargs):
        """Stop motion."""
        self._sync_current_position()
        self._clear_motion_state()
        self.async_write_ha_state()
        await self._wevolor.stop_blinds(self._channels)

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        self._begin_motion("opening")
        self.async_write_ha_state()
        await self._wevolor.open_blinds(self._channels)

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        self._begin_motion("closing")
        self.async_write_ha_state()
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
    def current_cover_position(self) -> int | None:
        """Return the estimated current cover position."""
        if not self._experimental_positioning:
            return None

        self._sync_current_position()
        return self._current_position

    @property
    def is_closed(self) -> bool | None:
        """Since Wevolor does not expose any status, return None here."""
        if self._experimental_positioning and self.current_cover_position is not None:
            return self.current_cover_position == MIN_POSITION
        return None

    @property
    def is_opening(self) -> bool | None:
        """Return whether the cover is opening."""
        return self._movement_direction == "opening"

    @property
    def is_closing(self) -> bool | None:
        """Return whether the cover is closing."""
        return self._movement_direction == "closing"

    @property
    def extra_state_attributes(self) -> dict[str, int | str] | None:
        """Expose debug-friendly implied-position state."""
        if not self._experimental_positioning or self._current_position is None:
            return None

        attributes: dict[str, int | str] = {
            "current_position": self._current_position,
        }
        if self._target_position is not None:
            attributes["target_position"] = self._target_position
        if self._movement_direction is not None:
            attributes["movement_direction"] = self._movement_direction
        return attributes

    def _begin_motion(self, direction: MovementDirection) -> None:
        """Start tracking cover motion."""
        if not self._experimental_positioning:
            return

        self._sync_current_position()
        self._cancel_scheduled_stop()
        self._movement_direction = direction
        self._movement_started_monotonic = time.monotonic()
        self._movement_start_position = self._current_position

    def _sync_current_position(self) -> None:
        """Update the implied position based on elapsed motion time."""
        if (
            not self._experimental_positioning
            or self._movement_direction is None
            or self._movement_started_monotonic is None
            or self._movement_start_position is None
        ):
            return

    def _clear_motion_state(self) -> None:
        """Clear in-flight motion state."""
        self._cancel_scheduled_stop()
        self._target_position = None
        self._movement_direction = None
        self._movement_started_monotonic = None
        self._movement_start_position = None

    def _cancel_scheduled_stop(self) -> None:
        """Cancel a scheduled stop callback if one exists."""
        if self._scheduled_stop_unsub is not None:
            self._scheduled_stop_unsub()
            self._scheduled_stop_unsub = None
