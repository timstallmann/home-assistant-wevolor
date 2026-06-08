"""Calibration status sensor for the Wevolor integration."""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.core import HomeAssistant

from . import WevolorRuntimeData
from .const import (
    CONFIG_HOST,
    CONFIG_NAME,
    DOMAIN,
    OPTION_EXPERIMENTAL_POSITIONING,
    OPTION_FULL_TRAVEL_TIME_SECS,
)

CALIBRATION_STATUS_OPTIONS = [
    "idle",
    "starting",
    "opening_to_anchor",
    "moving_to_target",
    "awaiting_observation",
    "adjusting",
    "complete",
    "invalid_observation",
    "missing_cover",
]


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up calibration status sensor entities."""
    runtime_data: WevolorRuntimeData = hass.data[DOMAIN][config_entry.entry_id]
    if (
        not runtime_data.get(OPTION_EXPERIMENTAL_POSITIONING, False)
        or runtime_data.get(OPTION_FULL_TRAVEL_TIME_SECS) is None
        or runtime_data.calibration is None
    ):
        return

    async_add_entities(
        [
            WevolorCalibrationStatusSensor(
                runtime_data.get(CONFIG_HOST),
                runtime_data.get(CONFIG_NAME),
                runtime_data.calibration,
            )
        ]
    )


class WevolorCalibrationStatusSensor(SensorEntity):
    """Sensor reporting the current calibration workflow status."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = CALIBRATION_STATUS_OPTIONS
    _attr_translation_key = "calibration_status"

    def __init__(self, host: str, name: str, calibration) -> None:
        """Initialize the calibration status sensor."""
        super().__init__()
        self._calibration = calibration
        self._remove_listener = None
        self._attr_unique_id = f"sensor.wevolor_{name}_calibration_status"
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
        self._remove_listener = self._calibration.register_listener(
            self.async_write_ha_state
        )

    async def async_will_remove_from_hass(self) -> None:
        """Remove the calibration state subscription."""
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None
        await super().async_will_remove_from_hass()

    @property
    def native_value(self) -> str:
        """Return the current calibration status."""
        status = self._calibration.last_status
        if status is None:
            return "idle"
        return status

    @property
    def extra_state_attributes(self) -> dict[str, str | int | float | bool | None]:
        """Expose calibration status attributes."""
        return self._calibration.status_attributes
