#!/usr/bin/env python3
"""Validate and render repo-local tooling contract artifacts."""

from __future__ import annotations

import argparse
import pathlib
import sys
import tomllib
from typing import Any


def _load_toml(path: pathlib.Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing file: {path}")
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _load_contract(path: pathlib.Path) -> dict[str, Any]:
    data = _load_toml(path)
    tooling = data.get("tooling")
    if not isinstance(tooling, dict):
        raise ValueError("contract must contain a [tooling] table")
    return tooling


def _validate_contract_shape(tooling: dict[str, Any]) -> tuple[list[str], list[str], list[dict[str, str]]]:
    required_mise_tools = tooling.get("required_mise_tools", [])
    required_bins = tooling.get("required_bins", [])
    required_codex_actions = tooling.get("required_codex_actions", [])

    if not isinstance(required_mise_tools, list) or not all(isinstance(x, str) for x in required_mise_tools):
        raise ValueError("tooling.required_mise_tools must be a string array")
    if not isinstance(required_bins, list) or not all(isinstance(x, str) for x in required_bins):
        raise ValueError("tooling.required_bins must be a string array")
    if not isinstance(required_codex_actions, list):
        raise ValueError("tooling.required_codex_actions must be an array of {name, icon} objects")

    normalized_actions: list[dict[str, str]] = []
    for entry in required_codex_actions:
        if not isinstance(entry, dict):
            raise ValueError("every tooling.required_codex_actions entry must be an object")
        name = entry.get("name")
        icon = entry.get("icon")
        if not isinstance(name, str) or not isinstance(icon, str):
            raise ValueError("every tooling.required_codex_actions entry needs string name and icon")
        normalized_actions.append({"name": name, "icon": icon})

    return required_mise_tools, required_bins, normalized_actions


def _validate_mise(mise_path: pathlib.Path, required_mise_tools: list[str]) -> list[str]:
    errors: list[str] = []
    data = _load_toml(mise_path)
    tools = data.get("tools")
    if not isinstance(tools, dict):
        return [f"missing [tools] table in {mise_path}"]
    for tool in required_mise_tools:
        if tool not in tools:
            errors.append(f"required tool '{tool}' is not pinned in {mise_path}")
    return errors


def _validate_codex_actions(codex_env_path: pathlib.Path, required_actions: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    data = _load_toml(codex_env_path)
    actions = data.get("actions")
    if not isinstance(actions, list):
        return [f"missing [[actions]] table array in {codex_env_path}"]

    action_pairs = {
        (action.get("name"), action.get("icon"))
        for action in actions
        if isinstance(action, dict)
    }
    for required in required_actions:
        pair = (required["name"], required["icon"])
        if pair not in action_pairs:
            errors.append(
                f"required Codex action missing or mismatched in {codex_env_path}: "
                f"name='{required['name']}', icon='{required['icon']}'"
            )
    return errors


def _render_doc(required_mise_tools: list[str], required_bins: list[str], required_actions: list[dict[str, str]]) -> str:
    lines: list[str] = [
        "# Tooling Inventory",
        "",
        "This is the repo-local, contract-backed tooling inventory for this repository.",
        "It is generated from `docs/agents/tooling.contract.toml`.",
        "",
        "## Table of Contents",
        "",
        "- [Purpose](#purpose)",
        "- [Required Mise Tools](#required-mise-tools)",
        "- [Required Binaries](#required-binaries)",
        "- [Required Codex Actions](#required-codex-actions)",
        "- [Validation](#validation)",
        "",
        "## Purpose",
        "",
        "Single source of truth:",
        "",
        "- [`docs/agents/tooling.contract.toml`](./tooling.contract.toml)",
        "",
        "Derived artifacts and checks:",
        "",
        "- [`.mise.toml`](../../.mise.toml)",
        "- [`.codex/environments/environment.toml`](../../.codex/environments/environment.toml)",
        "- [`scripts/check-environment.sh`](../../scripts/check-environment.sh)",
        "- [`scripts/tooling_contract.py`](../../scripts/tooling_contract.py)",
        "",
        "## Required Mise Tools",
        "",
        "Required `[tools]` entries in [`.mise.toml`](../../.mise.toml):",
        "",
    ]
    lines.extend([f"- `{tool}`" for tool in required_mise_tools] or ["- _none_"])

    lines += [
        "",
        "## Required Binaries",
        "",
        "Required binaries on `PATH` validated by",
        "[`scripts/check-environment.sh`](../../scripts/check-environment.sh):",
        "",
    ]
    lines.extend([f"- `{binary}`" for binary in required_bins] or ["- _none_"])

    lines += [
        "",
        "## Required Codex Actions",
        "",
        "Required action/icon pairs in",
        "[`.codex/environments/environment.toml`](../../.codex/environments/environment.toml):",
        "",
    ]
    lines.extend([f"- `{action['name']}` -> `{action['icon']}`" for action in required_actions] or ["- _none_"])

    lines += [
        "",
        "## Validation",
        "",
        "Regenerate tooling doc:",
        "",
        "```bash",
        "python3 scripts/tooling_contract.py --write-doc",
        "```",
        "",
        "Run environment check:",
        "",
        "```bash",
        "bash scripts/check-environment.sh",
        "```",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", default="docs/agents/tooling.contract.toml")
    parser.add_argument("--mise", default=".mise.toml")
    parser.add_argument("--codex-env", default=".codex/environments/environment.toml")
    parser.add_argument("--doc", default="docs/agents/tooling.md")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--write-doc", action="store_true")
    parser.add_argument("--check-doc", action="store_true")
    parser.add_argument("--print-required-bins", action="store_true")
    args = parser.parse_args()

    contract_path = pathlib.Path(args.contract)
    mise_path = pathlib.Path(args.mise)
    codex_env_path = pathlib.Path(args.codex_env)
    doc_path = pathlib.Path(args.doc)

    tooling = _load_contract(contract_path)
    required_mise_tools, required_bins, required_actions = _validate_contract_shape(tooling)

    if args.print_required_bins:
        for binary in required_bins:
            print(binary)

    if args.validate:
        errors = []
        errors.extend(_validate_mise(mise_path, required_mise_tools))
        errors.extend(_validate_codex_actions(codex_env_path, required_actions))
        if errors:
            for error in errors:
                print(f"Error: {error}")
            return 1

    if args.write_doc or args.check_doc:
        rendered = _render_doc(required_mise_tools, required_bins, required_actions)
        if args.write_doc:
            doc_path.parent.mkdir(parents=True, exist_ok=True)
            doc_path.write_text(rendered, encoding="utf-8")
            print(f"Wrote {doc_path}")
        elif args.check_doc:
            if not doc_path.exists():
                print(f"Error: tooling doc is missing at {doc_path}")
                print("Fix: run `python3 scripts/tooling_contract.py --write-doc`.")
                return 1
            current = doc_path.read_text(encoding="utf-8")
            if current != rendered:
                print(f"Error: tooling doc is out of date: {doc_path}")
                print("Fix: run `python3 scripts/tooling_contract.py --write-doc`.")
                return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
