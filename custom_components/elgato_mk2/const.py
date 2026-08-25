"""Constants for the Elgato Key Light MK.2 (local) integration."""
from __future__ import annotations

DOMAIN = "elgato_mk2"

# Elgato mired range reported by the hardware (cool -> warm).
MIN_MIRED = 143
MAX_MIRED = 344

DEFAULT_PORT = 9123
UPDATE_INTERVAL_SECONDS = 10

# Client-cert files, placed by the user in the certs/ subfolder of this integration.
# See certs/README.md and the repo README for how to obtain them. These are NOT
# shipped with the repository.
#   client-chain.pem : your client leaf cert + the Elgato intermediate cert (PEM, in that order)
#   client.key       : the matching private key (PEM)
CERT_CHAIN_FILE = "client-chain.pem"
CERT_KEY_FILE = "client.key"
