from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .. import __version__
from ..output import get_output_config, print_json_output, print_output


def _project_root() -> Path:
    return Path(os.getcwd()).resolve()


def cmd_bridge(args: argparse.Namespace) -> int:
    root = _project_root()
    from ..bridge import BridgeServer

    server = BridgeServer(root)
    # JSON-RPC over stdio (NDJSON). This call blocks until stdin closes.
    server.serve()
    return 0


def cmd_tui(args: argparse.Namespace) -> int:
    root = _project_root()
    from ..tui import run_tui

    return int(run_tui(root))


def cmd_serve(args: argparse.Namespace) -> int:
    from ..health import serve_health

    serve_health(host=str(args.host), port=int(args.port), version=__version__)
    return 0


def cmd_completion(args: argparse.Namespace) -> int:
    """Generate shell completion scripts."""

    from ..completion import generate_bash_completion, generate_zsh_completion

    if get_output_config().format == "json":
        print_json_output(
            {
                "cmd": "completion",
                "error": "JSON output is not supported for completion script generation.",
                "exit_code": 2,
            }
        )
        return 2

    shell = args.shell

    if shell == "bash":
        script = generate_bash_completion()
        print(script)
        print_output("\n# Installation instructions:", level="normal", file=sys.stderr)
        print_output(
            "# Save to file: ralph completion bash > ~/.ralph-completion.sh",
            level="normal",
            file=sys.stderr,
        )
        print_output(
            "# Add to ~/.bashrc: source ~/.ralph-completion.sh",
            level="normal",
            file=sys.stderr,
        )
        print_output(
            "# Or install system-wide: sudo cp ~/.ralph-completion.sh /etc/bash_completion.d/ralph",
            level="normal",
            file=sys.stderr,
        )
    elif shell == "zsh":
        script = generate_zsh_completion()
        print(script)
        print_output("\n# Installation instructions:", level="normal", file=sys.stderr)
        print_output(
            "# Save to file: ralph completion zsh > ~/.zsh/completion/_ralph",
            level="normal",
            file=sys.stderr,
        )
        print_output(
            "# Add to ~/.zshrc: fpath=(~/.zsh/completion $fpath)",
            level="normal",
            file=sys.stderr,
        )
        print_output("# Then run: compinit", level="normal", file=sys.stderr)
    else:
        print_output(f"Error: Unknown shell '{shell}'", level="error")
        print_output("Supported shells: bash, zsh", level="error")
        return 2

    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    """Convert PRD files (JSON or Markdown) to YAML format."""
    from ..converters import convert_to_yaml

    input_path = Path(args.input_file).resolve()
    output_path = Path(args.output_file).resolve()

    try:
        convert_to_yaml(
            input_path=input_path,
            output_path=output_path,
            infer_groups=bool(args.infer_groups),
        )

        print_output(f"✓ Converted {input_path.name} to {output_path}", level="quiet")

        if args.infer_groups:
            print_output("  Groups inferred from task titles", level="quiet")

        # Show summary
        import yaml

        with open(output_path) as f:
            data = yaml.safe_load(f)

        tasks = data.get("tasks", [])
        total = len(tasks)
        completed = sum(1 for t in tasks if t.get("completed", False))

        print_output(f"  Tasks: {total} total, {completed} completed", level="quiet")

        if args.infer_groups:
            groups = {}
            for task in tasks:
                group = task.get("group", "default")
                groups[group] = groups.get(group, 0) + 1

            if len(groups) > 1:
                print_output(
                    f"  Groups: {', '.join(f'{g} ({c})' for g, c in sorted(groups.items()))}",
                    level="quiet",
                )

        return 0

    except FileNotFoundError as e:
        print_output(f"Error: {e}", level="error")
        return 2
    except ValueError as e:
        print_output(f"Error: {e}", level="error")
        return 2
    except Exception as e:
        print_output(f"Unexpected error: {e}", level="error")
        return 2
