"""Samsung TV WebSocket integration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SamsungTVClient
from .const import CONF_ST_DEVICE_ID, CONF_ST_TOKEN, CONF_TOKEN
from .smartthings import SmartThingsClient

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.REMOTE]


@dataclass
class SamsungTVData:
    client: SamsungTVClient
    smartthings: SmartThingsClient | None
    options: dict[str, Any] = field(default_factory=dict)


type SamsungTVConfigEntry = ConfigEntry[SamsungTVData]


async def async_setup_entry(hass: HomeAssistant, entry: SamsungTVConfigEntry) -> bool:
    session = async_get_clientsession(hass)

    @callback
    def _save_token(token: str) -> None:
        hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_TOKEN: token})

    client = SamsungTVClient(
        session, entry.data[CONF_HOST], token=entry.data.get(CONF_TOKEN), on_token=_save_token
    )

    st = None
    if entry.options.get(CONF_ST_TOKEN) and entry.options.get(CONF_ST_DEVICE_ID):
        st = SmartThingsClient(
            session, entry.options[CONF_ST_TOKEN].strip(), entry.options[CONF_ST_DEVICE_ID].strip()
        )

    entry.runtime_data = SamsungTVData(client, st, dict(entry.options))
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: SamsungTVConfigEntry) -> None:
    # Only reload when options change (token rotation updates entry.data too).
    if dict(entry.options) != entry.runtime_data.options:
        await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SamsungTVConfigEntry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok:
        await entry.runtime_data.client.close()
    return ok
