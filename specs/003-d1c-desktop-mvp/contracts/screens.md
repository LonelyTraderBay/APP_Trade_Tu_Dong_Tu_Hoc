# Contract: Screen inventory (v1.4 §09)

| Screen | Minimum widgets / actions | Core dependency |
|---|---|---|
| Dashboard | equity, pnl, KS badge, health, data age | ledger + KS + recon + adapter |
| Broker Hub | Paper/DEMO cards, Test, Disconnect, Enable (cert) | accounts + certify + adapter |
| Kill-switch | L1–L4 display, Pause, Flatten confirm | risk.kill_switch |
| Live Monitor | orders/intents table incl. UNKNOWN | oms + ledger |
| Strategy | rule_sma_cross_v1 params read-only ceilings | strategy binding |
| History | filter + CSV | audit/intents/fills |
| Settings | PIN change, Telegram, allowlist read-only, autostart, backup | pin + secrets + backup |
| Tray | status, pnl, Pause, Open, Quit | KS + dashboard |

Mode/account/endpoint text on every trade-capable screen.
