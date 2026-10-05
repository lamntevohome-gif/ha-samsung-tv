"""Optional SmartThings Cloud client – reliable input source read/write."""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .api import SamsungTVAuthError, SamsungTVConnectionError, SamsungTVError

ST_API = "https://api.smartthings.com/v1"


class SmartThingsClient:
    def __init__(self, session: aiohttp.ClientSession, token: str, device_id: str) -> None:
        self._session = session
        self._token = token
        self._device_id = device_id

    async def _request(self, method: str, path: str, body: Any = None) -> Any:
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            async with asyncio.timeout(10):
                async with self._session.request(
                    method, f"{ST_API}{path}", json=body, headers=headers
                ) as resp:
                    if resp.status in (401, 403):
                        raise SamsungTVAuthError("SmartThings token invalid/expired")
                    if resp.status >= 400:
                        raise SamsungTVError(f"SmartThings HTTP {resp.status}: {await resp.text()}")
                    return await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SamsungTVConnectionError(str(err)) from err

    async def _main_status(self) -> dict[str, Any]:
        data = await self._request("GET", f"/devices/{self._device_id}/status")
        return data.get("components", {}).get("main", {})

    async def get_input_source(self) -> str | None:
        main = await self._main_status()
        for cap in ("samsungvd.mediaInputSource", "mediaInputSource"):
            value = main.get(cap, {}).get("inputSource", {}).get("value")
            if value:
                return value
        return None

    async def _command(self, capability: str, command: str, args: list | None = None) -> None:
        cmd: dict[str, Any] = {"component": "main", "capability": capability, "command": command}
        if args:
            cmd["arguments"] = args
        await self._request(
            "POST", f"/devices/{self._device_id}/commands", {"commands": [cmd]}
        )

    async def set_input_source(self, source: str) -> None:
        try:
            await self._command("samsungvd.mediaInputSource", "setInputSource", [source])
        except SamsungTVAuthError:
            raise
        except SamsungTVError:
            await self._command("mediaInputSource", "setInputSource", [source])

    async def switch_on(self) -> None:
        await self._command("switch", "on")
