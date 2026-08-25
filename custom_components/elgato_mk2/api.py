"""Local WSS + JSON-RPC 2.0 client for the Elgato Key Light Air/MK.2.

The MK.2 firmware replaced the old plain-HTTP REST API with a mutual-TLS
WebSocket endpoint (wss://<ip>:9123/) speaking JSON-RPC 2.0 with UUID ids.
Methods are verb-prefixed and mirror the old REST resources:

    get.elgato.accessory-info
    get.elgato.lights            -> {numberOfLights, lights:[{on,brightness,temperature}]}
    put.elgato.lights (params)   -> set state (same shape)

The light demands a client certificate chaining to "Elgato Lights Root CA".
We present the Elgato server-leaf identity (its cert carries EKU=clientAuth)
together with the intermediate cert so the light can build the chain.
"""
from __future__ import annotations

import asyncio
import os
import ssl
import uuid
from typing import Any

import aiohttp

from .const import CERT_CHAIN_FILE, CERT_KEY_FILE, DEFAULT_PORT

_CERT_DIR = os.path.join(os.path.dirname(__file__), "certs")


class ElgatoMK2Error(Exception):
    """Raised on connection or RPC errors."""


def _build_ssl_context() -> ssl.SSLContext:
    """Blocking: build the mutual-TLS client context. Run in an executor."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # the light uses a private CA; we don't pin it (yet)
    ctx.load_cert_chain(
        certfile=os.path.join(_CERT_DIR, CERT_CHAIN_FILE),
        keyfile=os.path.join(_CERT_DIR, CERT_KEY_FILE),
    )
    return ctx


class ElgatoMK2Client:
    """Minimal async client — one short-lived WS connection per operation."""

    def __init__(self, host: str, session: aiohttp.ClientSession, port: int = DEFAULT_PORT) -> None:
        self._host = host
        self._port = port
        self._session = session
        self._ssl: ssl.SSLContext | None = None
        self._lock = asyncio.Lock()

    @property
    def _uri(self) -> str:
        return f"wss://{self._host}:{self._port}/"

    async def _ensure_ssl(self) -> ssl.SSLContext:
        if self._ssl is None:
            loop = asyncio.get_running_loop()
            self._ssl = await loop.run_in_executor(None, _build_ssl_context)
        return self._ssl

    async def _rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        ctx = await self._ensure_ssl()
        rid = str(uuid.uuid4())
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            payload["params"] = params
        async with self._lock:
            try:
                async with self._session.ws_connect(
                    self._uri, ssl=ctx, timeout=aiohttp.ClientWSTimeout(ws_close=10)
                ) as ws:
                    await ws.send_json(payload)
                    # Skip interleaved notifications; match our request id.
                    for _ in range(15):
                        msg = await asyncio.wait_for(ws.receive(), timeout=6)
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            raise ElgatoMK2Error(f"unexpected ws message: {msg.type}")
                        data = msg.json()
                        if data.get("id") != rid:
                            continue
                        if "error" in data:
                            raise ElgatoMK2Error(str(data["error"]))
                        return data.get("result")
                    raise ElgatoMK2Error("no matching JSON-RPC response")
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as err:
                raise ElgatoMK2Error(str(err)) from err

    async def async_get_info(self) -> dict[str, Any]:
        return await self._rpc("get.elgato.accessory-info")

    async def async_get_lights(self) -> dict[str, Any]:
        return await self._rpc("get.elgato.lights")

    async def async_set_lights(
        self,
        *,
        on: bool | None = None,
        brightness: int | None = None,
        temperature: int | None = None,
    ) -> dict[str, Any]:
        light: dict[str, Any] = {}
        if on is not None:
            light["on"] = 1 if on else 0
        if brightness is not None:
            light["brightness"] = int(brightness)
        if temperature is not None:
            light["temperature"] = int(temperature)
        return await self._rpc(
            "put.elgato.lights", {"numberOfLights": 1, "lights": [light]}
        )
