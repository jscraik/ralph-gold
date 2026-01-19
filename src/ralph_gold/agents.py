"""Plugin architecture for agent runners.

This module provides a flexible plugin system for AI agent runners,
making it easy to add new agents and customize existing ones.

Benefits:
- Centralized agent configuration
- Easy to add new agent types
- Consistent agent invocation patterns
- Better testability

Usage:
    >>> from ralph_gold.agents import build_agent_invocation
    >>> argv, stdin = build_agent_invocation("codex", prompt, cfg)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from .config import Config, RunnerConfig


class AgentBuilder(ABC):
    """Abstract base class for agent builders.

    Each agent type (codex, claude, copilot, etc.) has its own builder
    that knows how to construct the appropriate command-line invocation.
    """

    @abstractmethod
    def build_argv(
        self, prompt: str, config: RunnerConfig
    ) -> Tuple[List[str], Optional[str]]:
        """Build argv and optional stdin for the agent.

        Args:
            prompt: The prompt text to send to the agent
            config: The runner configuration for this agent

        Returns:
            A tuple of (argv_list, optional_stdin_text)
            If stdin is provided, argv typically contains '-' as a placeholder
        """
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the agent name."""
        pass


class CodexAgentBuilder(AgentBuilder):
    """Builder for Codex CLI agent.

    Codex prefers stdin for prompts to avoid argv quoting/length issues.
    Example: `codex exec --full-auto -` (prompt read from stdin).
    """

    def build_argv(
        self, prompt: str, config: RunnerConfig
    ) -> Tuple[List[str], Optional[str]]:
        argv = [str(x) for x in config.argv]

        # Placeholder replacement (string literal '{prompt}')
        if "{prompt}" in argv:
            argv = [prompt if x == "{prompt}" else x for x in argv]
            return argv, None

        # Codex: stdin is the most robust approach
        if "-" not in argv:
            argv.append("-")
        return argv, prompt

    @property
    def name(self) -> str:
        return "codex"


class ClaudeAgentBuilder(AgentBuilder):
    """Builder for Claude Code CLI agent.

    Claude uses -p flag for single-line prompts or accepts
    interactive input.
    """

    def build_argv(
        self, prompt: str, config: RunnerConfig
    ) -> Tuple[List[str], Optional[str]]:
        argv = [str(x) for x in config.argv]

        # Placeholder replacement
        if "{prompt}" in argv:
            argv = [prompt if x == "{prompt}" else x for x in argv]
            return argv, None

        # Claude Code: `claude -p "..."`
        if "-p" in argv:
            i = argv.index("-p")
            if i == len(argv) - 1 or str(argv[i + 1]).startswith("-"):
                argv.insert(i + 1, prompt)
            else:
                argv[i + 1] = prompt
        else:
            argv.extend(["-p", prompt])
        return argv, None

    @property
    def name(self) -> str:
        return "claude"


class CopilotAgentBuilder(AgentBuilder):
    """Builder for GitHub Copilot CLI agent.

    Copilot uses --prompt flag for single-line prompts.
    """

    def build_argv(
        self, prompt: str, config: RunnerConfig
    ) -> Tuple[List[str], Optional[str]]:
        argv = [str(x) for x in config.argv]

        # Placeholder replacement
        if "{prompt}" in argv:
            argv = [prompt if x == "{prompt}" else x for x in argv]
            return argv, None

        # GitHub Copilot CLI: `copilot --prompt "..."`
        if "--prompt" in argv:
            i = argv.index("--prompt")
            if i == len(argv) - 1 or str(argv[i + 1]).startswith("-"):
                argv.insert(i + 1, prompt)
            else:
                argv[i + 1] = prompt
        else:
            argv.extend(["--prompt", prompt])
        return argv, None

    @property
    def name(self) -> str:
        return "copilot"


class GenericAgentBuilder(AgentBuilder):
    """Generic builder for custom/unknown agents.

    This builder handles agents that don't have specialized builders.
    It follows common conventions for CLI tools by appending the prompt
    as the final argument.
    """

    def __init__(self, name: str):
        self._name = name.lower().strip()

    def build_argv(
        self, prompt: str, config: RunnerConfig
    ) -> Tuple[List[str], Optional[str]]:
        argv = [str(x) for x in config.argv]

        # Placeholder replacement
        if "{prompt}" in argv:
            argv = [prompt if x == "{prompt}" else x for x in argv]
            return argv, None

        # Default: append prompt as final argument
        argv.append(prompt)
        return argv, None

    @property
    def name(self) -> str:
        return self._name


# Registry of known agent builders
_AGENT_BUILDERS: dict[str, AgentBuilder] = {
    "codex": CodexAgentBuilder(),
    "claude": ClaudeAgentBuilder(),
    "copilot": CopilotAgentBuilder(),
}


def register_agent_builder(name: str, builder: AgentBuilder) -> None:
    """Register a custom agent builder.

    This allows users to add support for new agent types at runtime.

    Args:
        name: The agent name (e.g., "my-custom-agent")
        builder: An AgentBuilder instance

    Example:
        >>> class MyAgentBuilder(AgentBuilder):
        ...     def build_argv(self, prompt, config):
        ...         return ["my-agent", "--prompt", prompt], None
        ...     @property
        ...     def name(self):
        ...         return "my-agent"
        >>> register_agent_builder("my-agent", MyAgentBuilder())
    """
    _AGENT_BUILDERS[name.lower().strip()] = builder
    logging.getLogger(__name__).info("Registered agent builder: %s", name)


def get_agent_builder(agent: str) -> AgentBuilder:
    """Get the agent builder for a given agent name.

    Args:
        agent: The agent name (e.g., "codex", "claude")

    Returns:
        An AgentBuilder instance

    Raises:
        ValueError: If the agent name is empty
    """
    agent_l = agent.lower().strip()
    if not agent_l:
        raise ValueError("Agent name cannot be empty")

    builder = _AGENT_BUILDERS.get(agent_l)
    if builder is None:
        # Return a generic builder for unknown agents
        return GenericAgentBuilder(agent_l)
    return builder


def build_agent_invocation(
    agent: str, prompt: str, config: RunnerConfig
) -> Tuple[List[str], Optional[str]]:
    """Build agent invocation using the plugin architecture.

    This is the main entry point for building agent command-line invocations.
    It automatically selects the appropriate builder based on the agent name.

    Args:
        agent: The agent name (e.g., "codex", "claude")
        prompt: The prompt text to send to the agent
        config: The runner configuration for this agent

    Returns:
        A tuple of (argv_list, optional_stdin_text)

    Raises:
        ValueError: If the agent name is empty

    Example:
        >>> argv, stdin = build_agent_invocation("codex", "fix the bug", cfg)
        >>> print(argv)
        ['codex', 'exec', '--full-auto', '-']
        >>> print(stdin[:50])
        'fix the bug'
    """
    builder = get_agent_builder(agent)
    return builder.build_argv(prompt, config)


def list_known_agents() -> List[str]:
    """Return a list of all known agent names.

    This includes both built-in agents and any custom registered agents.

    Returns:
        A sorted list of agent names

    Example:
        >>> list_known_agents()
        ['claude', 'codex', 'copilot']
    """
    return sorted(_AGENT_BUILDERS.keys())


def get_runner_config(cfg: Config, agent: str) -> RunnerConfig:
    """Get the runner configuration for a given agent.

    Args:
        cfg: The global Ralph configuration
        agent: The agent name

    Returns:
        The RunnerConfig for this agent

    Raises:
        RuntimeError: If the agent is not configured

    Example:
        >>> config = get_runner_config(cfg, "codex")
        >>> print(config.argv)
        ['codex', 'run', '--no-confirm', '--format', 'json', '--']
    """
    runner = cfg.runners.get(agent)
    if runner is None:
        available = ", ".join(sorted(cfg.runners.keys()))
        raise RuntimeError(
            f"Unknown agent '{agent}'. Available runners: {available}"
        )
    return runner
