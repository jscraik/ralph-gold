from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import tomllib  # py>=3.11
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


# -------------------------
# Dataclasses
# -------------------------


@dataclass(frozen=True)
class LoopConfig:
    max_iterations: int = 10
    no_progress_limit: int = 3
    rate_limit_per_hour: int = 0  # 0 = disabled
    sleep_seconds_between_iters: int = 0
    runner_timeout_seconds: int = 900  # 15m default (Codex can be slow)


@dataclass(frozen=True)
class FilesConfig:
    # Default: keep *all* Ralph durable memory in .ralph/ (user preference)
    prd: str = ".ralph/PRD.md"
    progress: str = ".ralph/progress.md"
    prompt: str = ".ralph/PROMPT_build.md"
    agents: str = ".ralph/AGENTS.md"
    specs_dir: str = ".ralph/specs"


@dataclass(frozen=True)
class RunnerConfig:
    argv: List[str]


@dataclass(frozen=True)
class LlmJudgeConfig:
    enabled: bool = False
    agent: str = "claude"
    prompt: str = ".ralph/PROMPT_judge.md"
    max_diff_chars: int = 30000


@dataclass(frozen=True)
class GatesConfig:
    commands: List[str]
    llm_judge: LlmJudgeConfig
    precommit_hook: bool = False
    fail_fast: bool = True
    output_mode: str = "summary"  # full|summary|errors_only
    max_output_lines: int = 50


@dataclass(frozen=True)
class GitConfig:
    # Branch automation
    branch_strategy: str = "per_prd"  # none|per_prd
    base_branch: str = ""  # empty => current HEAD
    branch_prefix: str = "ralph/"

    # Commit automation
    auto_commit: bool = True
    commit_message_template: str = "ralph: {story_id} {title}"
    amend_if_needed: bool = True


@dataclass(frozen=True)
class GitHubTrackerConfig:
    """Configuration for GitHub Issues tracker."""

    repo: str = ""
    auth_method: str = "gh_cli"  # gh_cli|token
    token_env: str = "GITHUB_TOKEN"
    label_filter: str = "ready"
    exclude_labels: List[str] = None  # type: ignore
    close_on_done: bool = True
    comment_on_done: bool = True
    add_labels_on_start: List[str] = None  # type: ignore
    add_labels_on_done: List[str] = None  # type: ignore
    cache_ttl_seconds: int = 300

    def __post_init__(self) -> None:
        """Initialize mutable default values."""
        if self.exclude_labels is None:
            object.__setattr__(self, "exclude_labels", ["blocked"])
        if self.add_labels_on_start is None:
            object.__setattr__(self, "add_labels_on_start", ["in-progress"])
        if self.add_labels_on_done is None:
            object.__setattr__(self, "add_labels_on_done", ["completed"])


@dataclass(frozen=True)
class TrackerConfig:
    # auto|markdown|json|beads|yaml|github_issues
    kind: str = "auto"
    plugin: str = ""  # optional: module:callable
    github: GitHubTrackerConfig = None  # type: ignore

    def __post_init__(self) -> None:
        """Initialize mutable default values."""
        if self.github is None:
            object.__setattr__(self, "github", GitHubTrackerConfig())


@dataclass(frozen=True)
class ParallelConfig:
    """Configuration for parallel execution with git worktrees."""

    enabled: bool = False
    max_workers: int = 3
    worktree_root: str = ".ralph/worktrees"
    strategy: str = "queue"  # queue|group
    merge_policy: str = "manual"  # manual|auto_merge


@dataclass(frozen=True)
class Config:
    loop: LoopConfig
    files: FilesConfig
    runners: Dict[str, RunnerConfig]
    gates: GatesConfig
    git: GitConfig
    tracker: TrackerConfig
    parallel: ParallelConfig


# -------------------------
# Parsing helpers
# -------------------------


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _coerce_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        v = value.strip().lower()
        if v in {"true", "1", "yes", "y", "on"}:
            return True
        if v in {"false", "0", "no", "n", "off"}:
            return False
    return default


def _load_toml(path: Path) -> Dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _deep_merge(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    """Merge b into a (recursively for dicts), return new dict."""

    out: Dict[str, Any] = dict(a)
    for k, v in b.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _resolve_existing(project_root: Path, preferred: str, candidates: List[str]) -> str:
    """Return the first existing path among [preferred] + candidates, else preferred."""

    if preferred:
        if (project_root / preferred).exists():
            return preferred
    for c in candidates:
        if (project_root / c).exists():
            return c
    return preferred


def _load_config_data(project_root: Path) -> Tuple[Dict[str, Any], List[Path]]:
    """Return merged toml data and the list of config files read (in order)."""

    paths: List[Path] = []

    # 1) project-local .ralph config (preferred)
    p1 = project_root / ".ralph" / "ralph.toml"
    if p1.exists():
        paths.append(p1)

    # 2) project root override
    p2 = project_root / "ralph.toml"
    if p2.exists():
        paths.append(p2)

    # 3) explicit env override
    env = os.environ.get("RALPH_CONFIG")
    if env:
        p3 = Path(env)
        if not p3.is_absolute():
            p3 = (project_root / p3).resolve()
        if p3.exists():
            paths.append(p3)

    data: Dict[str, Any] = {}
    for p in paths:
        data = _deep_merge(data, _load_toml(p))

    return data, paths


# -------------------------
# Public API
# -------------------------


def load_config(project_root: Path) -> Config:
    """Load and normalize configuration.

    Key behavior:
    - Prefers .ralph/ralph.toml (if present).
    - Allows ./ralph.toml to override.
    - Allows $RALPH_CONFIG to override both.

    The returned config is always usable (defaults applied).
    """

    data, _read_paths = _load_config_data(project_root)

    loop_raw = data.get("loop", {}) or {}
    files_raw = data.get("files", {}) or {}
    runners_raw = data.get("runners", {}) or {}
    gates_raw = data.get("gates", {}) or {}
    git_raw = data.get("git", {}) or {}
    tracker_raw = data.get("tracker", {}) or {}
    parallel_raw = data.get("parallel", {}) or {}

    loop = LoopConfig(
        max_iterations=_coerce_int(loop_raw.get("max_iterations"), 10),
        no_progress_limit=_coerce_int(loop_raw.get("no_progress_limit"), 3),
        rate_limit_per_hour=_coerce_int(loop_raw.get("rate_limit_per_hour"), 0),
        sleep_seconds_between_iters=_coerce_int(
            loop_raw.get("sleep_seconds_between_iters"), 0
        ),
        runner_timeout_seconds=_coerce_int(loop_raw.get("runner_timeout_seconds"), 900),
    )

    # Default file layout: all durable memory files live in .ralph/
    files = FilesConfig(
        prd=str(files_raw.get("prd", FilesConfig.prd)),
        progress=str(files_raw.get("progress", FilesConfig.progress)),
        prompt=str(files_raw.get("prompt", FilesConfig.prompt)),
        agents=str(files_raw.get("agents", FilesConfig.agents)),
        specs_dir=str(
            files_raw.get("specs_dir", files_raw.get("specsDir", FilesConfig.specs_dir))
        ),
    )

    # Resolve common filename mismatches automatically (prevents hard crashes).
    files = FilesConfig(
        prd=_resolve_existing(
            project_root,
            files.prd,
            [
                ".ralph/PRD.md",
                ".ralph/prd.json",
                "PRD.md",
                "prd.json",
                "IMPLEMENTATION_PLAN.md",
            ],
        ),
        progress=_resolve_existing(
            project_root,
            files.progress,
            [".ralph/progress.md", "progress.md"],
        ),
        prompt=_resolve_existing(
            project_root,
            files.prompt,
            [
                ".ralph/PROMPT_build.md",
                ".ralph/PROMPT.md",
                "PROMPT_build.md",
                "PROMPT.md",
            ],
        ),
        agents=_resolve_existing(
            project_root,
            files.agents,
            [".ralph/AGENTS.md", "AGENTS.md"],
        ),
        specs_dir=_resolve_existing(
            project_root,
            files.specs_dir,
            [".ralph/specs", "specs"],
        ),
    )

    # Default runner argv are intentionally conservative and easy to edit.
    # IMPORTANT: Codex expects the prompt either as the PROMPT positional argument or via stdin.
    # Using '-' is the most robust way to feed long prompts (no quoting issues).
    default_runners: Dict[str, RunnerConfig] = {
        "codex": RunnerConfig(argv=["codex", "exec", "--full-auto", "-"]),
        # Claude Code best practice for automation is headless print mode (-p)
        # with streaming JSON output for programmatic parsing/logging.
        "claude": RunnerConfig(argv=["claude", "-p", "--output-format", "stream-json"]),
        "copilot": RunnerConfig(argv=["copilot", "--prompt"]),
    }

    runners: Dict[str, RunnerConfig] = {}
    for name, rc in default_runners.items():
        raw = runners_raw.get(name, None)
        if isinstance(raw, dict) and isinstance(raw.get("argv"), list):
            runners[name] = RunnerConfig(argv=[str(x) for x in raw["argv"]])
        else:
            runners[name] = rc

    # Carry any user-defined runners (custom/enterprise wrappers) if present.
    for name, raw in runners_raw.items():
        if name in runners:
            continue
        if isinstance(raw, dict) and isinstance(raw.get("argv"), list):
            runners[name] = RunnerConfig(argv=[str(x) for x in raw["argv"]])

    gate_cmds: List[str] = []
    raw_cmds = gates_raw.get("commands", [])
    if isinstance(raw_cmds, list):
        gate_cmds = [str(x) for x in raw_cmds if str(x).strip()]

    llm_raw = gates_raw.get("llm_judge", {}) or {}
    if not isinstance(llm_raw, dict):
        llm_raw = {}

    llm_judge = LlmJudgeConfig(
        enabled=_coerce_bool(
            llm_raw.get("enabled", gates_raw.get("llm_judge_enabled")), False
        ),
        agent=str(llm_raw.get("agent", gates_raw.get("llm_judge_agent", "claude"))),
        prompt=str(
            llm_raw.get(
                "prompt",
                gates_raw.get(
                    "llm_judge_prompt",
                    FilesConfig.prompt.replace("PROMPT_build", "PROMPT_judge"),
                ),
            )
        ),
        max_diff_chars=_coerce_int(
            llm_raw.get(
                "max_diff_chars", gates_raw.get("llm_judge_max_diff_chars", 30000)
            ),
            30000,
        ),
    )

    gates = GatesConfig(
        commands=gate_cmds,
        llm_judge=llm_judge,
        precommit_hook=_coerce_bool(
            gates_raw.get("precommit_hook", gates_raw.get("precommitHook")), False
        ),
        fail_fast=_coerce_bool(
            gates_raw.get("fail_fast", gates_raw.get("failFast")), True
        ),
        output_mode=str(
            gates_raw.get("output_mode", gates_raw.get("outputMode", "summary"))
        ),
        max_output_lines=_coerce_int(
            gates_raw.get("max_output_lines", gates_raw.get("maxOutputLines")), 50
        ),
    )

    git = GitConfig(
        branch_strategy=str(
            git_raw.get(
                "branch_strategy",
                git_raw.get("branchStrategy", GitConfig.branch_strategy),
            )
        ),
        base_branch=str(
            git_raw.get("base_branch", git_raw.get("baseBranch", GitConfig.base_branch))
        ),
        branch_prefix=str(
            git_raw.get(
                "branch_prefix", git_raw.get("branchPrefix", GitConfig.branch_prefix)
            )
        ),
        auto_commit=_coerce_bool(
            git_raw.get("auto_commit", git_raw.get("autoCommit")), GitConfig.auto_commit
        ),
        commit_message_template=str(
            git_raw.get(
                "commit_message_template",
                git_raw.get("commitMessageTemplate", GitConfig.commit_message_template),
            )
        ),
        amend_if_needed=_coerce_bool(
            git_raw.get("amend_if_needed", git_raw.get("amendIfNeeded")),
            GitConfig.amend_if_needed,
        ),
    )

    # Parse GitHub tracker configuration
    github_raw = tracker_raw.get("github", {}) or {}
    if not isinstance(github_raw, dict):
        github_raw = {}

    # Parse exclude_labels list
    exclude_labels_raw = github_raw.get("exclude_labels", ["blocked"])
    if isinstance(exclude_labels_raw, list):
        exclude_labels = [str(x) for x in exclude_labels_raw]
    else:
        exclude_labels = ["blocked"]

    # Parse add_labels_on_start list
    add_labels_on_start_raw = github_raw.get("add_labels_on_start", ["in-progress"])
    if isinstance(add_labels_on_start_raw, list):
        add_labels_on_start = [str(x) for x in add_labels_on_start_raw]
    else:
        add_labels_on_start = ["in-progress"]

    # Parse add_labels_on_done list
    add_labels_on_done_raw = github_raw.get("add_labels_on_done", ["completed"])
    if isinstance(add_labels_on_done_raw, list):
        add_labels_on_done = [str(x) for x in add_labels_on_done_raw]
    else:
        add_labels_on_done = ["completed"]

    github_config = GitHubTrackerConfig(
        repo=str(github_raw.get("repo", "")),
        auth_method=str(github_raw.get("auth_method", "gh_cli")),
        token_env=str(github_raw.get("token_env", "GITHUB_TOKEN")),
        label_filter=str(github_raw.get("label_filter", "ready")),
        exclude_labels=exclude_labels,
        close_on_done=_coerce_bool(github_raw.get("close_on_done"), True),
        comment_on_done=_coerce_bool(github_raw.get("comment_on_done"), True),
        add_labels_on_start=add_labels_on_start,
        add_labels_on_done=add_labels_on_done,
        cache_ttl_seconds=_coerce_int(github_raw.get("cache_ttl_seconds"), 300),
    )

    tracker = TrackerConfig(
        kind=str(tracker_raw.get("kind", TrackerConfig.kind)).strip() or "auto",
        plugin=str(
            tracker_raw.get("plugin", tracker_raw.get("plugin_path", ""))
        ).strip(),
        github=github_config,
    )

    # Parse parallel configuration
    if not isinstance(parallel_raw, dict):
        parallel_raw = {}

    # Validate strategy
    strategy = str(parallel_raw.get("strategy", "queue")).strip().lower()
    if strategy not in {"queue", "group"}:
        raise ValueError(
            f"Invalid parallel.strategy: {strategy!r}. Must be 'queue' or 'group'."
        )

    # Validate merge_policy
    merge_policy = str(parallel_raw.get("merge_policy", "manual")).strip().lower()
    if merge_policy not in {"manual", "auto_merge"}:
        raise ValueError(
            f"Invalid parallel.merge_policy: {merge_policy!r}. "
            f"Must be 'manual' or 'auto_merge'."
        )

    # Validate max_workers
    max_workers = _coerce_int(parallel_raw.get("max_workers"), 3)
    if max_workers < 1:
        raise ValueError(f"Invalid parallel.max_workers: {max_workers}. Must be >= 1.")

    parallel = ParallelConfig(
        enabled=_coerce_bool(parallel_raw.get("enabled"), False),
        max_workers=max_workers,
        worktree_root=str(parallel_raw.get("worktree_root", ".ralph/worktrees")),
        strategy=strategy,
        merge_policy=merge_policy,
    )

    return Config(
        loop=loop,
        files=files,
        runners=runners,
        gates=gates,
        git=git,
        tracker=tracker,
        parallel=parallel,
    )
