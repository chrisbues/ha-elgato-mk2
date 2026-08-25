# Elgato Key Light MK.2 (local)

Local Home Assistant control for the **Elgato Key Light Air / MK.2**, which replaced the old HTTP REST
API with **JSON-RPC 2.0 over mutual-TLS WebSocket**. Gives you a native `light` entity (on/off,
brightness, colour temperature) — no cloud.

You must supply a client certificate (Elgato's — extracted from Control Center); see the README.
Reverse-engineered with Claude Fable 5 via Craft Agent.
