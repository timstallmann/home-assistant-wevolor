"""Tests for config and options flows."""

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.wevolor.const import (
    DEFAULT_EXPERIMENTAL_POSITIONING,
    DOMAIN,
    OPTION_EXPERIMENTAL_POSITIONING,
    OPTION_FULL_TRAVEL_TIME_SECS,
)


async def test_options_flow_defaults(hass) -> None:
    """Test default options flow values."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    assert result["step_id"] == "init"
    schema = result["data_schema"]
    values = schema({})
    assert values[OPTION_EXPERIMENTAL_POSITIONING] is DEFAULT_EXPERIMENTAL_POSITIONING
    assert OPTION_FULL_TRAVEL_TIME_SECS not in values


async def test_options_flow_enables_calibration(hass) -> None:
    """Test enabling experimental positioning prompts for calibration."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        entry.entry_id,
        data={OPTION_EXPERIMENTAL_POSITIONING: True},
    )

    assert result["type"] == "form"
    values = result["data_schema"](
        {
            OPTION_EXPERIMENTAL_POSITIONING: True,
            OPTION_FULL_TRAVEL_TIME_SECS: 10.0,
        }
    )
    assert values[OPTION_EXPERIMENTAL_POSITIONING] is True
    assert values[OPTION_FULL_TRAVEL_TIME_SECS] == 10.0


async def test_options_flow_saves_calibration(hass) -> None:
    """Test saving experimental positioning options."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    await hass.config_entries.options.async_init(
        entry.entry_id,
        data={OPTION_EXPERIMENTAL_POSITIONING: True},
    )
    result = await hass.config_entries.options.async_configure(
        entry.entry_id,
        {
            OPTION_EXPERIMENTAL_POSITIONING: True,
            OPTION_FULL_TRAVEL_TIME_SECS: 10.0,
        },
    )

    assert result["type"] == "create_entry"
    assert result["data"] == {
        OPTION_EXPERIMENTAL_POSITIONING: True,
        OPTION_FULL_TRAVEL_TIME_SECS: 10.0,
    }


async def test_options_flow_shows_calibration_field_when_enabled(hass) -> None:
    """Test calibration field appears once experimental mode is saved."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            OPTION_EXPERIMENTAL_POSITIONING: True,
            OPTION_FULL_TRAVEL_TIME_SECS: 12.5,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == "form"
    schema = result["data_schema"]
    values = schema(
        {
            OPTION_EXPERIMENTAL_POSITIONING: True,
            OPTION_FULL_TRAVEL_TIME_SECS: 12.5,
        }
    )
    assert values[OPTION_EXPERIMENTAL_POSITIONING] is True
    assert values[OPTION_FULL_TRAVEL_TIME_SECS] == 12.5
