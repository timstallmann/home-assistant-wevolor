"""Cover component for shades controlled by the Wevolor controller."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Literal

from pywevolor import Wevolor
from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.core import HomeAssistant
from homeassistant.helpers.restore_state import RestoreEntity

from . import WevolorRuntimeData
from .const import (
    CONFIG_HOST,
    CONFIG_CHANNEL_,
    CONFIG_NAME,
    CONFIG_TILT,
    DOMAIN,
    OPTION_EXPERIMENTAL_POSITIONING,
    OPTION_FULL_TRAVEL_TIME_SECS,
    OPTION_TREAT_FAVORITE_AS_CLOSED,
)

_LOGGER = logging.getLogger(__name__)

MovementDirection = Literal["opening", "closing"]
MIN_POSITION = 0
MAX_POSITION = 100
MIN_POSITION_DELTA = 1


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up the Wevolor shades."""

    runtime_data: WevolorRuntimeData = hass.data[DOMAIN][config_entry.entry_id]
    channels = [i for i in range(1, 7) if runtime_data.get(f"{CONFIG_CHANNEL_}{i}")]

    entity = WevolorShade(
        runtime_data.client,
        runtime_data.get(CONFIG_HOST),
        channels,
        runtime_data.get(CONFIG_NAME),
        runtime_data.get(CONFIG_TILT, False),
        runtime_data.get(OPTION_EXPERIMENTAL_POSITIONING, False),
        runtime_data.get(OPTION_FULL_TRAVEL_TIME_SECS),
        runtime_data.get(OPTION_TREAT_FAVORITE_AS_CLOSED, False),
    )
    if runtime_data.calibration is not None:
        runtime_data.calibration.register_cover(entity)
    entities = [entity]
    async_add_entities(entities)


class WevolorShade(CoverEntity, RestoreEntity):
    """Cover entity for control of Wevolor remote channel."""

    _attr_assumed_state = True
    _channels: list[int]
    _wevolor: Wevolor

    def __init__(
        self,
        wevolor: Wevolor,
        host: str,
        channels: list[int],
        name: str,
        support_tilt: bool = False,
        experimental_positioning: bool = False,
        full_travel_time_secs: float | None = None,
        treat_favorite_as_closed: bool = False,
    ):
        """Create this wevolor shade cover entity."""
        super().__init__()
        self._wevolor = wevolor
        self._channels = channels
        self._experimental_positioning = experimental_positioning
        self._full_travel_time_secs = full_travel_time_secs
        self._treat_favorite_as_closed = treat_favorite_as_closed
        self._calibration_travel_time_secs: float | None = None
        self._attr_name = f"Wevolor {name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{host}:{name}")},
            manufacturer="Wevolor",
            model="Levolor Blind Group",
            name=f"Wevolor {name}",
            configuration_url=f"http://{host}",
        )
        self._attr_device_class = CoverDeviceClass.SHADE
        self._attr_supported_features = (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        )
        self._attr_unique_id = "cover.wevolor_" + name
        self._current_position: int | None = (
            MAX_POSITION if experimental_positioning else None
        )
        self._target_position: int | None = None
        self._movement_direction: MovementDirection | None = None
        self._movement_started_monotonic: float | None = None
        self._movement_start_position: int | None = None
        self._scheduled_completion_task: asyncio.Task[None] | None = None

        if experimental_positioning and full_travel_time_secs is not None:
            self._attr_supported_features |= CoverEntityFeature.SET_POSITION

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
        _LOGGER.debug(
            "Stopping Wevolor cover %s; current=%s target=%s direction=%s",
            self.entity_id,
            self._current_position,
            self._target_position,
            self._movement_direction,
        )
        self._sync_current_position()
        self._clear_motion_state()
        self.async_write_ha_state()
        await self._wevolor.stop_blinds(self._channels)

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        if self._supports_positioning:
            current_position = self.current_cover_position
            if current_position is None:
                current_position = self._current_position or MIN_POSITION
            self._target_position = MAX_POSITION
        self._begin_motion("opening")
        if self._supports_positioning:
            self._schedule_completion_for_duration(
                self._travel_time_for_delta(MAX_POSITION - current_position),
                MAX_POSITION,
                send_stop=False,
            )
        _LOGGER.debug(
            "Opening Wevolor cover %s; current=%s target=%s supports_positioning=%s",
            self.entity_id,
            current_position if self._supports_positioning else None,
            self._target_position,
            self._supports_positioning,
        )
        self.async_write_ha_state()
        await self._wevolor.open_blinds(self._channels)

    async def async_close_cover(self, **kwargs):
        """Close the cover."""
        if self._supports_positioning:
            current_position = self.current_cover_position
            if current_position is None:
                current_position = self._current_position or MAX_POSITION
            self._target_position = MIN_POSITION
        self._begin_motion("closing")
        if self._supports_positioning:
            self._schedule_completion_for_duration(
                self._travel_time_for_delta(current_position - MIN_POSITION),
                MIN_POSITION,
                send_stop=False,
            )
        _LOGGER.debug(
            "Closing Wevolor cover %s; current=%s target=%s supports_positioning=%s treat_favorite_as_closed=%s",
            self.entity_id,
            current_position if self._supports_positioning else None,
            self._target_position,
            self._supports_positioning,
            self._treat_favorite_as_closed,
        )
        self.async_write_ha_state()
        if self._treat_favorite_as_closed:
            await self._wevolor.favorite_blinds(self._channels)
        else:
            await self._wevolor.close_blinds(self._channels)

    async def async_set_cover_position(self, **kwargs) -> None:
        """Move the cover to an estimated position."""
        if not self._supports_positioning:
            return

        requested_position = kwargs[ATTR_POSITION]
        target_position = self._clamp_position(requested_position)
        if target_position == MIN_POSITION:
            _LOGGER.debug(
                "Set position requested full close for Wevolor cover %s; delegating to close_cover",
                self.entity_id,
            )
            await self.async_close_cover(**kwargs)
            return
        if target_position == MAX_POSITION:
            _LOGGER.debug(
                "Set position requested full open for Wevolor cover %s; delegating to open_cover",
                self.entity_id,
            )
            await self.async_open_cover(**kwargs)
            return

        current_position = self.current_cover_position
        if current_position is None:
            current_position = self._current_position
        if current_position is None:
            current_position = MAX_POSITION

        position_delta = target_position - current_position
        _LOGGER.debug(
            "Set position requested for Wevolor cover %s; current=%s target=%s delta=%s",
            self.entity_id,
            current_position,
            target_position,
            position_delta,
        )
        if abs(position_delta) < MIN_POSITION_DELTA:
            self._current_position = target_position
            self._target_position = target_position
            self.async_write_ha_state()
            return

        direction: MovementDirection = "opening" if position_delta > 0 else "closing"
        self._target_position = target_position
        self._begin_motion(direction)
        self._schedule_completion_for_duration(
            self._travel_time_for_delta(abs(position_delta)),
            target_position,
            send_stop=True,
        )
        _LOGGER.debug(
            "Scheduled partial move for Wevolor cover %s; direction=%s duration=%.3fs target=%s",
            self.entity_id,
            direction,
            self._travel_time_for_delta(abs(position_delta)),
            target_position,
        )
        self.async_write_ha_state()

        if direction == "opening":
            await self._wevolor.open_blinds(self._channels)
        else:
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
        _LOGGER.debug(
            "Begin motion for Wevolor cover %s; direction=%s start_position=%s",
            self.entity_id,
            direction,
            self._movement_start_position,
        )

    def _sync_current_position(self) -> None:
        """Update the implied position based on elapsed motion time."""
        if (
            not self._supports_positioning
            or self._movement_direction is None
            or self._movement_started_monotonic is None
            or self._movement_start_position is None
        ):
            return

        elapsed_seconds = max(0.0, time.monotonic() - self._movement_started_monotonic)
        # _supports_positioning (checked above) guarantees this is non-None and > 0.
        assert self._effective_full_travel_time_secs is not None
        elapsed_position_delta = round(
            elapsed_seconds / self._effective_full_travel_time_secs * MAX_POSITION
        )
        signed_delta = (
            elapsed_position_delta
            if self._movement_direction == "opening"
            else -elapsed_position_delta
        )
        current_position = self._clamp_position(
            self._movement_start_position + signed_delta
        )

        if self._target_position is not None:
            if self._movement_direction == "opening":
                current_position = min(current_position, self._target_position)
            else:
                current_position = max(current_position, self._target_position)

        self._current_position = current_position

    def _clear_motion_state(self) -> None:
        """Clear in-flight motion state."""
        _LOGGER.debug(
            "Clearing motion state for Wevolor cover %s; current=%s target=%s direction=%s",
            self.entity_id,
            self._current_position,
            self._target_position,
            self._movement_direction,
        )
        self._cancel_scheduled_stop()
        self._target_position = None
        self._movement_direction = None
        self._movement_started_monotonic = None
        self._movement_start_position = None

    def _cancel_scheduled_stop(self) -> None:
        """Cancel a scheduled stop callback if one exists."""
        if self._scheduled_completion_task is not None:
            _LOGGER.debug(
                "Cancelling scheduled completion for Wevolor cover %s", self.entity_id
            )
            self._scheduled_completion_task.cancel()
            self._scheduled_completion_task = None

    @property
    def _supports_positioning(self) -> bool:
        """Return whether timed positioning is configured."""
        return (
            self._experimental_positioning
            and self._effective_full_travel_time_secs is not None
            and self._effective_full_travel_time_secs > 0
        )

    def _travel_time_for_delta(self, position_delta: int) -> float:
        """Convert a position delta into a travel duration."""
        # All callers are guarded by _supports_positioning, which ensures non-None and > 0.
        assert self._effective_full_travel_time_secs is not None
        return self._effective_full_travel_time_secs * position_delta / MAX_POSITION

    def _schedule_completion_for_duration(
        self,
        duration_seconds: float,
        target_position: int | None,
        *,
        send_stop: bool,
    ) -> None:
        """Schedule completion handling for the current timed movement."""
        self._cancel_scheduled_stop()
        _LOGGER.debug(
            "Scheduling completion for Wevolor cover %s in %.3fs; target=%s send_stop=%s",
            self.entity_id,
            duration_seconds,
            target_position,
            send_stop,
        )
        self._scheduled_completion_task = self.hass.async_create_task(
            self._async_wait_and_complete(
                duration_seconds,
                target_position,
                send_stop=send_stop,
            )
        )

    async def _async_wait_and_complete(
        self,
        duration_seconds: float,
        target_position: int | None,
        *,
        send_stop: bool,
    ) -> None:
        """Wait for the travel duration, then complete the movement."""
        try:
            _LOGGER.debug(
                "Waiting %.3fs before completion for Wevolor cover %s; target=%s send_stop=%s",
                duration_seconds,
                self.entity_id,
                target_position,
                send_stop,
            )
            await asyncio.sleep(max(0.0, duration_seconds))
            _LOGGER.debug(
                "Scheduled completion woke for Wevolor cover %s; target=%s send_stop=%s",
                self.entity_id,
                target_position,
                send_stop,
            )
            await self._async_handle_scheduled_completion(
                target_position,
                send_stop=send_stop,
            )
        except asyncio.CancelledError:
            _LOGGER.debug(
                "Scheduled completion cancelled for Wevolor cover %s", self.entity_id
            )
            return

    async def _async_handle_scheduled_completion(
        self,
        target_position: int | None,
        *,
        send_stop: bool,
    ) -> None:
        """Handle an internally scheduled movement completion."""
        self._scheduled_completion_task = None
        _LOGGER.debug(
            "Handling scheduled completion for Wevolor cover %s; current=%s target=%s send_stop=%s",
            self.entity_id,
            self._current_position,
            target_position,
            send_stop,
        )
        self._sync_current_position()
        if target_position is not None:
            self._current_position = target_position
        self._clear_motion_state()
        self.async_write_ha_state()
        if send_stop:
            _LOGGER.debug("Issuing timed stop for Wevolor cover %s", self.entity_id)
            await self._wevolor.stop_blinds(self._channels)

    def _clamp_position(self, position: int | float) -> int:
        """Clamp a position to HA cover bounds."""
        return max(MIN_POSITION, min(MAX_POSITION, round(position)))

    @property
    def _effective_full_travel_time_secs(self) -> float | None:
        """Return the active travel-time estimate."""
        return self._calibration_travel_time_secs or self._full_travel_time_secs

    def set_calibration_travel_time(self, travel_time: float | None) -> None:
        """Override the travel-time estimate during guided calibration."""
        self._calibration_travel_time_secs = travel_time
