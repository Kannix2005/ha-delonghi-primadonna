"""Delonghi integration"""

from __future__ import annotations

import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import BEVERAGE_SERVICE_NAME, DOMAIN
from .device import BeverageEntityFeature, DelongiPrimadonna

# Periodic status poll interval in seconds.
# The machine sends BLE notifications every ~6s, but we additionally
# poll the DEBUG command to bridge gaps when notifications are missed.
POLL_INTERVAL_SECONDS = 5
RECONNECT_INTERVAL_SECONDS = 30

PLATFORMS: list[str] = [
    Platform.IMAGE,
    Platform.BUTTON,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SELECT,
    Platform.SWITCH,
    Platform.TEXT,
    Platform.DEVICE_TRACKER,
]

__all__ = ['async_setup_entry', 'async_unload_entry', 'BeverageEntityFeature']

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry"""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    delonghi_device = DelongiPrimadonna(entry.data, hass)
    hass.data[DOMAIN][entry.unique_id] = delonghi_device
    _LOGGER.debug('Device id %s', entry.unique_id)
    _LOGGER.debug("Device data %s", entry.data)
    hass.async_create_task(delonghi_device.get_device_name())
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ── Periodic status polling ──────────────────────────────────
    _poll_running = False
    _last_reconnect_attempt = 0.0

    async def _periodic_status_poll(now) -> None:
        """Send DEBUG command to trigger a status response.

        Polls every POLL_INTERVAL_SECONDS when connected.
        Attempts reconnect at most every RECONNECT_INTERVAL_SECONDS
        when disconnected to avoid BLE spam.
        """
        nonlocal _poll_running, _last_reconnect_attempt
        import time

        if _poll_running:
            return  # Previous poll still running, skip
        _poll_running = True
        try:
            if delonghi_device.connected:
                await delonghi_device.poll_status()
            else:
                # Throttle reconnect attempts
                now_ts = time.monotonic()
                if (now_ts - _last_reconnect_attempt
                        >= RECONNECT_INTERVAL_SECONDS):
                    _last_reconnect_attempt = now_ts
                    _LOGGER.debug('Attempting reconnect to %s',
                                  delonghi_device.mac)
                    await delonghi_device.get_device_name()
        except Exception:  # noqa: BLE001
            _LOGGER.debug('Periodic poll failed, will retry next cycle')
            # Push state on failure (connection may have changed)
            async_dispatcher_send(
                hass, delonghi_device.signal_state_updated
            )
        finally:
            _poll_running = False

    unsub_poll = async_track_time_interval(
        hass, _periodic_status_poll, timedelta(seconds=POLL_INTERVAL_SECONDS)
    )
    delonghi_device._poll_unsub = unsub_poll
    # ─────────────────────────────────────────────────────────────

    async def make_beverage(call: ServiceCall) -> None:
        _LOGGER.debug('Make beverage %s', call.data)
        await delonghi_device.beverage_start(call.data['beverage'])

    hass.services.async_register(
        DOMAIN,
        BEVERAGE_SERVICE_NAME,
        make_beverage,
        schema=vol.Schema(
            {
                vol.Required('beverage'): vol.Coerce(str),
                vol.Optional('entity_id'): vol.Coerce(str),
                vol.Optional('device_id'): vol.Coerce(str),
            }
        ),
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )
    if unload_ok:
        device = hass.data[DOMAIN][entry.unique_id]
        # Cancel periodic poll before disconnect
        if device._poll_unsub:
            device._poll_unsub()
            device._poll_unsub = None
        await device.disconnect()
        hass.data[DOMAIN].pop(entry.unique_id)
    _LOGGER.debug('Unload %s', entry.unique_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the Delonghi entry."""

    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
