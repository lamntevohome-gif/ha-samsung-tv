"""Minimal async client for the Samsung Tizen TV WebSocket API (2016+).

Endpoints:
  REST  : http://<ip>:8001/api/v2/                      -> device info, PowerState
  WS    : wss://<ip>:8002/api/v2/channels/samsung.remote.control?name=<b64>&token=<t>
  Key   : {"method":"ms.remote.control","params":{"Cmd":"Click","DataOfCmd":"KEY_HDMI1",...}}
"""
from __future__ import annotations

import asyncio
import base64
from collections.abc import Callable
import json
import logging
import re
import socket
from typing import Any

import aiohttp

from .const import CLIENT_NAME, REST_PORT, WS_PORT

_LOGGER = logging.getLogger(__name__)


class SamsungTVError(Exception):
    """Generic error."""


class SamsungTVConnectionError(SamsungTVError):
    """TV unreachable."""


class SamsungTVAuthError(SamsungTVError):
    """TV refused the connection (pairing denied / timed out)."""


def send_magic_packet(mac: str, broadcast: str = "255.255.255.255", port: int = 9) -> None:
    """Send Wake-on-LAN packet (blocking, run in executor)."""
    clean = re.sub(r"[^0-9A-Fa-f]", "", mac)
    if len(clean) != 12:
        raise ValueError(f"Invalid MAC address: {mac}")
    packet = bytes.fromhex("FF" * 6 + clean * 16)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(packet, (broadcast, port))


class SamsungTVClient:
    """Persistent WebSocket connection to a Samsung TV."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        token: str | None = None,
        name: str = CLIENT_NAME,
        on_token: Callable[[str], None] | None = None,
    ) -> None:
        self._session = session
        self._host = host
        self._token = token
        self._name = name
        self._on_token = on_token
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._reader: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    @property
    def token(self) -> str | None:
        return self._token

    def _url(self) -> str:
        name = base64.b64encode(self._name.encode()).decode()
        url = (
            f"wss://{self._host}:{WS_PORT}/api/v2/channels/"
            f"samsung.remote.control?name={name}"
        )
        if self._token:
            url += f"&token={self._token}"
        return url

    # ---------- REST ----------
    async def device_info(self) -> dict[str, Any]:
        """Return /api/v2/ info. Raises SamsungTVConnectionError if unreachable."""
        urls = (
            f"http://{self._host}:{REST_PORT}/api/v2/",
            f"https://{self._host}:{WS_PORT}/api/v2/",
        )
        last_err: Exception | None = None
        for url in urls:
            try:
                async with asyncio.timeout(3):
                    async with self._session.get(url, ssl=False) as resp:
                        return await resp.json(content_type=None)
            except (aiohttp.ClientError, TimeoutError, ValueError) as err:
                last_err = err
        raise SamsungTVConnectionError(f"{self._host} unreachable: {last_err}")

    async def power_state(self) -> str:
        """Return 'on', 'standby' or 'off'."""
        try:
            info = await self.device_info()
        except SamsungTVConnectionError:
            return "off"
        state = info.get("device", {}).get("PowerState")
        return (state or "on").lower()

    # ---------- WebSocket ----------
    async def _ensure_connected(self, timeout: float = 10) -> None:
        if self._ws is not None and not self._ws.closed:
            return
        ws: aiohttp.ClientWebSocketResponse | None = None
        try:
            async with asyncio.timeout(timeout):
                ws = await self._session.ws_connect(self._url(), ssl=False, heartbeat=30)
                while True:
                    msg = await ws.receive()
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        raise SamsungTVConnectionError(f"Unexpected WS message: {msg.type}")
                    data = json.loads(msg.data)
                    event = data.get("event")
                    if event == "ms.channel.connect":
                        new_token = (data.get("data") or {}).get("token")
                        if new_token and new_token != self._token:
                            _LOGGER.debug("Received new token from TV")
                            self._token = new_token
                            if self._on_token:
                                self._on_token(new_token)
                        break
                    if event in ("ms.channel.unauthorized", "ms.channel.timeOut"):
                        raise SamsungTVAuthError(event)
        except TimeoutError as err:
            if ws is not None:
                await ws.close()
            raise SamsungTVConnectionError("Timeout connecting to TV") from err
        except (aiohttp.ClientError, OSError) as err:
            if ws is not None:
                await ws.close()
            raise SamsungTVConnectionError(str(err)) from err
        except SamsungTVError:
            if ws is not None:
                await ws.close()
            raise

        self._ws = ws
        self._reader = asyncio.create_task(self._read_loop(ws))

    async def _read_loop(self, ws: aiohttp.ClientWebSocketResponse) -> None:
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    _LOGGER.debug("TV event: %s", msg.data[:200])
        except Exception:  # noqa: BLE001
            pass
        finally:
            if self._ws is ws:
                self._ws = None

    async def _drop(self) -> None:
        if self._reader:
            self._reader.cancel()
            self._reader = None
        if self._ws is not None:
            ws, self._ws = self._ws, None
            await ws.close()

    async def _send(self, payload: dict[str, Any]) -> None:
        async with self._lock:
            for attempt in (1, 2):
                await self._ensure_connected()
                try:
                    await self._ws.send_str(json.dumps(payload))  # type: ignore[union-attr]
                    return
                except (aiohttp.ClientError, ConnectionResetError, RuntimeError, AttributeError) as err:
                    await self._drop()
                    if attempt == 2:
                        raise SamsungTVConnectionError(str(err)) from err

    async def pair(self, timeout: float = 30) -> str | None:
        """Connect and wait for user to press Allow on the TV. Returns token."""
        async with self._lock:
            await self._ensure_connected(timeout=timeout)
        return self._token

    async def send_key(self, key: str, cmd: str = "Click") -> None:
        await self._send(
            {
                "method": "ms.remote.control",
                "params": {
                    "Cmd": cmd,
                    "DataOfCmd": key,
                    "Option": "false",
                    "TypeOfRemote": "SendRemoteKey",
                },
            }
        )

    async def hold_key(self, key: str, seconds: float) -> None:
        await self.send_key(key, "Press")
        await asyncio.sleep(seconds)
        await self.send_key(key, "Release")

    async def launch_app(self, app_id: str) -> None:
        await self._send(
            {
                "method": "ms.channel.emit",
                "params": {
                    "event": "ed.apps.launch",
                    "to": "host",
                    "data": {"appId": app_id, "action_type": "DEEP_LINK"},
                },
            }
        )

    async def close(self) -> None:
        async with self._lock:
            await self._drop()
