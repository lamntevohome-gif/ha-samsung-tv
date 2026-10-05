"""Media player entity with HDMI source selection."""
from __future__ import annotations

from datetime import timedelta
import logging
import time

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature as F,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SamsungTVConfigEntry
from .api import SamsungTVError
from .const import CONF_HDMI_COUNT, DEFAULT_HDMI_COUNT, SOURCE_KEYS, SOURCE_TV
from .entity import SamsungTVEntity

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=10)
OFF_GRACE = 20  # seconds: TV still answers REST shortly after power off


def _normalize_source(raw: str) -> str:
    up = raw.upper().replace(" ", "")
    if up.startswith("HDMI"):
        return up
    if up in ("DTV", "DIGITALTV", "TV", "ATV"):
        return SOURCE_TV
    return raw


async def async_setup_entry(
    hass: HomeAssistant, entry: SamsungTVConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([SamsungTVMediaPlayer(entry)], update_before_add=True)


class SamsungTVMediaPlayer(SamsungTVEntity, MediaPlayerEntity):
    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.TV

    def __init__(self, entry: SamsungTVConfigEntry) -> None:
        super().__init__(entry)
        self._attr_unique_id = self._uid
        hdmi = entry.options.get(CONF_HDMI_COUNT, DEFAULT_HDMI_COUNT)
        self._attr_source_list = [SOURCE_TV] + [f"HDMI{i}" for i in range(1, hdmi + 1)]
        self._attr_source = None
        self._attr_state = MediaPlayerState.OFF
        self._attr_is_volume_muted = False
        self._off_until = 0.0

    @property
    def supported_features(self) -> F:
        feats = (
            F.TURN_OFF | F.VOLUME_STEP | F.VOLUME_MUTE | F.SELECT_SOURCE
            | F.PLAY | F.PAUSE | F.STOP | F.NEXT_TRACK | F.PREVIOUS_TRACK
        )
        if self._mac or self._st:
            feats |= F.TURN_ON
        return feats

    async def async_update(self) -> None:
        if time.monotonic() < self._off_until:
            self._attr_state = MediaPlayerState.OFF
            return
        on = await self._client.power_state() == "on"
        self._attr_state = MediaPlayerState.ON if on else MediaPlayerState.OFF
        if not on:
            await self._client.close()
            return
        if self._st:
            try:
                raw = await self._st.get_input_source()
            except SamsungTVError as err:
                _LOGGER.debug("SmartThings status failed: %s", err)
            else:
                if raw:
                    src = _normalize_source(raw)
                    if src not in self._attr_source_list:
                        self._attr_source_list = [*self._attr_source_list, src]
                    self._attr_source = src

    # ---- power ----
    async def async_turn_on(self) -> None:
        self._off_until = 0
        await self._async_power_on()

    async def async_turn_off(self) -> None:
        await self._async_power_off()
        self._off_until = time.monotonic() + OFF_GRACE
        self._attr_state = MediaPlayerState.OFF
        self.async_write_ha_state()

    # ---- source ----
    async def async_select_source(self, source: str) -> None:
        if self._st:
            try:
                await self._st.set_input_source(source if source != SOURCE_TV else "digitalTv")
                self._attr_source = source
                self.async_write_ha_state()
                return
            except SamsungTVError as err:
                _LOGGER.warning("SmartThings setInputSource failed (%s), fallback to keys", err)
        key = SOURCE_KEYS.get(source)
        if key is None:
            raise HomeAssistantError(f"Nguồn không hỗ trợ: {source}")
        await self._async_send_keys([key])
        self._attr_source = source
        self.async_write_ha_state()

    # ---- volume / media ----
    async def async_volume_up(self) -> None:
        await self._async_send_keys(["KEY_VOLUP"])

    async def async_volume_down(self) -> None:
        await self._async_send_keys(["KEY_VOLDOWN"])

    async def async_mute_volume(self, mute: bool) -> None:
        await self._async_send_keys(["KEY_MUTE"])
        self._attr_is_volume_muted = mute
        self.async_write_ha_state()

    async def async_media_play(self) -> None:
        await self._async_send_keys(["KEY_PLAY"])

    async def async_media_pause(self) -> None:
        await self._async_send_keys(["KEY_PAUSE"])

    async def async_media_stop(self) -> None:
        await self._async_send_keys(["KEY_STOP"])

    async def async_media_next_track(self) -> None:
        await self._async_send_keys(["KEY_CHUP"])

    async def async_media_previous_track(self) -> None:
        await self._async_send_keys(["KEY_CHDOWN"])
