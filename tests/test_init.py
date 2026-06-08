"""Test sensor for simple integration."""

from homeassistant.helpers import device_registry
from pytest_homeassistant_custom_component.common import MockConfigEntry
from homeassistant.helpers import entity_registry

from custom_components.wevolor.const import (
    DOMAIN,
    CONFIG_HOST,
    CONFIG_CHANNEL_1,
    CONFIG_CHANNEL_2,
    CONFIG_CHANNEL_3,
    CONFIG_CHANNEL_4,
    CONFIG_CHANNEL_5,
    CONFIG_CHANNEL_6,
    CONFIG_NAME,
    CONFIG_TILT,
    OPTION_EXPERIMENTAL_POSITIONING,
    OPTION_FULL_TRAVEL_TIME_SECS,
)


async def test_sensor(hass):
    """Test sensor."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
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
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("cover.wevolor_all_blinds")
    favorite_state = hass.states.get("button.wevolor_all_blinds_to_favorite_position")
    assert state
    assert favorite_state
    registry = entity_registry.async_get(hass)
    devices = device_registry.async_get(hass)
    all_entries = list(registry.entities.values())
    assert len(all_entries) == 2
    assert all_entries[0].entity_id == "cover.wevolor_all_blinds"
    assert all_entries[1].entity_id == "button.wevolor_all_blinds_to_favorite_position"
    all_devices = list(devices.devices.values())
    assert len(all_devices) == 1
    assert all_devices[0].name == "Wevolor all_blinds"


async def test_experimental_setup_adds_calibration_entities(hass):
    """Experimental positioning should expose calibration controls."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
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
        },
        options={
            OPTION_EXPERIMENTAL_POSITIONING: True,
            OPTION_FULL_TRAVEL_TIME_SECS: 10.0,
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = entity_registry.async_get(hass)
    devices = device_registry.async_get(hass)
    all_entries = list(registry.entities.values())
    entity_ids = {entry.entity_id for entry in all_entries}
    assert "cover.wevolor_all_blinds" in entity_ids
    assert "button.wevolor_all_blinds_to_favorite_position" in entity_ids
    assert "button.wevolor_all_blinds_start_calibration" in entity_ids
    assert "number.wevolor_all_blinds_observed_percent_open" in entity_ids
    assert len(list(devices.devices.values())) == 1
