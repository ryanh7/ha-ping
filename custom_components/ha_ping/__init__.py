"""The ping component."""
from __future__ import annotations

import logging
import asyncio
import async_timeout
import re

from datetime import timedelta
from contextlib import suppress
from icmplib import SocketPermissionError, NameLookupError, async_ping, ping as icmp_ping

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.const import Platform, CONF_HOST, CONF_SCAN_INTERVAL

from .const import (
    DOMAIN,
    PING_PRIVS,
    ICMP_TIMEOUT,
    PING_TIMEOUT,
    IS_ALIVE,
    ATTR_ROUND_TRIP_TIME_AVG,
    ATTR_ROUND_TRIP_TIME_MAX,
    ATTR_ROUND_TRIP_TIME_MIN
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER]

PING_MATCHER = re.compile(
    r"(?P<min>\d+.\d+)\/(?P<avg>\d+.\d+)\/(?P<max>\d+.\d+)\/(?P<mdev>\d+.\d+)"
)

PING_MATCHER_BUSYBOX = re.compile(
    r"(?P<min>\d+.\d+)\/(?P<avg>\d+.\d+)\/(?P<max>\d+.\d+)"
)


class PingData(DataUpdateCoordinator):
    """The class for handling the data retrieval."""

    def __init__(self, hass, host, interval):
        """Initialize the data object."""
        interval = int(interval)
        super().__init__(
            hass, _LOGGER, name=DOMAIN, update_interval=timedelta(
                seconds=interval)
        )
        self._ip_address = host
        self._count = min(interval - 1, 5) if interval > 1 else 1


class PingDataICMPLib(PingData):
    """The Class for handling the data retrieval using icmplib."""

    def __init__(
        self, hass: HomeAssistant, host: str, interval: int, privileged: bool | None
    ) -> None:
        """Initialize the data object."""
        super().__init__(hass, host, interval)
        self._privileged = privileged

    async def _async_update_data(self):
        """Retrieve the latest details from the host."""
        _LOGGER.debug("ping address: %s", self._ip_address)
        try:
            data = await async_ping(
                self._ip_address,
                count=self._count,
                timeout=ICMP_TIMEOUT,
                privileged=self._privileged,
            )
        except NameLookupError:
            return {IS_ALIVE: False}

        if not data.is_alive:
            return {IS_ALIVE: False}

        return {
            ATTR_ROUND_TRIP_TIME_MIN: data.min_rtt,
            ATTR_ROUND_TRIP_TIME_MAX: data.max_rtt,
            ATTR_ROUND_TRIP_TIME_AVG: data.avg_rtt,
            IS_ALIVE: data.is_alive
        }


class PingDataSubProcess(PingData):
    """The Class for handling the data retrieval using the ping binary."""

    def __init__(
        self, hass: HomeAssistant, host: str, interval: int, privileged: bool | None
    ) -> None:
        """Initialize the data object."""
        super().__init__(hass, host, interval)
        self._ping_cmd = [
            "ping",
            "-n",
            "-q",
            "-c",
            str(self._count),
            "-W1",
            self._ip_address,
        ]

    async def _async_update_data(self):
        """Send ICMP echo request and return details if success."""
        pinger = await asyncio.create_subprocess_exec(
            *self._ping_cmd,
            stdin=None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            close_fds=False,  # required for posix_spawn
        )
        try:
            async with async_timeout.timeout(self._count + PING_TIMEOUT):
                out_data, out_error = await pinger.communicate()

            if out_data:
                _LOGGER.debug(
                    "Output of command: `%s`, return code: %s:\n%s",
                    " ".join(self._ping_cmd),
                    pinger.returncode,
                    out_data,
                )
            if out_error:
                _LOGGER.debug(
                    "Error of command: `%s`, return code: %s:\n%s",
                    " ".join(self._ping_cmd),
                    pinger.returncode,
                    out_error,
                )

            if pinger.returncode > 1:
                # returncode of 1 means the host is unreachable
                _LOGGER.exception(
                    "Error running command: `%s`, return code: %s",
                    " ".join(self._ping_cmd),
                    pinger.returncode,
                )

            if "max/" not in str(out_data):
                match = PING_MATCHER_BUSYBOX.search(
                    str(out_data).rsplit("\n", maxsplit=1)[-1]
                )
                rtt_min, rtt_avg, rtt_max = match.groups()
                return {
                    IS_ALIVE: True,
                    ATTR_ROUND_TRIP_TIME_MIN: rtt_min,
                    ATTR_ROUND_TRIP_TIME_AVG: rtt_avg,
                    ATTR_ROUND_TRIP_TIME_MAX: rtt_max,
                }
            match = PING_MATCHER.search(
                str(out_data).rsplit("\n", maxsplit=1)[-1])
            rtt_min, rtt_avg, rtt_max, rtt_mdev = match.groups()
            return {
                IS_ALIVE: True,
                ATTR_ROUND_TRIP_TIME_MIN: rtt_min,
                ATTR_ROUND_TRIP_TIME_AVG: rtt_avg,
                ATTR_ROUND_TRIP_TIME_MAX: rtt_max,
            }
        except asyncio.TimeoutError:
            _LOGGER.exception(
                "Timed out running command: `%s`, after: %ss",
                self._ping_cmd,
                self._count + PING_TIMEOUT,
            )
            if pinger:
                with suppress(TypeError):
                    await pinger.kill()
                del pinger

            return {IS_ALIVE: False}
        except AttributeError:
            return {IS_ALIVE: False}


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the template integration."""
    hass.data[DOMAIN] = {
        PING_PRIVS: await hass.async_add_executor_job(_can_use_icmp_lib_with_privilege),
    }
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    config = entry.data
    host = config[CONF_HOST]
    interval = config[CONF_SCAN_INTERVAL]

    privileged: bool | None = hass.data[DOMAIN][PING_PRIVS]
    coordinator: type[PingDataSubProcess | PingDataICMPLib]
    if privileged is None:
        coordinator = PingDataSubProcess
    else:
        coordinator = PingDataICMPLib
    data = coordinator(hass, host, interval, privileged)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _can_use_icmp_lib_with_privilege() -> None | bool:
    """Verify we can create a raw socket."""
    try:
        icmp_ping("127.0.0.1", count=0, timeout=0, privileged=True)
    except SocketPermissionError:
        try:
            icmp_ping("127.0.0.1", count=0, timeout=0, privileged=False)
        except SocketPermissionError:
            _LOGGER.debug(
                "Cannot use icmplib because privileges are insufficient to create the"
                " socket"
            )
            return None

        _LOGGER.debug("Using icmplib in privileged=False mode")
        return False

    _LOGGER.debug("Using icmplib in privileged=True mode")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        if len(hass.config_entries.async_entries(DOMAIN)) == 0:
            hass.data.pop(DOMAIN)

    return unload_ok
