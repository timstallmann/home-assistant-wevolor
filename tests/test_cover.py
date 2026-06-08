"""Tests for experimental timed cover positioning."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from homeassistant.components.cover import CoverEntityFeature

from custom_components.wevolor.cover import MAX_POSITION, MIN_POSITION, WevolorShade


def _create_cover(
    hass,
    *,
    full_travel_time_secs: float = 10.0,
    treat_favorite_as_closed: bool = False,
) -> WevolorShade:
    """Create a cover entity with mocked runtime dependencies."""
    client = AsyncMock()
    cover = WevolorShade(
        client,
        host="192.168.1.1",
        channels=[1],
        name="office",
        experimental_positioning=True,
        full_travel_time_secs=full_travel_time_secs,
        treat_favorite_as_closed=treat_favorite_as_closed,
    )
    cover.entity_id = "cover.wevolor_office"
    cover.hass = hass
    cover.async_write_ha_state = Mock()
    return cover


async def test_experimental_cover_supports_set_position(hass) -> None:
    """Experimental positioning should expose set-position support."""
    cover = _create_cover(hass)

    assert cover.supported_features & CoverEntityFeature.SET_POSITION


async def test_set_cover_position_schedules_timed_stop(hass, monkeypatch) -> None:
    """Moving to an intermediate position should schedule a timed stop."""
    cover = _create_cover(hass)
    scheduled = {}

    monotonic = Mock(side_effect=[10.0, 10.0])
    monkeypatch.setattr("custom_components.wevolor.cover.time.monotonic", monotonic)

    def _fake_async_call_later(_hass, duration, callback):
        scheduled["duration"] = duration
        scheduled["callback"] = callback
        return lambda: scheduled.setdefault("cancelled", True)

    monkeypatch.setattr(
        "custom_components.wevolor.cover.async_call_later",
        _fake_async_call_later,
    )

    await cover.async_set_cover_position(position=50)

    assert scheduled["duration"] == 5.0
    cover._wevolor.close_blinds.assert_awaited_once_with([1])

    scheduled["callback"](None)
    await hass.async_block_till_done()

    cover._wevolor.stop_blinds.assert_awaited_once_with([1])
    assert cover.current_cover_position == 50


async def test_stop_cover_persists_partial_progress(hass, monkeypatch) -> None:
    """Stopping mid-travel should keep the estimated partial position."""
    cover = _create_cover(hass)

    monotonic = Mock(side_effect=[10.0, 12.0])
    monkeypatch.setattr("custom_components.wevolor.cover.time.monotonic", monotonic)
    monkeypatch.setattr(
        "custom_components.wevolor.cover.async_call_later",
        lambda _hass, _duration, _callback: (lambda: None),
    )

    await cover.async_close_cover()
    await cover.async_stop_cover()

    assert cover.current_cover_position == 80
    cover._wevolor.stop_blinds.assert_awaited_once_with([1])


async def test_full_close_snaps_to_zero(hass, monkeypatch) -> None:
    """A full close command should reset the implied position to zero."""
    cover = _create_cover(hass)
    scheduled = {}

    monotonic = Mock(side_effect=[5.0, 5.0])
    monkeypatch.setattr("custom_components.wevolor.cover.time.monotonic", monotonic)

    def _fake_async_call_later(_hass, duration, callback):
        scheduled["duration"] = duration
        scheduled["callback"] = callback
        return lambda: None

    monkeypatch.setattr(
        "custom_components.wevolor.cover.async_call_later",
        _fake_async_call_later,
    )

    await cover.async_close_cover()
    assert scheduled["duration"] == 10.0

    scheduled["callback"](None)
    await hass.async_block_till_done()

    assert cover.current_cover_position == MIN_POSITION
    cover._wevolor.stop_blinds.assert_not_awaited()


async def test_async_added_to_hass_restores_last_position(hass) -> None:
    """Restored state should seed the implied current position."""
    cover = _create_cover(hass)
    cover.async_get_last_state = AsyncMock(
        return_value=SimpleNamespace(attributes={"current_position": 37})
    )

    await cover.async_added_to_hass()

    assert cover.current_cover_position == 37


async def test_open_cover_snaps_back_to_full_open(hass, monkeypatch) -> None:
    """A full open command should reset the implied position to 100."""
    cover = _create_cover(hass)
    cover._current_position = 25
    scheduled = {}

    monotonic = Mock(side_effect=[2.0, 2.0])
    monkeypatch.setattr("custom_components.wevolor.cover.time.monotonic", monotonic)

    def _fake_async_call_later(_hass, duration, callback):
        scheduled["duration"] = duration
        scheduled["callback"] = callback
        return lambda: None

    monkeypatch.setattr(
        "custom_components.wevolor.cover.async_call_later",
        _fake_async_call_later,
    )

    await cover.async_open_cover()
    assert scheduled["duration"] == 7.5

    scheduled["callback"](None)
    await hass.async_block_till_done()

    assert cover.current_cover_position == MAX_POSITION
    cover._wevolor.stop_blinds.assert_not_awaited()


async def test_close_cover_dispatches_favorite_when_option_on(hass) -> None:
    """async_close_cover should call favorite_blinds when treat_favorite_as_closed is True."""
    cover = _create_cover(hass, treat_favorite_as_closed=True)

    await cover.async_close_cover()

    cover._wevolor.favorite_blinds.assert_awaited_once_with([1])
    cover._wevolor.close_blinds.assert_not_awaited()


async def test_close_cover_dispatches_normal_close_when_option_off(hass) -> None:
    """async_close_cover should call close_blinds when treat_favorite_as_closed is False."""
    cover = _create_cover(hass, treat_favorite_as_closed=False)

    await cover.async_close_cover()

    cover._wevolor.close_blinds.assert_awaited_once_with([1])
    cover._wevolor.favorite_blinds.assert_not_awaited()
