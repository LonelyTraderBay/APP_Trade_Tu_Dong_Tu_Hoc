# Contract: Packaged Windows ops (D1c)

## Single-instance

- Second process MUST exit non-zero or focus existing window; MUST NOT open second SQLite writer.

## Sleep / resume

- On resume: run Startup Recovery subset before new exposure (same as core D1a/D1b).

## Backup / restore

- Backup: SQLite (+ WAL/SHM if present) + non-secret `ui_settings`.
- Restore: refuse if schema_meta incompatible; never restore plaintext secrets (re-enter keyring).

## Installer

- one-folder PyInstaller; clean Win11 x64 install path documented in quickstart (later).
- No listening TCP port in packaged process (ADR-D13).
