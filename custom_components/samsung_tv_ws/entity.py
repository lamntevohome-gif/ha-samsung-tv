"""Shared base entity."""
from __future__ import annotations

import asyncio

from homeassistant.const import CONF_MAC
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo, format_mac
from homeassistant.helpers.entity import Entity

from . import SamsungTVConfigEntry
from .api import SamsungTVAuthError, SamsungTVError, send_magic_packet
from .const import CONF_MODEL, DOMAIN


class SamsungTVEntity(Entity):
    _attr_has_entity_name = True

    def __init__(self, entry: SamsungTVConfigEntry) -> None:
        self._entry = entry
        self._client = entry.runtime_data.client
        self._st = entry.runtime_data.smartthings
        self._mac: str | None = entry.options.get(CONF_MAC) or entry.data.get(CONF_MAC)
        self._uid = entry.unique_id or entry.entry_id
        connections = {(CONNECTION_NETWORK_MAC, format_mac(self._mac))} if self._mac else set()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._uid)},
            connections=connections,
            name=entry.title,
            manufacturer="Samsung",
            model=entry.data.get(CONF_MODEL),
        )

    async def _async_send_keys(self, keys: list[str], delay: float = 0.4) -> None:
        try:
            for i, key in enumerate(keys):
                if i:
                    await asyncio.sleep(delay)
                await self._client.send_key(key)
        except SamsungTVAuthError as err:
            raise HomeAssistantError("TV từ chối kết nối – hãy bấm Allow trên TV") from err
        except SamsungTVError as err:
            raise HomeAssistantError(f"Không gửi được lệnh tới TV: {err}") from err

    async def _async_power_on(self) -> None:
        if await self._client.power_state() == "standby":
            try:
                await self._client.send_key("KEY_POWER")
                return
            except SamsungTVError:
                pass
        if self._mac:
            await self.hass.async_add_executor_job(send_magic_packet, self._mac)
        if self._st:
            try:
                await self._st.switch_on()
            except SamsungTVError:
                pass

    async def _async_power_off(self) -> None:
        await self._async_send_keys(["KEY_POWER"])
        await self._client.close()
