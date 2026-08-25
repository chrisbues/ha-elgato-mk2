#!/usr/bin/env python3
"""
Elgato Key Light Air MK.2 — local control over the new WSS + JSON-RPC 2.0 protocol.

Reverse-engineered 2026-08-25 (Craft Agent). The MK.2 firmware replaced the old
plain-HTTP REST API (:9123/elgato/lights) with a mutual-TLS WebSocket endpoint
speaking JSON-RPC 2.0. Key facts:

  * Transport : wss://<ip>:9123/   (mutual TLS, TLS 1.2)
  * Client auth: the light demands a client cert chaining to "Elgato Lights Root CA".
                 We reuse the Elgato "server leaf" identity (cert has EKU=clientAuth)
                 extracted from Control Center's memory, presented WITH the
                 intermediate cert so the light can build the chain.
  * RPC      : JSON-RPC 2.0, string (UUID) ids. Methods are VERB-prefixed:
                 get.elgato.accessory-info
                 get.elgato.lights            -> {numberOfLights, lights:[{on,brightness,temperature}]}
                 put.elgato.lights  (params)  -> set state (same shape as the old REST PUT)
                 get.elgato.lights.settings
                 post.elgato.identify         (likely; mirrors old POST /identify)
               The light PUSHES unsolicited notification.elgato.lights / .accessory-info.

Requires: websockets  (pip install websockets)
Cert files (from the same folder by default): client-chain.pem (leaf+intermediate), client.key
"""
import asyncio, ssl, json, uuid, os, argparse
import websockets

HERE = os.path.dirname(os.path.abspath(__file__))

def make_ctx(certdir):
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE            # TODO: pin the light's server cert instead
    ctx.load_cert_chain(certfile=os.path.join(certdir, "client-chain.pem"),
                        keyfile=os.path.join(certdir, "client.key"))
    return ctx

class ElgatoMK2:
    def __init__(self, host, certdir=HERE, port=9123):
        self.uri = f"wss://{host}:{port}/"
        self.ctx = make_ctx(certdir)
        self.ws = None

    async def __aenter__(self):
        self.ws = await websockets.connect(self.uri, ssl=self.ctx, open_timeout=8)
        return self

    async def __aexit__(self, *a):
        await self.ws.close()

    async def call(self, method, params=None, timeout=4):
        rid = str(uuid.uuid4())
        msg = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            msg["params"] = params
        await self.ws.send(json.dumps(msg))
        for _ in range(12):                    # skip interleaved notifications
            r = json.loads(await asyncio.wait_for(self.ws.recv(), timeout))
            if r.get("id") == rid:
                if "error" in r:
                    raise RuntimeError(r["error"])
                return r.get("result")

    # convenience wrappers
    async def accessory_info(self): return await self.call("get.elgato.accessory-info")
    async def get_lights(self):     return await self.call("get.elgato.lights")
    async def set_lights(self, on=None, brightness=None, temperature=None):
        light = {}
        if on is not None:          light["on"] = int(on)
        if brightness is not None:  light["brightness"] = int(brightness)
        if temperature is not None: light["temperature"] = int(temperature)
        return await self.call("put.elgato.lights",
                               {"numberOfLights": 1, "lights": [light]})

async def _main():
    ap = argparse.ArgumentParser()
    ap.add_argument("host")
    ap.add_argument("cmd", choices=["info", "state", "on", "off", "set"])
    ap.add_argument("--brightness", type=int)
    ap.add_argument("--temperature", type=int, help="mireds ~143 (cool) .. 344 (warm)")
    ap.add_argument("--certdir", default=HERE)
    a = ap.parse_args()
    async with ElgatoMK2(a.host, a.certdir) as light:
        if a.cmd == "info":   print(json.dumps(await light.accessory_info(), indent=2))
        elif a.cmd == "state":print(json.dumps(await light.get_lights(), indent=2))
        elif a.cmd == "on":   print(await light.set_lights(on=1, brightness=a.brightness, temperature=a.temperature))
        elif a.cmd == "off":  print(await light.set_lights(on=0))
        elif a.cmd == "set":  print(await light.set_lights(brightness=a.brightness, temperature=a.temperature))

if __name__ == "__main__":
    asyncio.run(_main())
