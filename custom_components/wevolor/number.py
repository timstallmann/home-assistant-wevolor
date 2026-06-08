"""Calibration number entities for the Wevolor integration."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
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


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up calibration number entities."""
    runtime_data: WevolorRuntimeData = hass.data[DOMAIN][config_entry.entry_id]
    if (
        not runtime_data.get(OPTION_EXPERIMENTAL_POSITIONING, False)
        or runtime_data.get(OPTION_FULL_TRAVEL_TIME_SECS) is None
        or runtime_data.calibration is None
    ):
        return

    async_add_entities(
        [
            WevolorObservedOpenPercentNumber(
                runtime_data.get(CONFIG_HOST),
                runtime_data.get(CONFIG_NAME),
                runtime_data.calibration,
            )
        ]
    )


class WevolorObservedOpenPercentNumber(NumberEntity):
    """User input for the observed open percentage during calibration."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX
    _attr_name = "Observed Percent Open"
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1

    def __init__(self, host: str, name: str, calibration) -> None:
        """Initialize the observed-open number entity."""
        super().__init__()
        self._calibration = calibration
        self._remove_listener = None
        self._attr_unique_id = f"number.wevolor_{name}_observed_percent_open"
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
        """Return whether the entity should accept user input."""
        return self._calibration.supports_calibration

    @property
    def native_value(self) -> float | None:
        """Return the last observed percent open."""
        return self._calibration.last_observed_open_percent

    @property
    def extra_state_attributes(self) -> dict[str, str | int | float | bool | None]:
        """Expose calibration status attributes."""
        return self._calibration.status_attributes

    async def async_set_native_value(self, value: float) -> None:
        """Submit the observed percent open."""
        await self._calibration.async_submit_observed_position(value)
