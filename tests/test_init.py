"""Test sensor for simple integration."""

from pytest_homeassistant_custom_component.common import MockConfigEntry

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
