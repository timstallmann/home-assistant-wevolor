"""Tests for guided calibration."""

from types import SimpleNamespace

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wevolor import WevolorRuntimeData
from custom_components.wevolor.calibration import WevolorCalibrationCoordinator
from custom_components.wevolor.const import (
    DOMAIN,
    OPTION_EXPERIMENTAL_POSITIONING,
    OPTION_FULL_TRAVEL_TIME_SECS,
)


class DummyCover:
    """Minimal cover stub for calibration tests."""

    def __init__(self) -> None:
        self.calibration_travel_time = None

    def set_calibration_travel_time(self, travel_time):
        """Store the active calibration travel time."""
        self.calibration_travel_time = travel_time


async def test_calibration_refines_in_memory_until_complete(hass) -> None:
    """Calibration should keep intermediate adjustments in memory."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            OPTION_EXPERIMENTAL_POSITIONING: True,
            OPTION_FULL_TRAVEL_TIME_SECS: 10.0,
        },
    )
    runtime_data = WevolorRuntimeData(entry=entry, client=SimpleNamespace())
    coordinator = WevolorCalibrationCoordinator(hass, runtime_data)
    cover = DummyCover()
    coordinator.register_cover(cover)

    coordinator.active = True
    coordinator.awaiting_observation = True
    coordinator.working_travel_time = 10.0

    await coordinator.async_submit_observed_position(35.0)

    assert round(coordinator.working_travel_time, 3) == 7.692
    assert coordinator.last_status == "adjusting"
    assert entry.options[OPTION_FULL_TRAVEL_TIME_SECS] == 10.0

    coordinator.awaiting_observation = True
    coordinator.active = True
    await coordinator.async_submit_observed_position(49.0)

    assert coordinator.active is False
    assert coordinator.awaiting_observation is False
    assert round(entry.options[OPTION_FULL_TRAVEL_TIME_SECS], 3) == 7.848
