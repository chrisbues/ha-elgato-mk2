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

## Getting them on macOS

Same idea as Windows: the working identity lives in Control Center's process memory while it is
connected to a light. On macOS you dump that memory with the built-in developer tools, then carve the
PEM/DER material out of the dump.

Prerequisites: the **Xcode Command Line Tools** (`xcode-select --install`) provide `lldb`; OpenSSL
(`openssl`, preinstalled, or `brew install openssl`) is handy for inspecting what you recover.

1. Open Elgato **Control Center** and make sure it can see/control your light (so it's connected and
   the identity is resident in memory).
2. Find the process id:
   ```
   pgrep -f "Control Center" || pgrep -if elgato
   ```
3. Take a full memory dump of that process. macOS has no `gcore`, so use `lldb` (you'll be prompted
   for your password, and on recent macOS you may need to approve the developer-tools / debugging
   prompt):
   ```
   sudo lldb -p <PID> -o "process save-core /tmp/cc.core" -o "detach" -o "quit"
   ```
   If attaching fails, relaunch Control Center under the debugger instead. Pass the binary as
   `lldb`'s own target argument (after `--`) so a target exists before `process launch` runs — putting
   the path inside the `process launch` command gives `error: invalid target`:
   ```
   sudo lldb "/Applications/Elgato Control Center.app/Contents/MacOS/Control Center"
   (lldb) process launch --stop-at-entry
   (lldb) continue
   ```
   Let it connect to the light, press **Ctrl-C** to return to the `(lldb)` prompt, then
   `process save-core /tmp/cc.core`.

   > **Caveat — code signing.** Control Center is shipped with the hardened runtime and without the
   > `get-task-allow` entitlement, so macOS may refuse the debugger even under `sudo` ("not allowed to
   > attach to process" / a code-signing error), for both attach and launch. If so, either run the
   > extraction with SIP disabled (`csrutil disable` from Recovery, re-enable afterwards), or re-sign
   > a copy of the app with `get-task-allow`. Try `process save-core` on the already-running PID first
   > (above) — it's the least likely to trip the signing check.
4. Carve the certs and key out of the dump. The server-leaf **cert + EC private key** are present as
   PEM, and the intermediate/root CAs are DER (see `docs/PROTOCOL.md` for the approach). A quick way
   to pull the PEM blocks:
   ```
   # leaf cert + EC private key (PEM, appear verbatim in the dump)
   awk '/-----BEGIN CERTIFICATE-----/,/-----END CERTIFICATE-----/'   /tmp/cc.core > /tmp/leaf.pem
   awk '/-----BEGIN EC PRIVATE KEY-----/,/-----END EC PRIVATE KEY-----/' /tmp/cc.core > /tmp/leaf.key
   ```
   If a file came out with more than one block, split it and keep the leaf (the one whose public key
   matches `leaf.key` — check with `openssl x509 -in leaf.pem -noout -pubkey` vs
   `openssl ec -in leaf.key -pubout`). The `Elgato Lights Intermediate CA` cert is DER inside the
   dump; recover it with the same carving script referenced in `docs/PROTOCOL.md` and convert it:
   ```
   openssl x509 -inform der -in intermediate.der -out intermediate.pem
   ```
5. Assemble (leaf first, then intermediate):
   ```
   cat /tmp/leaf.pem intermediate.pem > client-chain.pem
   mv /tmp/leaf.key client.key
   ```
   Place `client-chain.pem` and `client.key` in this folder, then delete the dump
   (`rm /tmp/cc.core`) — it contains the private key in cleartext.

**Linux:** the identity can be recovered the same way from a running process — dump it with
`gcore <PID>` (or `sudo cat /proc/<PID>/maps` + `gdb`), then carve with the identical steps.

> This is exactly the "users supply their own cert" model discussed upstream. If Elgato publishes a
> documented client identity, this step goes away.
