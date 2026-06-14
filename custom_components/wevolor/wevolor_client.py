"""Client wrapper around the pywevolor Wevolor client.

Wraps every command method with three layers of behaviour:

- **Logging**: Home Assistant's logger receives, at DEBUG level, the URL,
  channels, HTTP status, elapsed time, and any exception (at ERROR).
- **Serialization**: A per-host ``asyncio.Lock`` prevents concurrent HTTP
  requests to the same relay.
- **STOP retry**: ``stop_blinds`` retries once after 250 ms on non-200 to
  reduce the chance of a motor running to its limit.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from pywevolor import Wevolor

_LOGGER = logging.getLogger(__name__)


class WevolorClient:
    """Proxy around :class:`pywevolor.Wevolor` with logging, serialization, and STOP retry.

    Every command method delegates to the underlying ``Wevolor`` instance.
    Before and after the call it records the endpoint URL, channels, HTTP
    status, elapsed time, and any exception — all at a log level that matches
    the rest of the integration (``custom_components.wevolor.*`` at DEBUG).
    """

    # Locks keyed by relay host so that all WevolorClient instances that
    # point at the same IP share a single asyncio.Lock.  Locks are created
    # inside HA's event loop (integration setup runs there), so there is no
    # risk of binding to a stale loop.
    _locks_by_host: dict[str, asyncio.Lock] = {}

    def __init__(self, host: str) -> None:
        """Create the proxy and an underlying Wevolor client for *host*."""
        self._host = host
        self._client = Wevolor(host=host)
        # Get or create the host-keyed lock so all instances pointing at the
        # same relay IP share serialization.
        if host not in WevolorClient._locks_by_host:
            WevolorClient._locks_by_host[host] = asyncio.Lock()
        self._lock = WevolorClient._locks_by_host[host]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _url_for(self, path: str) -> str:
        """Return the full URL that pywevolor will hit."""
        return f"http://{self._host}/{path}"

    async def _logged_command(
        self, method_name: str, channels: list[int], action: str
    ) -> bool:
        """Call *method_name* on the underlying client and log the outcome."""
        async with self._lock:
            _LOGGER.debug(
                "Wevolor HTTP request: %s channels=%s url=%s",
                action,
                channels,
                self._url_for(
                    "_command?action=%s&groups=%d"
                    % (action, sum(2 ** (i - 1) for i in channels))
                ),
            )
            t_start = time.monotonic()
            try:
                result: bool = await getattr(self._client, method_name)(channels)
                elapsed = time.monotonic() - t_start
                # pywevolor returns True on HTTP 200, False otherwise (including
                # exceptions).  A False result means the relay returned a non-200
                # status or raised ClientError silently — we surface that here.
                if result:
                    _LOGGER.debug(
                        "Wevolor HTTP response: %s channels=%s status=200 elapsed=%.3fs",
                        action,
                        channels,
                        elapsed,
                    )
                else:
                    _LOGGER.warning(
                        "Wevolor HTTP response: %s channels=%s status=non-200 or network-error elapsed=%.3fs",
                        action,
                        channels,
                        elapsed,
                    )
                return result
            except Exception:
                elapsed = time.monotonic() - t_start
                _LOGGER.error(
                    "Wevolor HTTP exception: %s channels=%s elapsed=%.3fs",
                    action,
                    channels,
                    elapsed,
                    exc_info=True,
                )
                return False

    # ------------------------------------------------------------------
    # Status (not a blind command — keep simple logging)
    # ------------------------------------------------------------------

    async def get_status(self) -> Any:
        """Proxy get_status with basic debug logging."""
        async with self._lock:
            url = self._url_for("_status")
            _LOGGER.debug("Wevolor HTTP request: get_status url=%s", url)
            t_start = time.monotonic()
            try:
                result = await self._client.get_status()
                elapsed = time.monotonic() - t_start
                if result is not None:
                    _LOGGER.debug(
                        "Wevolor HTTP response: get_status status=200 elapsed=%.3fs",
                        elapsed,
                    )
                else:
                    _LOGGER.warning(
                        "Wevolor HTTP response: get_status status=non-200 or network-error elapsed=%.3fs",
                        elapsed,
                    )
                return result
            except Exception:
                elapsed = time.monotonic() - t_start
                _LOGGER.error(
                    "Wevolor HTTP exception: get_status elapsed=%.3fs",
                    elapsed,
                    exc_info=True,
                )
                return None

    # ------------------------------------------------------------------
    # Multi-channel command methods (called by cover.py / button.py)
    # ------------------------------------------------------------------

    async def open_blinds(self, channels: list[int]) -> bool:
        """Open blinds on *channels*."""
        return await self._logged_command("open_blinds", channels, "open")

    async def close_blinds(self, channels: list[int]) -> bool:
        """Close blinds on *channels*."""
        return await self._logged_command("close_blinds", channels, "close")

    async def stop_blinds(self, channels: list[int]) -> bool:
        """Stop blinds on *channels*.

        If the first attempt returns False (non-200 or network error), waits
        250 ms and makes exactly one retry.  The lock inside ``_logged_command``
        is released between the two calls, so other commands can slip through
        during the gap — that is intentional.
        """
        result = await self._logged_command("stop_blinds", channels, "stop")
        if not result:
            _LOGGER.warning(
                "Wevolor stop returned non-200; retrying in 250ms (channels=%s)",
                channels,
            )
            await asyncio.sleep(0.25)
            result = await self._logged_command("stop_blinds", channels, "stop")
            if not result:
                _LOGGER.error(
                    "Wevolor stop retry failed (channels=%s) — motor may run to limit",
                    channels,
                )
        return result

    async def favorite_blinds(self, channels: list[int]) -> bool:
        """Set blinds on *channels* to favorite position."""
        return await self._logged_command("favorite_blinds", channels, "favorite")

    async def open_blinds_tilt(self, channels: list[int]) -> bool:
        """Open tilt on *channels*."""
        return await self._logged_command("open_blinds_tilt", channels, "tiltopen")

    async def close_blinds_tilt(self, channels: list[int]) -> bool:
        """Close tilt on *channels*."""
        return await self._logged_command("close_blinds_tilt", channels, "tiltclose")

    async def stop_blinds_tilt(self, channels: list[int]) -> bool:
        """Stop tilt on *channels*."""
        # pywevolor delegates stop_blinds_tilt -> stop_blinds internally; we
        # do the same so the action label reflects what the relay sees.
        return await self._logged_command("stop_blinds_tilt", channels, "stop")

