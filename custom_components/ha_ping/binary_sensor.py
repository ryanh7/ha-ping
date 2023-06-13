"""Tracks the latency of a host by sending ICMP echo requests (ping)."""
from __future__ import annotations

import logging
from typing import Any


from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_NAME, CONF_PLATFORM
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    BINARY_SENSOR,
    IS_ALIVE,
    ATTR_ROUND_TRIP_TIME_AVG,
    ATTR_ROUND_TRIP_TIME_MAX,
    ATTR_ROUND_TRIP_TIME_MIN
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    config = entry.data

    if BINARY_SENSOR not in config[CONF_PLATFORM]:
        return

    name = config[CONF_NAME]
    coordinator = hass.data[DOMAIN][entry.entry_id]
    unique_id = f"{entry.entry_id}-binary_sensor"

    async_add_entities([PingBinarySensor(coordinator, unique_id, name)])


class PingBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Ping Binary sensor."""

    _attr_translation_key = "ping"

    def __init__(self, coordinator, unique_id, name) -> None:
        """Initialize the Ping Binary sensor."""
        super().__init__(coordinator)
        self._unique_id = unique_id
        self._name = name

    @property
    def name(self) -> str:
        """Return the name of the device."""
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def available(self) -> bool:
        """Return if we have done the first ping."""
        return self.coordinator.data is not None

    @property
    def device_class(self) -> BinarySensorDeviceClass:
        """Return the class of this sensor."""
        return BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.coordinator.data[IS_ALIVE]

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the ICMP checo request."""
        if self.coordinator.data is None or not self.coordinator.data[IS_ALIVE]:
            return None
        return {
            ATTR_ROUND_TRIP_TIME_AVG: self.coordinator.data[ATTR_ROUND_TRIP_TIME_AVG],
            ATTR_ROUND_TRIP_TIME_MAX: self.coordinator.data[ATTR_ROUND_TRIP_TIME_MAX],
            ATTR_ROUND_TRIP_TIME_MIN: self.coordinator.data[ATTR_ROUND_TRIP_TIME_MIN],
        }
