"""Calibration coordinator for experimental timed positioning."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging
from typing import TYPE_CHECKING

from .const import (
    CALIBRATION_SETTLE_SECONDS,
    CALIBRATION_TARGET_POSITION,
    CALIBRATION_TOLERANCE,
    OPTION_EXPERIMENTAL_POSITIONING,
    OPTION_FULL_TRAVEL_TIME_SECS,
)

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from . import WevolorRuntimeData
    from .cover import WevolorShade

_LOGGER = logging.getLogger(__name__)


class WevolorCalibrationCoordinator:
    """Coordinate guided calibration for timed positioning."""

    def __init__(self, hass: HomeAssistant, runtime_data: WevolorRuntimeData) -> None:
        """Initialize calibration state."""
        self._hass = hass
        self._runtime_data = runtime_data
        self._cover: WevolorShade | None = None
        self._listeners: list[Callable[[], None]] = []
        self._task: asyncio.Task[None] | None = None
        self.active = False
        self.awaiting_observation = False
        self.trial_count = 0
        self.last_observed_open_percent: float | None = None
        self.last_refined_travel_time: float | None = None
        self.working_travel_time: float | None = None
        self.last_status = "idle"

    def register_cover(self, cover: WevolorShade) -> None:
        """Register the cover used for calibration moves."""
        self._cover = cover

    def register_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        """Register a state-update listener."""
        self._listeners.append(listener)

        def _remove() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return _remove

    @property
    def target_position(self) -> int:
        """Return the calibration target position."""
        return CALIBRATION_TARGET_POSITION

    @property
    def tolerance(self) -> int:
        """Return the accepted target tolerance."""
        return CALIBRATION_TOLERANCE

    @property
    def configured_travel_time(self) -> float | None:
        """Return the currently configured travel time."""
        travel_time = self._runtime_data.get(OPTION_FULL_TRAVEL_TIME_SECS)
        if travel_time is None:
            return None
        return float(travel_time)

    @property
    def supports_calibration(self) -> bool:
        """Return whether calibration can be started."""
        return bool(
            self._runtime_data.get(OPTION_EXPERIMENTAL_POSITIONING, False)
            and self.configured_travel_time is not None
            and self._cover is not None
        )

    @property
    def status_attributes(self) -> dict[str, str | int | float | bool | None]:
        """Expose calibration state for UI entities."""
        return {
            "active": self.active,
            "awaiting_observation": self.awaiting_observation,
            "trial_count": self.trial_count,
            "target_position": self.target_position,
            "tolerance": self.tolerance,
            "configured_travel_time": self.configured_travel_time,
            "working_travel_time": self.working_travel_time,
            "last_observed_open_percent": self.last_observed_open_percent,
            "last_refined_travel_time": self.last_refined_travel_time,
            "status": self.last_status,
        }

    async def async_start(self) -> None:
        """Start or restart the calibration loop."""
        if not self.supports_calibration:
            _LOGGER.debug("Ignoring Wevolor calibration start; requirements not met")
            return

        self._cancel_task()
        self.active = True
        self.awaiting_observation = False
        self.trial_count = 0
        self.last_observed_open_percent = None
        self.last_refined_travel_time = self.configured_travel_time
        self.working_travel_time = self.configured_travel_time
        self.last_status = "starting"
        if self._cover is not None:
            self._cover.set_calibration_travel_time(self.working_travel_time)
        self._notify_listeners()
        self._task = self._hass.async_create_task(self._async_run_trial())

    async def async_submit_observed_position(self, observed_open_percent: float) -> None:
        """Handle user-submitted midpoint observation."""
        if not self.active or not self.awaiting_observation:
            _LOGGER.debug(
                "Ignoring Wevolor calibration observation %.1f; active=%s awaiting=%s",
                observed_open_percent,
                self.active,
                self.awaiting_observation,
            )
            return

        observed_open_percent = max(0.0, min(100.0, observed_open_percent))
        self.last_observed_open_percent = observed_open_percent
        observed_delta = 100.0 - observed_open_percent
        commanded_delta = 100.0 - self.target_position
        current_travel_time = self.working_travel_time
        if current_travel_time is None or observed_delta <= 0:
            self.last_status = "invalid_observation"
            self._notify_listeners()
            return

        refined_travel_time = current_travel_time * (commanded_delta / observed_delta)
        self.last_refined_travel_time = refined_travel_time

        if abs(observed_open_percent - self.target_position) <= self.tolerance:
            self.last_status = "complete"
            self.awaiting_observation = False
            self.active = False
            self.working_travel_time = refined_travel_time
            if self._cover is not None:
                self._cover.set_calibration_travel_time(None)
            await self._async_persist_travel_time(refined_travel_time)
            self._notify_listeners()
            return

        self.last_status = "adjusting"
        self.awaiting_observation = False
        self.working_travel_time = refined_travel_time
        if self._cover is not None:
            self._cover.set_calibration_travel_time(refined_travel_time)
        self._notify_listeners()
        self._task = self._hass.async_create_task(self._async_run_trial())

    async def _async_run_trial(self) -> None:
        """Run a single full-open then midpoint calibration trial."""
        if self._cover is None:
            self.last_status = "missing_cover"
            self.active = False
            self._notify_listeners()
            return

        self.trial_count += 1
        self.last_status = "opening_to_anchor"
        self._notify_listeners()
        _LOGGER.debug("Starting Wevolor calibration trial %s", self.trial_count)
        try:
            self._cover.set_calibration_travel_time(self.working_travel_time)
            await self._cover.async_open_cover()
            await asyncio.sleep(
                (self.working_travel_time or 0) + CALIBRATION_SETTLE_SECONDS
            )
            self.last_status = "moving_to_target"
            self._notify_listeners()
            await self._cover.async_set_cover_position(position=self.target_position)
            await asyncio.sleep(
                ((self.working_travel_time or 0) / 2) + CALIBRATION_SETTLE_SECONDS
            )
            self.awaiting_observation = True
            self.last_status = "awaiting_observation"
            self._notify_listeners()
        except asyncio.CancelledError:
            _LOGGER.debug("Cancelled Wevolor calibration trial %s", self.trial_count)
            return

    async def _async_persist_travel_time(self, travel_time: float) -> None:
        """Persist a refined travel time into config-entry options."""
        entry: ConfigEntry = self._runtime_data.entry
        updated_options = dict(entry.options)
        updated_options[OPTION_FULL_TRAVEL_TIME_SECS] = round(travel_time, 3)
        self._hass.config_entries.async_update_entry(entry, options=updated_options)

    def _cancel_task(self) -> None:
        """Cancel an in-flight calibration task."""
        if self._task is not None:
            self._task.cancel()
            self._task = None
        if self._cover is not None:
            self._cover.set_calibration_travel_time(None)

    def _notify_listeners(self) -> None:
        """Notify UI entities that calibration state changed."""
        for listener in list(self._listeners):
            listener()
