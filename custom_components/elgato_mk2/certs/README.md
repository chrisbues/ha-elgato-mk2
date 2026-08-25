# Client certificate — place your files here

This integration needs a client certificate the light will accept during its mutual-TLS handshake.
The light only trusts client certs that **chain to `Elgato Lights Root CA`**, so you can't self-sign —
you reuse the identity the official Elgato **Control Center** app already uses.

Place two PEM files in this folder (they are `.gitignore`d and must never be committed):

- **`client-chain.pem`** — your client **leaf** certificate, immediately followed by the Elgato
  **intermediate** CA certificate (PEM blocks, leaf first).
- **`client.key`** — the private key matching the leaf.

## Getting them from Control Center (Windows example)

The working identity lives in Control Center's process memory while it is connected to a light. The
generic `ElgatoLightsServerLeafCertificate` it holds has `EKU=serverAuth,clientAuth`, so it works as a
client cert.

1. Open Elgato **Control Center** and make sure it can see/control your light (so it's connected).
2. Take a full memory dump of the `ControlCenter` process. On Windows:
   ```
   rundll32.exe C:\Windows\System32\comsvcs.dll, MiniDump <PID> C:\temp\cc.dmp full
   ```
   (Find `<PID>` in Task Manager. Needs admin.)
3. Carve the certs and key out of the dump — the server-leaf **cert + EC private key** are present as
   PEM, and the intermediate/root CAs are DER. A short carving script (see `docs/PROTOCOL.md` for the
   approach) will recover:
   - the leaf cert + its `EC PRIVATE KEY`,
   - the `Elgato Lights Intermediate CA` cert.
4. Assemble:
   ```
   cat leaf.pem intermediate.pem > client-chain.pem
   mv leaf.key client.key
   ```

macOS/Linux: the equivalent identity ships with the Control Center app bundle / can be recovered the
same way from a running process.

> This is exactly the "users supply their own cert" model discussed upstream. If Elgato publishes a
> documented client identity, this step goes away.
