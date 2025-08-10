# Home Assistant integration for Wevolor
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

[Levolor](https://levolor.com) is an American manufacturer of window shades and coverings. Motorized Levolor blinds can be controlled via the [Levolor Premium 6-Channel Remote](https://www.levolor.com/premium-6-channel-remote.html), which syncs via Bluetooth with a smartphone app but does not offer any remote control over Wi-Fi.

[Wevolor](https://wevolor.com) is a Wi-Fi-enabled IoT device, built by Roger Hoggarth, which syncs with the Levolor 6-channel remote to allow linking Levolor blinds to a home automation system. The Wevolor firmware can be downloaded for free and installed on a compatible Arduino device, or Wevolor devices can be purchased from the Wevolor website.

This integration supports Wevolor [version 5.4](https://wevolor.com/instructions/wevolor_instructions_5_4.html) and greater, using the locally available API. Your Wevolor device will need to have a static IP address on the local network since Wevolor does not support any sort of auto-discovery.

## Configuration

```
  host:
    description: The IP address of the Wevolor device on the local network.
  name:
    description: Name for this channel grouping.
  channel_1 ... channel_6:
    description:  Whether or not channel 1 - 6 should be included in commands sent to this group.
  support_tilt:
    description: Set true if any of the Levolor blinds you are controlling support tilt, false otherwise.
```

## Cover

After setup, a new cover entity will appear in Home Assistant, controlling the various channels you specified.

For more information on working with shades in Home Assistant, see the [Covers component](/integrations/cover/).

Available services: `cover.open_cover`, `cover.close_cover`, `cover.stop_cover`. When tilt is enabled, `cover.open_cover_tilt`, `cover.close_cover_tilt` and `cover.stop_cover_tilt` are also available.

## Button

Favorite position for shades is exposed via a button, `button.wevolor_channel_1_favorite_position`.

# Local development

Run `pip install -r requirements.test.txt` to install requirements. Run `pre-commit install` to setup pre commit.
Run `pytest --asyncio-mode-auto` to run a basic configuration test.
