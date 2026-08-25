# Home Assistant — Elgato Key Light Air / MK.2 (local)

A Home Assistant custom integration for the **Elgato Key Light Air MK.2** (`20LAM9901`) and other
MK.2-generation lights that advertise the new `tls=CERT_1_VER_EN` capability.

Unlike the original Key Lights, the MK.2 firmware **dropped the plain-HTTP REST API** and replaced it
with **JSON-RPC 2.0 over a mutual-TLS WebSocket** on port `9123`. The stock `elgato` integration talks
plain HTTP and can't connect, so these lights show up as "unsupported / can't connect". This
integration speaks the new protocol and gives you a proper local `light` entity: **on/off, brightness,
and colour temperature** — no cloud, no Stream Deck bridge.

> Status: works today, but it's an unofficial teardown. See [`docs/PROTOCOL.md`](docs/PROTOCOL.md) for
> the full protocol write-up. Official support is being discussed upstream in
> [home-assistant/discussions#4673](https://github.com/orgs/home-assistant/discussions/4673).

## The catch: a client certificate

The light requires a **client certificate chaining to `Elgato Lights Root CA`** during the mutual-TLS
handshake. That certificate is Elgato's, so **it is not shipped in this repo** — you supply your own.
The Elgato **desktop client (Control Center) holds a working client identity**, and the generic
`ElgatoLightsServerLeafCertificate` it uses carries `EKU=clientAuth`, so it doubles as a valid client
cert. Extract it once from your own machine and drop two PEM files in `certs/`. See
[`certs/README.md`](custom_components/elgato_mk2/certs/README.md) for the how-to.

## Install

### HACS (custom repository)
1. HACS → ⋮ → **Custom repositories** → add `https://github.com/McMoobud/ha-elgato-mk2`, category
   **Integration**.
2. Install **Elgato Key Light MK.2 (local)**.
3. Place your `client-chain.pem` and `client.key` in
   `config/custom_components/elgato_mk2/certs/` (see below).
4. Restart Home Assistant.

### Manual
Copy `custom_components/elgato_mk2/` into your `config/custom_components/`, add the two cert files to
its `certs/` folder, and restart HA.

### Add the light
**Settings → Devices & Services → Add Integration → "Elgato Key Light MK.2 (local)"**, then enter the
light's IP address.

## Providing the certificate

Put these two files in `custom_components/elgato_mk2/certs/`:

| File | Contents |
|------|----------|
| `client-chain.pem` | your client **leaf** cert **followed by** the Elgato **intermediate** cert (PEM, in that order) |
| `client.key` | the matching private key (PEM) |

Both must be presented — the leaf alone triggers a TLS `unknown_ca` (alert 48). Full extraction steps
are in [`certs/README.md`](custom_components/elgato_mk2/certs/README.md).

## Command-line tool

`tools/elgato_mk2_cli.py` is a standalone client (no HA required), handy for testing:

```bash
pip install websockets
python tools/elgato_mk2_cli.py 192.168.1.50 state
python tools/elgato_mk2_cli.py 192.168.1.50 on --brightness 50 --temperature 260
python tools/elgato_mk2_cli.py 192.168.1.50 off
```

## Protocol (short version)

- Transport: `wss://<ip>:9123/`, TLS 1.2, EC P-256, mutual TLS.
- JSON-RPC 2.0, **string (UUID) ids**, methods are the old REST resources **verb-prefixed**:
  - `get.elgato.accessory-info`
  - `get.elgato.lights` → `{"numberOfLights":1,"lights":[{"on":0|1,"brightness":0-100,"temperature":143-344}]}`
  - `put.elgato.lights` (same body) to set state
- The light also **pushes** `notification.elgato.lights` / `.accessory-info` frames for instant state.

Full teardown, PKI chain, and a minimal client: [`docs/PROTOCOL.md`](docs/PROTOCOL.md).

## Limitations / roadmap

- v0.1: polling coordinator, manual host entry, single light. TODO: consume the push notifications for
  instant state; zeroconf discovery filtered on the `tls=CERT_1_VER_EN` TXT key; multi-light rigs.
- The client cert / private key is Elgato's; treat it as you would any vendor credential.

## Credits

The MK.2 protocol was reverse-engineered — mDNS/TLS teardown, memory-dump cert recovery, and the
JSON-RPC method discovery — with **Claude Fable 5** (via Craft Agent) doing the investigation and
writing the integration, in an evening's work. Thanks also to the upstream discussion participants
(brodock, joagonca) and to `@frenck` / the Home Assistant `elgato` maintainers.

## License

MIT — see [LICENSE](LICENSE). Not affiliated with or endorsed by Elgato / Corsair.
