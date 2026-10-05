"""Remote entity: send any KEY_* code (remote.send_command)."""
from __future__ import annotations

from collections.abc import Iterable
from datetime import timedelta
from typing import Any

from homeassistant.components.remote import (
    ATTR_DELAY_SECS,
    ATTR_HOLD_SECS,
    ATTR_NUM_REPEATS,
    RemoteEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SamsungTVConfigEntry
from .entity import SamsungTVEntity

SCAN_INTERVAL = timedelta(seconds=10)


async def async_setup_entry(
    hass: HomeAssistant, entry: SamsungTVConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([SamsungTVRemote(entry)], update_before_add=True)


class SamsungTVRemote(SamsungTVEntity, RemoteEntity):
    _attr_name = "Remote"

    def __init__(self, entry: SamsungTVConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = f"{self._uid}_remote"
        self._attr_is_on = False

    async def async_update(self) -> None:
        self._attr_is_on = await self._client.power_state() == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_power_on()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_power_off()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        repeats = kwargs.get(ATTR_NUM_REPEATS, 1)
        delay = kwargs.get(ATTR_DELAY_SECS, 0.4)
        hold = kwargs.get(ATTR_HOLD_SECS, 0)
        keys = [c.strip().upper() for c in command]
        for _ in range(repeats):
            if hold:
                for key in keys:
                    await self._client.hold_key(key, hold)
            else:
                await self._async_send_keys(keys, delay)
