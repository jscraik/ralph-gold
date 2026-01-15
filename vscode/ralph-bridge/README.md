# Ralph Bridge (VS Code extension)

This extension provides a thin control surface for **ralph-gold** inside VS Code.

It spawns the CLI bridge:

```bash
ralph bridge
```

…and communicates using the stdio JSON-RPC protocol described in:
- `../../docs/VSCODE_BRIDGE_PROTOCOL.md`

## Prerequisites

- `ralph` installed in PATH (recommended: `uv tool install -e .` from the main repo)
- agent CLIs installed (`codex`, `claude`, `copilot`) if you plan to use those runners

## Install

This folder is a standard VS Code extension project. Two common ways to run it:

### A) Run in Extension Development Host (no packaging)

1. Open this folder in VS Code:
   - `vscode/ralph-bridge`
2. Press `F5` to run the extension.

### B) Package into a .vsix (recommended for daily use)

Requires Node.js and VS Code's packaging tool:

```bash
npm i -g @vscode/vsce
cd vscode/ralph-bridge
vsce package
```

Then install the generated `.vsix` via:
- **Extensions → … → Install from VSIX…**

## Usage

Open the Command Palette and run:
- **Ralph: Start Bridge**
- **Ralph: Status**
- **Ralph: Step (one iteration)**
- **Ralph: Run Loop**
- **Ralph: Stop Loop** / **Pause** / **Resume**

Logs appear in the **Ralph** Output panel.

## Configuration

- `ralph.bridgeCommand` (string): command used to start the bridge (default: `ralph`)
