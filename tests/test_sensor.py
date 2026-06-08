"""Tests for the calibration status sensor and number availability gating."""

from types import SimpleNamespace

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wevolor import WevolorRuntimeData
from custom_components.wevolor.calibration import WevolorCalibrationCoordinator
from custom_components.wevolor.const import (
    CONFIG_CHANNEL_1,
    CONFIG_CHANNEL_2,
    CONFIG_CHANNEL_3,
    CONFIG_CHANNEL_4,
    CONFIG_CHANNEL_5,
    CONFIG_CHANNEL_6,
    CONFIG_HOST,
    CONFIG_NAME,
    CONFIG_TILT,
    DOMAIN,
    OPTION_EXPERIMENTAL_POSITIONING,
    OPTION_FULL_TRAVEL_TIME_SECS,
)
from custom_components.wevolor.sensor import (
    CALIBRATION_STATUS_OPTIONS,
    WevolorCalibrationStatusSensor,
)
from custom_components.wevolor.number import WevolorObservedOpenPercentNumber


_COMMON_DATA = {
    "name": "simple config",
    CONFIG_HOST: "192.168.1.100",
    CONFIG_CHANNEL_1: True,
    CONFIG_CHANNEL_2: True,
    CONFIG_CHANNEL_3: False,
    CONFIG_CHANNEL_4: False,
    CONFIG_CHANNEL_5: False,
    CONFIG_CHANNEL_6: False,
    CONFIG_NAME: "all_blinds",
    CONFIG_TILT: False,
}

_EXPERIMENTAL_OPTIONS = {
    OPTION_EXPERIMENTAL_POSITIONING: True,
    OPTION_FULL_TRAVEL_TIME_SECS: 10.0,
}


# ---------------------------------------------------------------------------
# Integration-level setup tests
# ---------------------------------------------------------------------------


async def test_sensor_created_when_experimental_on(hass) -> None:
    """Calibration status sensor should be registered when experimental positioning is on."""
    from homeassistant.helpers import entity_registry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_COMMON_DATA,
        options=_EXPERIMENTAL_OPTIONS,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = entity_registry.async_get(hass)
    entity_ids = {e.entity_id for e in registry.entities.values()}
    assert "sensor.wevolor_all_blinds_calibration_status" in entity_ids


async def test_sensor_not_created_when_experimental_off(hass) -> None:
    """Calibration status sensor should not be registered when experimental positioning is off."""
    from homeassistant.helpers import entity_registry

    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_COMMON_DATA,
        # No options → experimental positioning disabled
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = entity_registry.async_get(hass)
    entity_ids = {e.entity_id for e in registry.entities.values()}
    assert "sensor.wevolor_all_blinds_calibration_status" not in entity_ids


# ---------------------------------------------------------------------------
# Unit tests for WevolorCalibrationStatusSensor
# ---------------------------------------------------------------------------


def _make_coordinator(hass) -> WevolorCalibrationCoordinator:
    """Build a minimal coordinator for sensor unit tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            OPTION_EXPERIMENTAL_POSITIONING: True,
            OPTION_FULL_TRAVEL_TIME_SECS: 10.0,
        },
    )
    runtime_data = WevolorRuntimeData(entry=entry, client=SimpleNamespace())
    return WevolorCalibrationCoordinator(hass, runtime_data)


def _make_sensor(coordinator) -> WevolorCalibrationStatusSensor:
    return WevolorCalibrationStatusSensor("192.168.1.1", "test", coordinator)


def test_sensor_initial_value_is_idle(hass) -> None:
    """Sensor should return 'idle' when calibration has not started."""
    coordinator = _make_coordinator(hass)
    sensor = _make_sensor(coordinator)
    assert sensor.native_value == "idle"


def test_sensor_none_status_normalised_to_idle(hass) -> None:
    """Sensor should normalise a None last_status to 'idle'."""
    coordinator = _make_coordinator(hass)
    coordinator.last_status = None  # type: ignore[assignment]
    sensor = _make_sensor(coordinator)
    assert sensor.native_value == "idle"


def test_sensor_native_value_mirrors_last_status(hass) -> None:
    """Sensor native_value should reflect every status the coordinator can emit."""
    coordinator = _make_coordinator(hass)
    sensor = _make_sensor(coordinator)

    for status in CALIBRATION_STATUS_OPTIONS:
        coordinator.last_status = status
        assert sensor.native_value == status


def test_sensor_extra_state_attributes_match_coordinator(hass) -> None:
    """Sensor extra_state_attributes should expose the coordinator's status_attributes."""
    coordinator = _make_coordinator(hass)
    coordinator.active = True
    coordinator.trial_count = 2
    sensor = _make_sensor(coordinator)

    attrs = sensor.extra_state_attributes
    assert attrs["active"] is True
    assert attrs["trial_count"] == 2
    assert attrs == coordinator.status_attributes


def test_sensor_options_list_covers_all_statuses(hass) -> None:
    """The ENUM options list should contain every status the sensor can return."""
    coordinator = _make_coordinator(hass)
    sensor = _make_sensor(coordinator)

    for status in CALIBRATION_STATUS_OPTIONS:
        coordinator.last_status = status
        assert sensor.native_value in sensor._attr_options


# ---------------------------------------------------------------------------
# Unit tests for WevolorObservedOpenPercentNumber availability gating
# ---------------------------------------------------------------------------


def _make_number(coordinator) -> WevolorObservedOpenPercentNumber:
    return WevolorObservedOpenPercentNumber("192.168.1.1", "test", coordinator)


def test_number_unavailable_when_idle(hass) -> None:
    """Number entity should be unavailable when calibration is not active."""
    coordinator = _make_coordinator(hass)
    number = _make_number(coordinator)
    # coordinator starts with active=False, awaiting_observation=False
    assert not number.available


def test_number_unavailable_when_active_but_not_awaiting(hass) -> None:
    """Number entity should be unavailable while calibration is running but not yet waiting."""
    coordinator = _make_coordinator(hass)
    coordinator.active = True
    coordinator.awaiting_observation = False
    number = _make_number(coordinator)
    assert not number.available


def test_number_available_when_awaiting_observation(hass) -> None:
    """Number entity should become available exactly when the coordinator is awaiting observation."""
    coordinator = _make_coordinator(hass)
    coordinator.active = True
    coordinator.awaiting_observation = True
    number = _make_number(coordinator)
    assert number.available


async def test_number_unavailable_after_submission(hass) -> None:
    """Number entity should become unavailable again once the observation is submitted."""
    from types import SimpleNamespace

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

    # Simulate the coordinator being in the awaiting_observation window
    coordinator.active = True
    coordinator.awaiting_observation = True
    coordinator.working_travel_time = 10.0

    number = _make_number(coordinator)
    assert number.available

    # Submit an observation that is within tolerance → calibration completes
    await coordinator.async_submit_observed_position(50.0)

    assert not coordinator.active
    assert not coordinator.awaiting_observation
    assert not number.available


async def test_sensor_status_transitions(hass) -> None:
    """Sensor native_value should track status changes pushed by the coordinator."""
    from types import SimpleNamespace

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
    sensor = _make_sensor(coordinator)

    assert sensor.native_value == "idle"

    coordinator.last_status = "opening_to_anchor"
    assert sensor.native_value == "opening_to_anchor"

    coordinator.last_status = "awaiting_observation"
    assert sensor.native_value == "awaiting_observation"

    coordinator.last_status = "complete"
    assert sensor.native_value == "complete"
