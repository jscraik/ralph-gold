# Tooling Inventory

This is the repo-local, contract-backed tooling inventory for this repository.
It is generated from `docs/agents/tooling.contract.toml`.

## Table of Contents

- [Purpose](#purpose)
- [Required Mise Tools](#required-mise-tools)
- [Required Binaries](#required-binaries)
- [Required Codex Actions](#required-codex-actions)
- [Validation](#validation)

## Purpose

Single source of truth:

- [`docs/agents/tooling.contract.toml`](./tooling.contract.toml)

Derived artifacts and checks:

- [`.mise.toml`](../../.mise.toml)
- [`.codex/environments/environment.toml`](../../.codex/environments/environment.toml)
- [`scripts/check-environment.sh`](../../scripts/check-environment.sh)
- [`scripts/tooling_contract.py`](../../scripts/tooling_contract.py)

## Required Mise Tools

Required `[tools]` entries in [`.mise.toml`](../../.mise.toml):

- `uv`

## Required Binaries

Required binaries on `PATH` validated by
[`scripts/check-environment.sh`](../../scripts/check-environment.sh):

- `uv`
- `ralph`

## Required Codex Actions

Required action/icon pairs in
[`.codex/environments/environment.toml`](../../.codex/environments/environment.toml):

- `Tooling` -> `tool`
- `Run tests` -> `test`

## Validation

Regenerate tooling doc:

```bash
python3 scripts/tooling_contract.py --write-doc
```

Run environment check:

```bash
bash scripts/check-environment.sh
```
