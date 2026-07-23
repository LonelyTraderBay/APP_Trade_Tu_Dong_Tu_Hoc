# Contract: Headless CLI DEMO Operations

**Phase**: D1b  
**Normative**: spec FR-010; clarify Q1=A  
**Entrypoint**: `autotrade-headless` (extend; exact subcommand names may match click/argparse style in tasks)

## Purpose

Owner-operated attended surface without PySide6 Broker Hub.

## Required operations (behavioral)

| Operation | Input | Effect |
|---|---|---|
| Store DEMO credentials | API key + secret (stdin/secure prompt) | Keyring refs only; redact logs |
| Test connection | none (uses stored refs) | Probe testnet + capabilities; print pass/fail (no secrets) |
| Enable DEMO | none | Requires valid cert + allowlist; sets DEMO account active if switch rules OK |
| Disable DEMO | none | Stops DEMO trading READY; does not delete cert |
| Switch account | `paper` \| `demo` | Enforces [account-switch.md](./account-switch.md) |
| Status | none | Active mode, cert validity, KS, unresolved recon summary |

## Non-goals

- Credential wizard UI / Broker Hub / Settings screens (D1c)
- Export secrets
- LIVE enable commands

## Telegram (unchanged command set)

`/status`, `/pnl`, `/pause` — payloads MUST include `mode=DEMO` or `mode=PAPER` for the active account.

## Tests

- Credential store never writes plaintext to SQLite
- Test connection fails closed on wrong endpoint/mode
- Enable without cert → refused
- Status redacts secrets
