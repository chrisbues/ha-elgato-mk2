# Elgato Key Light Air MK.2 — local protocol teardown (for python-elgato / core `elgato`)

Re: home-assistant discussions #4673. Hardware in hand: **Key Light Air MK.2**, model
`20LAM9901`, `hardwareBoardType` 214, `hardwareRevision` 1.1, firmware build 148, MAC
`<your-light-mac>`. Everything below is confirmed against the live device.

## TL;DR
- MK.2 (the TLS variant) drops the plain-HTTP REST API and speaks **JSON-RPC 2.0 over a
  mutual-TLS WebSocket** on `:9123`.
- Method names are the old REST resources, **verb-prefixed**: `get.elgato.lights`,
  `put.elgato.lights`, `get.elgato.accessory-info`. Payloads are byte-for-byte the old shapes.
- The mTLS client cert the light demands is an **Elgato-signed** cert. The generic
  `ElgatoLightsServerLeafCertificate` (shipped in both firmware and Control Center) has
  **EKU = serverAuth + clientAuth**, so it doubles as a **universal client cert** — this is the
  "cert for a wide audience" unblock.

## Discovery
- mDNS `_elg._tcp.local`, port 9123. TXT:
  `mf=Elgato dt=214 id=<mac> md=Elgato Key Light Air MK.2 20LAM9901 pv=1.0 tls=CERT_1_VER_EN`
- The **`tls=CERT_1_VER_EN`** TXT key is the reliable discriminator. The non-TLS Key Light MK.2
  (`20GAK9902`, cf. jmylchreest/keylightd#24) has **no `tls` key** and still answers plain HTTP —
  which is why "just add the model to the allowlist" worked there but not here.

## Transport / mTLS
- `wss://<ip>:9123/` (root path). **TLS 1.2**, cipher `ECDHE-ECDSA-AES256-SHA` (EC P-256 throughout).
- Server sends a `CertificateRequest`; **Acceptable client CA = `CN=Elgato Lights Root CA`**.
- Client auth is *optional at the TLS layer* (handshake completes with no client cert), but the
  **application refuses to talk** (no WS upgrade / silent close) unless a valid client cert is
  presented. Present **leaf + intermediate**, or the server returns TLS alert 48 `unknown_ca`.
- PKI: `Elgato Lights Root CA` (self-signed) → `Elgato Lights Intermediate CA` →
  `ElgatoLightsServerLeafCertificate` (the light's server identity). Control Center also holds a
  **per-install client cert** `CN=ControlCenter-<guid>`, EC P-256, issued by the Intermediate CA.

## The universal-client-cert finding
`ElgatoLightsServerLeafCertificate` is a **generic** identity (no per-device data) present in the
firmware image *and* the desktop client. Its `keyUsage`/EKU includes **clientAuth**, so presenting
`{leaf + intermediate}` as the client chain authenticates against any MK.2. i.e. HA would **not**
need per-user cert extraction — a single bundled identity works for every unit. (Caveat: it's
Elgato's key; the clean path is Elgato blessing this / an official integration, but technically the
credential is uniform.) The per-install `ControlCenter-<guid>` client cert is *also* accepted, which
implies the app is signing its own client certs from the Intermediate CA it ships — i.e. the CA (or a
signing path) is on the client side too.

## JSON-RPC 2.0 application layer
- Requests: `{"jsonrpc":"2.0","id":"<uuid-string>","method":"<verb>.elgato.<resource>","params":{…}}`
- **Verb prefix maps to the old HTTP verb**: GET→`get.`, PUT→`put.`, POST→`post.`
- Confirmed methods:
  - `get.elgato.accessory-info` → `{productName, hardwareBoardType, hardwareRevision,
    firmwareBuildNumber, firmwareVersion, serialNumber, displayName, features, …}`
  - `get.elgato.lights` → `{"numberOfLights":1,"lights":[{"on":0|1,"brightness":0-100,"temperature":143-344}]}`
  - `put.elgato.lights` with the same `{numberOfLights, lights:[…]}` body → sets state
  - `get.elgato.lights.settings` (settings resource), `post.elgato.identify`, `elgato.restart`,
    `elgato.factory-reset`, `elgato.firmware-update.*` also present in the client's method table.
- Unknown methods → JSON-RPC error `-32601 Method not found` (so it's introspectable by probing;
  `rpc.discover` / `system.listMethods` are **not** implemented).
- The light **pushes unsolicited notifications**: `{"jsonrpc":"2.0","method":"notification.elgato.lights",
  "params":{…}}` (also `notification.elgato.accessory-info`, `notification.elgato.lights.settings`) —
  so a persistent connection gives instant state without polling.
- Payload semantics are identical to the legacy REST API (brightness 0-100, temperature in mireds
  143–344), so the mapping into `python-elgato` is 1:1 beyond the transport swap.

## Minimal working client (Python)
```python
import asyncio, ssl, json, uuid, aiohttp
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
ctx.load_cert_chain("leaf+intermediate.pem", "leaf.key")     # EKU clientAuth leaf + intermediate
async def rpc(ws, method, params=None):
    rid=str(uuid.uuid4()); msg={"jsonrpc":"2.0","id":rid,"method":method}
    if params: msg["params"]=params
    await ws.send_json(msg)
    while True:
        d=(await ws.receive()).json()
        if d.get("id")==rid: return d.get("result")   # skip notification.* frames
async def main():
    async with aiohttp.ClientSession() as s, s.ws_connect("wss://<light-ip>:9123/", ssl=ctx) as ws:
        print(await rpc(ws,"get.elgato.lights"))
        await rpc(ws,"put.elgato.lights",{"numberOfLights":1,"lights":[{"on":1,"brightness":40,"temperature":230}]})
asyncio.run(main())
```

## How the identity was obtained (for reproducibility)
Static extraction from the Windows client failed (no PKCS12/PEM/base64 cert in any assembly; only
Authenticode chains). The identity was recovered from a **full memory dump of Control Center while it
held a live connection** (`comsvcs.dll MiniDump`), then DER/PEM-carved: the server-leaf **cert + EC
private key** are present in cleartext (PEM) in memory; the per-install client key is a BouncyCastle
`ECPrivateKeyParameters` scalar (not DER). The bundled `Firmware_Key_Light_Air_Mk2.bin` also carries
packed cert material.

## Suggested path for core
1. Detect MK.2-TLS via the `tls=CERT_1_VER_EN` zeroconf TXT key (fall back to model list).
2. In `python-elgato`: add a WSS+JSON-RPC transport (verb-prefixed methods, UUID ids, notification
   stream) behind the existing model; keep the response mapping as-is.
3. Client cert: either bundle the universal `ElgatoLightsServerLeafCertificate` identity (pending an
   OK from Elgato), or a config-flow step to supply one. Worth asking Elgato directly given the OHF
   relationship — a documented client cert or a clientAuth-scoped identity would make this clean.

Happy to share raw pcaps / the carved chain / the full method table.
