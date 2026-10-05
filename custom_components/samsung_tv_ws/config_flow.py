"""Config flow: enter IP -> press Allow on TV -> done."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SamsungTVAuthError, SamsungTVClient, SamsungTVConnectionError
from .const import (
    CONF_HDMI_COUNT,
    CONF_MODEL,
    CONF_ST_DEVICE_ID,
    CONF_ST_TOKEN,
    CONF_TOKEN,
    DEFAULT_HDMI_COUNT,
    DOMAIN,
)


class SamsungTVConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._host: str = ""
        self._name: str = ""
        self._mac: str | None = None
        self._model: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            client = SamsungTVClient(async_get_clientsession(self.hass), host)
            try:
                info = await client.device_info()
            except SamsungTVConnectionError:
                errors["base"] = "cannot_connect"
            else:
                device = info.get("device", {})
                await self.async_set_unique_id(device.get("duid") or device.get("id") or host)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                self._host = host
                self._name = user_input.get(CONF_NAME) or device.get("name") or "Samsung TV"
                self._mac = user_input.get(CONF_MAC) or device.get("wifiMac")
                self._model = device.get("modelName")
                return await self.async_step_pair()

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Optional(CONF_NAME): str,
                vol.Optional(CONF_MAC): str,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input or {}),
            errors=errors,
        )

    async def async_step_pair(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            client = SamsungTVClient(async_get_clientsession(self.hass), self._host)
            try:
                token = await client.pair(timeout=30)
            except SamsungTVAuthError:
                errors["base"] = "auth_denied"
            except SamsungTVConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=self._name,
                    data={
                        CONF_HOST: self._host,
                        CONF_NAME: self._name,
                        CONF_MAC: self._mac,
                        CONF_MODEL: self._model,
                        CONF_TOKEN: token,
                    },
                )
            finally:
                await client.close()

        return self.async_show_form(
            step_id="pair",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders={"host": self._host},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SamsungTVOptionsFlow()


class SamsungTVOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        opts = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_HDMI_COUNT, default=opts.get(CONF_HDMI_COUNT, DEFAULT_HDMI_COUNT)
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=4)),
                vol.Optional(
                    CONF_MAC,
                    description={
                        "suggested_value": opts.get(CONF_MAC) or self.config_entry.data.get(CONF_MAC)
                    },
                ): str,
                vol.Optional(
                    CONF_ST_TOKEN, description={"suggested_value": opts.get(CONF_ST_TOKEN)}
                ): str,
                vol.Optional(
                    CONF_ST_DEVICE_ID, description={"suggested_value": opts.get(CONF_ST_DEVICE_ID)}
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
