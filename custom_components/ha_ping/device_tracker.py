"""Tracks devices by sending a ICMP echo request (ping)."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, CONF_HOST, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.device_tracker import (
    ScannerEntity,
    SourceType,
)

from .const import (
    DOMAIN,
    DEVICE_TRACKER,
    IS_ALIVE,
    ATTR_ROUND_TRIP_TIME_AVG,
    ATTR_ROUND_TRIP_TIME_MAX,
    ATTR_ROUND_TRIP_TIME_MDEV,
    ATTR_ROUND_TRIP_TIME_MIN
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    config = entry.data

    if DEVICE_TRACKER not in config[CONF_PLATFORM]:
        return

    name = config[CONF_NAME]
    host = config[CONF_HOST]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    unique_id = f"{entry.entry_id}-device_tracker"

    async_add_entities([PingTracker(coordinator, unique_id, name, host)])


class PingTracker(CoordinatorEntity, ScannerEntity):
    """Representation of network device."""

    def __init__(self, coordinator, unique_id, name, host) -> None:
        """Initialize the tracked device."""
        super().__init__(coordinator)
        self._unique_id = unique_id
        self._name = name
        self._host = host

    @property
    def is_connected(self) -> bool:
        """Return true if the device is connected to the network."""
        return self.coordinator.data[IS_ALIVE]

    @property
    def source_type(self) -> SourceType:
        """Return the source type of the client."""
        return SourceType.ROUTER

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return a unique identifier for this device."""
        return self._unique_id

    @property
    def hostname(self) -> str | None:
        """Return hostname of the device."""
        return self._host

    @property
    def available(self) -> bool:
        """Return if controller is available."""
        return self.coordinator.data is not None

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        if self.coordinator.data is None or not self.coordinator.data[IS_ALIVE]:
            return None
        return {
            ATTR_ROUND_TRIP_TIME_AVG: self.coordinator.data[ATTR_ROUND_TRIP_TIME_AVG],
            ATTR_ROUND_TRIP_TIME_MAX: self.coordinator.data[ATTR_ROUND_TRIP_TIME_MAX],
            ATTR_ROUND_TRIP_TIME_MDEV: self.coordinator.data[ATTR_ROUND_TRIP_TIME_MDEV],
            ATTR_ROUND_TRIP_TIME_MIN: self.coordinator.data[ATTR_ROUND_TRIP_TIME_MDEV],
        }
