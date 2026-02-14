from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

# Import for type annotation only (avoid circular dependency at runtime)
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ralph_gold.authorization import EnforcementMode
else:
    from ralph_gold.authorization import EnforcementMode

try:
    import tomllib  # py>=3.11
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

logger = logging.getLogger(__name__)


# -------------------------
# Dataclasses
# -------------------------


@dataclass(frozen=True)
class LoopModeConfig:
    max_iterations: Optional[int] = None
    no_progress_limit: Optional[int] = None
    rate_limit_per_hour: Optional[int] = None
    sleep_seconds_between_iters: Optional[int] = None
    runner_timeout_seconds: Optional[int] = None
    max_attempts_per_task: Optional[int] = None
    skip_blocked_tasks: Optional[bool] = None


_LOOP_MODE_NAMES: Tuple[str, ...] = ("speed", "quality", "exploration")
LOOP_MODE_NAMES: Tuple[str, ...] = _LOOP_MODE_NAMES


def _default_loop_modes() -> Dict[str, LoopModeConfig]:
    return {name: LoopModeConfig() for name in _LOOP_MODE_NAMES}


@dataclass(frozen=True)
class LoopConfig:
    max_iterations: int = 10
    no_progress_limit: int = 3
    rate_limit_per_hour: int = 0  # 0 = disabled
    sleep_seconds_between_iters: int = 0
    runner_timeout_seconds: int = 900  # 15m default (Codex can be slow)
    max_attempts_per_task: int = 3
    skip_blocked_tasks: bool = True
    mode: str = "speed"
    modes: Dict[str, LoopModeConfig] = field(default_factory=_default_loop_modes)

    def __post_init__(self) -> None:
        """Validate LoopConfig values to prevent configuration errors.

        This validation catches common misconfigurations early, preventing
        runtime issues like infinite loops or unreasonable timeouts.

        Raises:
            ValueError: If any configuration value is invalid
        """
        if self.max_iterations < 1:
            raise ValueError(
                f"max_iterations must be >= 1, got {self.max_iterations}"
            )
        if self.max_iterations > 1000:
            raise ValueError(
                f"max_iterations suspiciously large: {self.max_iterations} "
                f"(limit: 1000)"
            )
        if self.no_progress_limit < 1:
            raise ValueError(
                f"no_progress_limit must be >= 1, got {self.no_progress_limit}"
            )
        if self.no_progress_limit > 100:
            raise ValueError(
                f"no_progress_limit suspiciously large: {self.no_progress_limit} "
                f"(limit: 100)"
            )
        # Auto-adjust no_progress_limit if it exceeds max_iterations
        # This can happen when combining defaults with overrides
        if self.no_progress_limit > self.max_iterations:
            # Use object.__setattr__ because dataclass is frozen
            object.__setattr__(self, "no_progress_limit", self.max_iterations)

        if self.runner_timeout_seconds < 1:
            raise ValueError(
                f"runner_timeout_seconds must be >= 1, got {self.runner_timeout_seconds}"
            )
        if self.runner_timeout_seconds > 86400:  # 24 hours
            raise ValueError(
                f"runner_timeout_seconds suspiciously large: {self.runner_timeout_seconds} "
                f"(limit: 86400 = 24 hours)"
            )
        if self.max_attempts_per_task < 1:
            raise ValueError(
                f"max_attempts_per_task must be >= 1, got {self.max_attempts_per_task}"
            )
        if self.max_attempts_per_task > 100:
            raise ValueError(
                f"max_attempts_per_task suspiciously large: {self.max_attempts_per_task} "
                f"(limit: 100)"
            )
        if self.rate_limit_per_hour < 0:
            raise ValueError(
                f"rate_limit_per_hour must be >= 0, got {self.rate_limit_per_hour}"
            )
        if self.rate_limit_per_hour > 1000:
            raise ValueError(
                f"rate_limit_per_hour suspiciously large: {self.rate_limit_per_hour} "
                f"(limit: 1000)"
            )
        if self.sleep_seconds_between_iters < 0:
            raise ValueError(
                f"sleep_seconds_between_iters must be >= 0, got {self.sleep_seconds_between_iters}"
            )
        if self.sleep_seconds_between_iters > 3600:  # 1 hour
            raise ValueError(
                f"sleep_seconds_between_iters suspiciously large: {self.sleep_seconds_between_iters} "
                f"(limit: 3600 = 1 hour)"
            )
        if self.mode not in _LOOP_MODE_NAMES:
            raise ValueError(
                f"Invalid loop mode: {self.mode!r}. "
                f"Must be one of: {', '.join(_LOOP_MODE_NAMES)}."
            )


@dataclass(frozen=True)
class FilesConfig:
    # Default: keep *all* Ralph durable memory in .ralph/ (user preference)
    prd: str = ".ralph/PRD.md"
    progress: str = ".ralph/progress.md"
    prompt: str = ".ralph/PROMPT_build.md"
    plan: str = ".ralph/PROMPT_plan.md"
    judge: str = ".ralph/PROMPT_judge.md"
    review: str = ".ralph/PROMPT_review.md"
    agents: str = ".ralph/AGENTS.md"
    specs_dir: str = ".ralph/specs"
    feedback: str = ".ralph/FEEDBACK.md"


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
class ReviewConfig:
    enabled: bool = False
    backend: str = "runner"  # runner|repoprompt
    agent: str = "claude"  # used when backend=runner
    prompt: str = ".ralph/PROMPT_review.md"
    max_diff_chars: int = 30000
    required_token: str = "SHIP"


@dataclass(frozen=True)
class PrekConfig:
    enabled: bool = False
    argv: List[str] = field(default_factory=lambda: ["prek", "run", "--all-files"])


@dataclass(frozen=True)
class GatesSmartConfig:
    enabled: bool = False
    skip_gates_for: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class GatesConfig:
    commands: List[str]
    llm_judge: LlmJudgeConfig
    review: ReviewConfig = field(default_factory=ReviewConfig)
    prek: PrekConfig = field(default_factory=PrekConfig)
    smart: GatesSmartConfig = field(default_factory=GatesSmartConfig)
    precommit_hook: bool = False
    fail_fast: bool = True
    output_mode: str = "summary"  # full|summary|errors_only
    max_output_lines: int = 50


@dataclass(frozen=True)
class GitConfig:
    # Branch automation
    branch_strategy: str = "none"  # none|per_prd|task
    base_branch: str = ""  # empty => current HEAD
    branch_prefix: str = "ralph/"

    # Commit automation
    auto_commit: bool = False
    commit_message_template: str = "ralph: {story_id} {title}"
    amend_if_needed: bool = True


@dataclass(frozen=True)
class GitHubTrackerConfig:
    """Configuration for GitHub Issues tracker."""

    repo: str = ""
    auth_method: str = "gh_cli"  # gh_cli|token
    token_env: str = "GITHUB_TOKEN"
    label_filter: str = "ready"
    exclude_labels: Optional[List[str]] = None
    close_on_done: bool = True
    comment_on_done: bool = True
    add_labels_on_start: Optional[List[str]] = None
    add_labels_on_done: Optional[List[str]] = None
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
class WebTrackerConfig:
    """Configuration for Web Analysis tracker.

    The web analysis tracker performs reconnaissance on web applications
    to discover and generate tasks for issues, optimizations, and areas
    needing investigation.
    """

    base_url: str = ""
    sitemap_url: str = ""  # default: {base_url}/sitemap.xml
    crawl_depth: int = 2
    max_pages: int = 100
    api_discovery: bool = True
    js_analysis: bool = True
    normalize_hashes: bool = True
    headless_nav: bool = False
    cache_ttl_seconds: int = 3600
    output_path: str = ".ralph/web_analysis.json"

    def __post_init__(self) -> None:
        """Initialize derived values."""
        # If sitemap_url is not set, derive from base_url
        if not self.sitemap_url and self.base_url:
            # Normalize base_url and append /sitemap.xml
            base = self.base_url.rstrip("/")
            object.__setattr__(self, "sitemap_url", f"{base}/sitemap.xml")


@dataclass(frozen=True)
class TrackerConfig:
    # auto|markdown|json|beads|yaml|github_issues|web_analysis
    kind: str = "auto"
    plugin: str = ""  # optional: module:callable
    github: Optional[GitHubTrackerConfig] = None
    web: Optional[WebTrackerConfig] = None

    def __post_init__(self) -> None:
        """Initialize mutable default values."""
        if self.github is None:
            object.__setattr__(self, "github", GitHubTrackerConfig())
        if self.web is None:
            object.__setattr__(self, "web", WebTrackerConfig())


@dataclass(frozen=True)
class RepoPromptConfig:
    enabled: bool = False
    required: bool = False
    cli: str = "rp-cli"
    window_id: Optional[int] = None
    tab: str = ""
    workspace: str = ""
    builder_type: str = "clarify"  # clarify|plan|question
    copy_preset: str = ""
    timeout_seconds: int = 300
    fail_open: bool = True


@dataclass(frozen=True)
class ParallelConfig:
    """Configuration for parallel execution with git worktrees."""

    enabled: bool = False
    max_workers: int = 3
    worktree_root: str = ".ralph/worktrees"
    strategy: str = "queue"  # queue|group
    merge_policy: str = "manual"  # manual|auto_merge


@dataclass(frozen=True)
class DiagnosticsConfig:
    """Configuration for diagnostics features."""

    enabled: bool = True
    check_gates: bool = True
    validate_prd: bool = True


@dataclass(frozen=True)
class StatsConfig:
    """Configuration for statistics tracking."""

    track_duration: bool = True
    track_cost: bool = False  # Future: API cost tracking


@dataclass(frozen=True)
class WatchConfig:
    """Configuration for watch mode."""

    enabled: bool = False
    patterns: List[str] = field(default_factory=lambda: ["**/*.py", "**/*.md"])
    debounce_ms: int = 500
    auto_commit: bool = False


@dataclass(frozen=True)
class HarnessReplayConfig:
    """Configuration for harness replay behavior."""

    default_isolation: str = "worktree"  # worktree|snapshot
    max_case_timeout_seconds: int = 900


@dataclass(frozen=True)
class HarnessRetentionConfig:
    """Configuration for harness artifact retention."""

    cases_days: int = 30
    runs_days: int = 30
    keep_last_runs: int = 20
    pinned_days: int = 90


@dataclass(frozen=True)
class HarnessBucketConfig:
    """Configuration for harness bucket classification thresholds."""

    small_max_seconds: int = 120
    medium_max_seconds: int = 600


@dataclass(frozen=True)
class HarnessCIConfig:
    """Configuration for harness CI orchestration."""

    enabled: bool = True
    execution_mode: str = "historical"  # historical|live
    max_cases: int = 200
    enforce_regression_threshold: bool = True
    require_baseline: bool = True
    baseline_missing_policy: str = "fail"  # fail|warn


@dataclass(frozen=True)
class HarnessConfig:
    """Configuration for harness dataset/evaluation commands."""

    enabled: bool = False
    owner: str = "engineering"
    dataset_path: str = ".ralph/harness/cases.json"
    pinned_dataset_path: str = ".ralph/harness/pinned.json"
    runs_dir: str = ".ralph/harness/runs"
    baseline_run_path: str = ".ralph/harness/runs/baseline.json"
    append_pinned_by_default: bool = True
    max_cases_per_task: int = 2
    default_days: int = 30
    default_limit: int = 200
    regression_threshold: float = 0.05
    buckets: HarnessBucketConfig = field(default_factory=HarnessBucketConfig)
    ci: HarnessCIConfig = field(default_factory=HarnessCIConfig)
    replay: HarnessReplayConfig = field(default_factory=HarnessReplayConfig)
    retention: HarnessRetentionConfig = field(default_factory=HarnessRetentionConfig)


@dataclass(frozen=True)
class SupervisorConfig:
    """Configuration for long-running supervisor/heartbeat mode.

    This config is used by `ralph supervise`. It is intentionally conservative:
    - Notifications are enabled by default (best-effort).
    - No new dependencies are required; backends are selected based on what is installed.
    """

    heartbeat_seconds: int = 60
    sleep_seconds_between_runs: int = 5
    max_runtime_seconds: int = 0  # 0 = unlimited

    # stop|continue
    on_no_progress_limit: str = "stop"

    # wait|stop
    on_rate_limit: str = "wait"

    # Notifications
    notify_enabled: bool = True
    notify_events: List[str] = field(
        default_factory=lambda: ["complete", "stopped", "error"]
    )
    notify_backend: str = "auto"  # auto|macos|linux|windows|command|none
    notify_command_argv: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProgressConfig:
    """Configuration for progress visualization."""

    show_velocity: bool = True
    show_burndown: bool = True
    chart_width: int = 60


@dataclass(frozen=True)
class TemplatesConfig:
    """Configuration for task templates."""

    builtin: List[str] = field(
        default_factory=lambda: ["bug-fix", "feature", "refactor"]
    )
    custom_dir: str = ".ralph/templates"


@dataclass(frozen=True)
class OutputControlConfig:
    """Configuration for output control (verbosity and format)."""

    verbosity: str = "normal"  # quiet|normal|verbose
    format: str = "text"  # text|json


@dataclass(frozen=True)
class PromptConfig:
    """Configuration for prompt building and spec limits.

    Attributes:
        enable_limits: Whether to enforce spec size limits (default: false for backward compatibility)
        max_specs_files: Maximum number of spec files to include (default: 20)
        max_specs_chars: Maximum total characters across all specs (default: 100000)
        max_single_spec_chars: Maximum characters for a single spec file (default: 50000)
        truncate_long_specs: Whether to truncate oversized specs vs excluding them (default: true)
        specs_inclusion_order: How to order specs - "sorted", "recency", or "manual" (default: "sorted")
        context_total_budget: Total character budget for all context (default: 50000)
        context_progress_max_lines: Maximum number of progress entries to include (default: 100)
        context_progress_max_chars: Maximum characters for progress section (default: 10000)
        context_prune_on_build: Automatically truncate progress when building prompt (default: true)
        context_archive_old_entries: Archive old progress entries (default: true)
        context_archive_dir: Directory for archived progress relative to .ralph/ (default: archive/progress)
    """

    enable_limits: bool = False
    max_specs_files: int = 20
    max_specs_chars: int = 100000  # Increased from 50000 (2x) to reduce spec truncation
    max_single_spec_chars: int = 50000  # Increased from 10000 (5x) for larger individual specs
    truncate_long_specs: bool = True
    specs_inclusion_order: str = "sorted"  # sorted|recency|manual
    # Context management settings
    context_total_budget: int = 50000
    context_progress_max_lines: int = 100
    context_progress_max_chars: int = 10000
    context_prune_on_build: bool = True
    context_archive_old_entries: bool = True
    context_archive_dir: str = "archive/progress"


@dataclass(frozen=True)
class AuthorizationConfig:
    """Configuration for file write authorization.

    Attributes:
        enabled: Whether authorization verification is active
        fallback_to_full_auto: Skip auth when --full-auto flag present
        permissions_file: Path to permissions JSON file
        enforcement_mode: How to handle authorization failures (warn or block)
    """

    enabled: bool = False
    fallback_to_full_auto: bool = False
    permissions_file: str = ".ralph/permissions.json"
    enforcement_mode: EnforcementMode = EnforcementMode.WARN  # type: ignore[assignment]


@dataclass(frozen=True)
class StateConfig:
    """Configuration for state validation and cleanup.

    Attributes:
        auto_cleanup_stale: Automatically remove stale task IDs (default: false for safety)
        validate_on_startup: Validate state against PRD on startup (default: true)
        warn_on_prd_modified: Warn if PRD modified after state (default: true)
        protect_current_task: Always protect current task from cleanup (default: true)
        protect_recent_hours: Protect tasks completed in last N hours (default: 1)
    """

    auto_cleanup_stale: bool = False  # CHANGED: Default false for safety
    validate_on_startup: bool = True
    warn_on_prd_modified: bool = True
    protect_current_task: bool = True
    protect_recent_hours: int = 1


@dataclass(frozen=True)
class InitConfig:
    """Configuration for ralph init behavior.

    Attributes:
        merge_config_on_reinit: Whether to merge config when re-running init (default: true)
        merge_strategy: Strategy for merging - "user_wins", "template_wins", or "ask" (default: "user_wins")
        preserve_sections: Config sections never overwritten (user values always kept)
        merge_sections: Config sections to merge (user values override template)
    """

    merge_config_on_reinit: bool = True
    merge_strategy: str = "user_wins"  # user_wins|template_wins|ask
    preserve_sections: List[str] = field(
        default_factory=lambda: [
            "runners.custom",
            "tracker.github",
            "tracker.web",
            "authorization",
        ]
    )
    merge_sections: List[str] = field(
        default_factory=lambda: [
            "loop",
            "gates",
            "files",
            "prompt",
            "state",
            "output_control",
        ]
    )


@dataclass(frozen=True)
class AdaptiveTimeoutConfig:
    """Configuration for adaptive timeout behavior.

    Phase 5: Adaptive Timeout & Unblock mechanism.

    Attributes:
        enabled: Whether adaptive timeout is enabled (default: true)
        enable_complexity_scaling: Apply complexity-based multipliers (default: true)
        enable_failure_scaling: Increase timeout after each failure (default: true)
        max_timeout: Absolute maximum timeout in seconds (default: 3600 = 1 hour)
        min_timeout: Absolute minimum timeout in seconds (default: 60 = 1 minute)
        timeout_multiplier_per_failure: 50% increase per timeout (default: 1.5)
        default_mode_timeout: Fallback when mode timeout not available (default: 120)
    """

    enabled: bool = True
    enable_complexity_scaling: bool = True
    enable_failure_scaling: bool = True
    max_timeout: int = 3600  # 1 hour
    min_timeout: int = 60  # 1 minute
    timeout_multiplier_per_failure: float = 1.5
    default_mode_timeout: int = 120  # speed mode default


@dataclass(frozen=True)
class UnblockConfig:
    """Configuration for unblock commands and batch operations.

    Phase 5: Adaptive Timeout & Unblock mechanism.

    Attributes:
        auto_suggest: Automatically suggest unblock strategies (default: true)
        max_auto_unblock_attempts: Maximum times to auto-unblock a task (default: 1)
        require_reason: Require reason for unblock operations (default: true)
        allow_batch_unblock: Allow batch unblock operations (default: true)
    """

    auto_suggest: bool = True
    max_auto_unblock_attempts: int = 1
    require_reason: bool = True
    allow_batch_unblock: bool = True


@dataclass(frozen=True)
class Config:
    loop: LoopConfig
    files: FilesConfig
    runners: Dict[str, RunnerConfig]
    gates: GatesConfig
    git: GitConfig
    tracker: TrackerConfig
    parallel: ParallelConfig
    repoprompt: RepoPromptConfig = field(default_factory=RepoPromptConfig)
    diagnostics: DiagnosticsConfig = field(default_factory=DiagnosticsConfig)
    stats: StatsConfig = field(default_factory=StatsConfig)
    watch: WatchConfig = field(default_factory=WatchConfig)
    harness: HarnessConfig = field(default_factory=HarnessConfig)
    supervisor: SupervisorConfig = field(default_factory=SupervisorConfig)
    progress: ProgressConfig = field(default_factory=ProgressConfig)
    templates: TemplatesConfig = field(default_factory=TemplatesConfig)
    output: OutputControlConfig = field(default_factory=OutputControlConfig)
    prompt: PromptConfig = field(default_factory=PromptConfig)
    state: StateConfig = field(default_factory=StateConfig)
    authorization: AuthorizationConfig = field(default_factory=AuthorizationConfig)
    init: InitConfig = field(default_factory=InitConfig)
    adaptive_timeout: AdaptiveTimeoutConfig = field(default_factory=AdaptiveTimeoutConfig)
    unblock: UnblockConfig = field(default_factory=UnblockConfig)


# -------------------------
# Parsing helpers
# -------------------------


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (ValueError, TypeError) as e:
        logger.debug("Coercion failed: %s", e)
        return default


def _parse_string_list(raw: Any, default: List[str]) -> List[str]:
    """Parse a list configuration value with type coercion.

    Args:
        raw: Raw value from config (list, str, or other)
        default: Default list if raw is invalid

    Returns:
        List of coerced strings
    """
    if isinstance(raw, list):
        return [str(x) for x in raw]
    elif isinstance(raw, str) and raw.strip():
        return [raw.strip()]
    else:
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
    except (tomli.TOMLDecodeError, OSError) as e:
        logger.debug("Failed to load TOML: %s", e)
        return {}


def _normalize_mode_name(value: Any, default: str = "speed") -> str:
    if isinstance(value, str):
        candidate = value.strip().lower()
        if candidate:
            return candidate
    return default


def _parse_loop_mode_config(raw: Any) -> LoopModeConfig:
    if not isinstance(raw, dict):
        return LoopModeConfig()
    return LoopModeConfig(
        max_iterations=(
            _coerce_int(raw.get("max_iterations"), None)
            if raw.get("max_iterations") is not None
            else None
        ),
        no_progress_limit=(
            _coerce_int(raw.get("no_progress_limit"), None)
            if raw.get("no_progress_limit") is not None
            else None
        ),
        rate_limit_per_hour=(
            _coerce_int(raw.get("rate_limit_per_hour"), None)
            if raw.get("rate_limit_per_hour") is not None
            else None
        ),
        sleep_seconds_between_iters=(
            _coerce_int(raw.get("sleep_seconds_between_iters"), None)
            if raw.get("sleep_seconds_between_iters") is not None
            else None
        ),
        runner_timeout_seconds=(
            _coerce_int(raw.get("runner_timeout_seconds"), None)
            if raw.get("runner_timeout_seconds") is not None
            else None
        ),
        max_attempts_per_task=(
            _coerce_int(raw.get("max_attempts_per_task"), None)
            if raw.get("max_attempts_per_task") is not None
            else None
        ),
        skip_blocked_tasks=(
            _coerce_bool(raw.get("skip_blocked_tasks"), None)
            if raw.get("skip_blocked_tasks") is not None
            else None
        ),
    )


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
    harness_raw = data.get("harness", {}) or {}
    supervisor_raw = data.get("supervisor", {}) or {}

    mode_name = _normalize_mode_name(loop_raw.get("mode"), "speed")

    modes_raw = loop_raw.get("modes", {}) or {}
    if not isinstance(modes_raw, dict):
        modes_raw = {}
    modes: Dict[str, LoopModeConfig] = _default_loop_modes()
    for name, raw in modes_raw.items():
        if not isinstance(name, str):
            continue
        key = name.strip().lower()
        if not key:
            continue
        if key not in _LOOP_MODE_NAMES:
            raise ValueError(
                f"Invalid loop mode: {key!r}. "
                f"Must be one of: {', '.join(_LOOP_MODE_NAMES)}."
            )
        modes[key] = _parse_loop_mode_config(raw)

    if mode_name not in _LOOP_MODE_NAMES:
        raise ValueError(
            f"Invalid loop.mode: {mode_name!r}. "
            f"Must be one of: {', '.join(_LOOP_MODE_NAMES)}."
        )

    loop = LoopConfig(
        max_iterations=_coerce_int(loop_raw.get("max_iterations"), 10),
        no_progress_limit=_coerce_int(loop_raw.get("no_progress_limit"), 3),
        rate_limit_per_hour=_coerce_int(loop_raw.get("rate_limit_per_hour"), 0),
        sleep_seconds_between_iters=_coerce_int(
            loop_raw.get("sleep_seconds_between_iters"), 0
        ),
        runner_timeout_seconds=_coerce_int(loop_raw.get("runner_timeout_seconds"), 900),
        max_attempts_per_task=_coerce_int(loop_raw.get("max_attempts_per_task"), 3),
        skip_blocked_tasks=_coerce_bool(loop_raw.get("skip_blocked_tasks"), True),
        mode=mode_name,
        modes=modes,
    )

    # Default file layout: all durable memory files live in .ralph/
    files = FilesConfig(
        prd=str(files_raw.get("prd", FilesConfig.prd)),
        progress=str(files_raw.get("progress", FilesConfig.progress)),
        prompt=str(files_raw.get("prompt", FilesConfig.prompt)),
        plan=str(files_raw.get("plan", FilesConfig.plan)),
        judge=str(files_raw.get("judge", FilesConfig.judge)),
        review=str(files_raw.get("review", FilesConfig.review)),
        agents=str(files_raw.get("agents", FilesConfig.agents)),
        specs_dir=str(
            files_raw.get("specs_dir", files_raw.get("specsDir", FilesConfig.specs_dir))
        ),
        feedback=str(files_raw.get("feedback", FilesConfig.feedback)),
    )

    # Resolve common filename mismatches automatically (prevents hard crashes).
    files = FilesConfig(
        prd=_resolve_existing(
            project_root,
            files.prd,
            [
                ".ralph/PRD.md",
                "PRD.md",
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
        plan=_resolve_existing(
            project_root,
            files.plan,
            [".ralph/PROMPT_plan.md", "PROMPT_plan.md"],
        ),
        judge=_resolve_existing(
            project_root,
            files.judge,
            [".ralph/PROMPT_judge.md", "PROMPT_judge.md"],
        ),
        review=_resolve_existing(
            project_root,
            files.review,
            [".ralph/PROMPT_review.md", "PROMPT_review.md"],
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
        feedback=_resolve_existing(
            project_root,
            files.feedback,
            [".ralph/FEEDBACK.md", "FEEDBACK.md"],
        ),
    )

    # Default runner argv are intentionally conservative and easy to edit.
    # IMPORTANT: Codex expects the prompt either as the PROMPT positional argument or via stdin.
    # Using '-' is the most robust way to feed long prompts (no quoting issues).
    default_runners: Dict[str, RunnerConfig] = {
        "codex": RunnerConfig(argv=["codex", "exec", "--full-auto", "-"]),
        "claude": RunnerConfig(argv=["claude", "-p"]),
        "copilot": RunnerConfig(
            argv=["gh", "copilot", "suggest", "--type", "shell", "--prompt"]
        ),
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

    review_raw = gates_raw.get("review", {}) or {}
    if not isinstance(review_raw, dict):
        review_raw = {}
    review = ReviewConfig(
        enabled=_coerce_bool(review_raw.get("enabled"), False),
        backend=str(review_raw.get("backend", "runner")).strip() or "runner",
        agent=str(review_raw.get("agent", "claude")).strip() or "claude",
        prompt=str(review_raw.get("prompt", files.review)),
        max_diff_chars=_coerce_int(review_raw.get("max_diff_chars"), 30000),
        required_token=str(review_raw.get("required_token", "SHIP")).strip() or "SHIP",
    )

    prek_raw = gates_raw.get("prek", {}) or {}
    if not isinstance(prek_raw, dict):
        prek_raw = {}
    prek_argv_raw = prek_raw.get("argv")
    if isinstance(prek_argv_raw, list):
        prek_argv = [str(x) for x in prek_argv_raw]
    elif isinstance(prek_argv_raw, str):
        prek_argv = [prek_argv_raw]
    else:
        prek_argv = ["prek", "run", "--all-files"]
    prek = PrekConfig(
        enabled=_coerce_bool(prek_raw.get("enabled"), False),
        argv=prek_argv,
    )

    smart_raw = gates_raw.get("smart", {}) or {}
    if not isinstance(smart_raw, dict):
        smart_raw = {}
    skip_raw = smart_raw.get("skip_gates_for", smart_raw.get("skipGatesFor", []))
    skip_gates_for: List[str] = []
    if isinstance(skip_raw, list):
        skip_gates_for = [str(x) for x in skip_raw if str(x).strip()]
    elif isinstance(skip_raw, str) and skip_raw.strip():
        skip_gates_for = [skip_raw.strip()]
    smart = GatesSmartConfig(
        enabled=_coerce_bool(
            smart_raw.get("enabled", gates_raw.get("smart_enabled")), False
        ),
        skip_gates_for=skip_gates_for,
    )

    gates = GatesConfig(
        commands=gate_cmds,
        llm_judge=llm_judge,
        review=review,
        prek=prek,
        smart=smart,
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
    exclude_labels = _parse_string_list(exclude_labels_raw, ["blocked"])

    # Parse add_labels_on_start list
    add_labels_on_start_raw = github_raw.get("add_labels_on_start", ["in-progress"])
    add_labels_on_start = _parse_string_list(add_labels_on_start_raw, ["in-progress"])

    # Parse add_labels_on_done list
    add_labels_on_done_raw = github_raw.get("add_labels_on_done", ["completed"])
    add_labels_on_done = _parse_string_list(add_labels_on_done_raw, ["completed"])

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

    # Parse Web tracker configuration
    web_raw = tracker_raw.get("web", {}) or {}
    if not isinstance(web_raw, dict):
        web_raw = {}

    web_config = WebTrackerConfig(
        base_url=str(web_raw.get("base_url", "")),
        sitemap_url=str(web_raw.get("sitemap_url", "")),
        crawl_depth=_coerce_int(web_raw.get("crawl_depth"), 2),
        max_pages=_coerce_int(web_raw.get("max_pages"), 100),
        api_discovery=_coerce_bool(web_raw.get("api_discovery"), True),
        js_analysis=_coerce_bool(web_raw.get("js_analysis"), True),
        normalize_hashes=_coerce_bool(web_raw.get("normalize_hashes"), True),
        headless_nav=_coerce_bool(web_raw.get("headless_nav"), False),
        cache_ttl_seconds=_coerce_int(web_raw.get("cache_ttl_seconds"), 3600),
        output_path=str(web_raw.get("output_path", ".ralph/web_analysis.json")),
    )

    tracker = TrackerConfig(
        kind=str(tracker_raw.get("kind", TrackerConfig.kind)).strip() or "auto",
        plugin=str(
            tracker_raw.get("plugin", tracker_raw.get("plugin_path", ""))
        ).strip(),
        github=github_config,
        web=web_config,
    )

    repoprompt_raw = data.get("repoprompt", data.get("repo_prompt", {})) or {}
    if not isinstance(repoprompt_raw, dict):
        repoprompt_raw = {}
    repoprompt = RepoPromptConfig(
        enabled=_coerce_bool(repoprompt_raw.get("enabled"), False),
        required=_coerce_bool(repoprompt_raw.get("required"), False),
        cli=str(repoprompt_raw.get("cli", "rp-cli")),
        window_id=(
            int(repoprompt_raw.get("window_id"))
            if repoprompt_raw.get("window_id") is not None
            else None
        ),
        tab=str(repoprompt_raw.get("tab", "")),
        workspace=str(repoprompt_raw.get("workspace", "")),
        builder_type=str(repoprompt_raw.get("builder_type", "clarify")),
        copy_preset=str(repoprompt_raw.get("copy_preset", "")),
        timeout_seconds=_coerce_int(repoprompt_raw.get("timeout_seconds"), 300),
        fail_open=_coerce_bool(repoprompt_raw.get("fail_open"), True),
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

    # Parse diagnostics configuration
    diagnostics_raw = data.get("diagnostics", {}) or {}
    if not isinstance(diagnostics_raw, dict):
        diagnostics_raw = {}

    diagnostics = DiagnosticsConfig(
        enabled=_coerce_bool(diagnostics_raw.get("enabled"), True),
        check_gates=_coerce_bool(diagnostics_raw.get("check_gates"), True),
        validate_prd=_coerce_bool(diagnostics_raw.get("validate_prd"), True),
    )

    # Parse stats configuration
    stats_raw = data.get("stats", {}) or {}
    if not isinstance(stats_raw, dict):
        stats_raw = {}

    stats = StatsConfig(
        track_duration=_coerce_bool(stats_raw.get("track_duration"), True),
        track_cost=_coerce_bool(stats_raw.get("track_cost"), False),
    )

    # Parse watch configuration
    watch_raw = data.get("watch", {}) or {}
    if not isinstance(watch_raw, dict):
        watch_raw = {}

    # Parse watch patterns
    patterns_raw = watch_raw.get("patterns", ["**/*.py", "**/*.md"])
    watch_patterns = _parse_string_list(patterns_raw, ["**/*.py", "**/*.md"])

    watch = WatchConfig(
        enabled=_coerce_bool(watch_raw.get("enabled"), False),
        patterns=watch_patterns,
        debounce_ms=_coerce_int(watch_raw.get("debounce_ms"), 500),
        auto_commit=_coerce_bool(watch_raw.get("auto_commit"), False),
    )

    # Parse harness configuration
    if not isinstance(harness_raw, dict):
        harness_raw = {}
    harness_replay_raw = harness_raw.get("replay", {}) or {}
    if not isinstance(harness_replay_raw, dict):
        harness_replay_raw = {}
    harness_retention_raw = harness_raw.get("retention", {}) or {}
    if not isinstance(harness_retention_raw, dict):
        harness_retention_raw = {}
    harness_buckets_raw = harness_raw.get("buckets", {}) or {}
    if not isinstance(harness_buckets_raw, dict):
        harness_buckets_raw = {}
    harness_ci_raw = harness_raw.get("ci", {}) or {}
    if not isinstance(harness_ci_raw, dict):
        harness_ci_raw = {}

    replay_isolation = str(
        harness_replay_raw.get("default_isolation", "worktree")
    ).strip().lower()
    if replay_isolation not in {"worktree", "snapshot"}:
        replay_isolation = "worktree"

    ci_execution_mode = str(
        harness_ci_raw.get("execution_mode", "historical")
    ).strip().lower()
    if ci_execution_mode not in {"historical", "live"}:
        ci_execution_mode = "historical"

    baseline_missing_policy = str(
        harness_ci_raw.get("baseline_missing_policy", "fail")
    ).strip().lower()
    if baseline_missing_policy not in {"fail", "warn"}:
        baseline_missing_policy = "fail"

    regression_threshold_raw = harness_raw.get("regression_threshold", 0.05)
    try:
        regression_threshold = float(regression_threshold_raw)
    except (TypeError, ValueError):
        regression_threshold = 0.05
    if regression_threshold < 0:
        regression_threshold = 0.0
    if regression_threshold > 1:
        regression_threshold = 1.0

    max_cases_per_task = _coerce_int(harness_raw.get("max_cases_per_task"), 2)
    if max_cases_per_task < 0:
        max_cases_per_task = 0

    small_max_seconds = _coerce_int(harness_buckets_raw.get("small_max_seconds"), 120)
    if small_max_seconds < 1:
        small_max_seconds = 1

    medium_max_seconds = _coerce_int(
        harness_buckets_raw.get("medium_max_seconds"), 600
    )
    if medium_max_seconds < small_max_seconds:
        medium_max_seconds = small_max_seconds

    harness = HarnessConfig(
        enabled=_coerce_bool(harness_raw.get("enabled"), False),
        owner=str(harness_raw.get("owner", "engineering")).strip() or "engineering",
        dataset_path=str(
            harness_raw.get("dataset_path", ".ralph/harness/cases.json")
        ),
        pinned_dataset_path=str(
            harness_raw.get("pinned_dataset_path", ".ralph/harness/pinned.json")
        ),
        runs_dir=str(harness_raw.get("runs_dir", ".ralph/harness/runs")),
        baseline_run_path=str(
            harness_raw.get("baseline_run_path", ".ralph/harness/runs/baseline.json")
        ),
        append_pinned_by_default=_coerce_bool(
            harness_raw.get("append_pinned_by_default"), True
        ),
        max_cases_per_task=max_cases_per_task,
        default_days=_coerce_int(harness_raw.get("default_days"), 30),
        default_limit=_coerce_int(harness_raw.get("default_limit"), 200),
        regression_threshold=regression_threshold,
        buckets=HarnessBucketConfig(
            small_max_seconds=small_max_seconds,
            medium_max_seconds=medium_max_seconds,
        ),
        ci=HarnessCIConfig(
            enabled=_coerce_bool(harness_ci_raw.get("enabled"), True),
            execution_mode=ci_execution_mode,
            max_cases=max(1, _coerce_int(harness_ci_raw.get("max_cases"), 200)),
            enforce_regression_threshold=_coerce_bool(
                harness_ci_raw.get("enforce_regression_threshold"), True
            ),
            require_baseline=_coerce_bool(
                harness_ci_raw.get("require_baseline"), True
            ),
            baseline_missing_policy=baseline_missing_policy,
        ),
        replay=HarnessReplayConfig(
            default_isolation=replay_isolation,
            max_case_timeout_seconds=_coerce_int(
                harness_replay_raw.get("max_case_timeout_seconds"), 900
            ),
        ),
        retention=HarnessRetentionConfig(
            cases_days=_coerce_int(harness_retention_raw.get("cases_days"), 30),
            runs_days=_coerce_int(harness_retention_raw.get("runs_days"), 30),
            keep_last_runs=_coerce_int(
                harness_retention_raw.get("keep_last_runs"), 20
            ),
            pinned_days=_coerce_int(harness_retention_raw.get("pinned_days"), 90),
        ),
    )

    # Parse supervisor configuration (used by `ralph supervise`)
    if not isinstance(supervisor_raw, dict):
        supervisor_raw = {}

    on_no_prog = str(supervisor_raw.get("on_no_progress_limit", "stop")).strip().lower()
    if on_no_prog not in {"stop", "continue"}:
        on_no_prog = "stop"

    on_rate = str(supervisor_raw.get("on_rate_limit", "wait")).strip().lower()
    if on_rate not in {"wait", "stop"}:
        on_rate = "wait"

    notify_backend = str(supervisor_raw.get("notify_backend", "auto")).strip().lower()
    if notify_backend not in {"auto", "macos", "linux", "windows", "command", "none"}:
        notify_backend = "auto"

    supervisor = SupervisorConfig(
        heartbeat_seconds=_coerce_int(supervisor_raw.get("heartbeat_seconds"), 60),
        sleep_seconds_between_runs=_coerce_int(
            supervisor_raw.get("sleep_seconds_between_runs"), 5
        ),
        max_runtime_seconds=_coerce_int(supervisor_raw.get("max_runtime_seconds"), 0),
        on_no_progress_limit=on_no_prog,
        on_rate_limit=on_rate,
        notify_enabled=_coerce_bool(supervisor_raw.get("notify_enabled"), True),
        notify_events=_parse_string_list(
            supervisor_raw.get("notify_events"), ["complete", "stopped", "error"]
        ),
        notify_backend=notify_backend,
        notify_command_argv=_parse_string_list(
            supervisor_raw.get("notify_command_argv"), []
        ),
    )

    # Parse progress configuration
    progress_raw = data.get("progress", {}) or {}
    if not isinstance(progress_raw, dict):
        progress_raw = {}

    progress = ProgressConfig(
        show_velocity=_coerce_bool(progress_raw.get("show_velocity"), True),
        show_burndown=_coerce_bool(progress_raw.get("show_burndown"), True),
        chart_width=_coerce_int(progress_raw.get("chart_width"), 60),
    )

    # Parse templates configuration
    templates_raw = data.get("templates", {}) or {}
    if not isinstance(templates_raw, dict):
        templates_raw = {}

    # Parse builtin templates list
    builtin_raw = templates_raw.get("builtin", ["bug-fix", "feature", "refactor"])
    builtin_templates = _parse_string_list(builtin_raw, ["bug-fix", "feature", "refactor"])

    templates = TemplatesConfig(
        builtin=builtin_templates,
        custom_dir=str(templates_raw.get("custom_dir", ".ralph/templates")),
    )

    # Parse output configuration
    output_raw = data.get("output", {}) or {}
    if not isinstance(output_raw, dict):
        output_raw = {}

    # Validate verbosity
    verbosity = str(output_raw.get("verbosity", "normal")).strip().lower()
    if verbosity not in {"quiet", "normal", "verbose"}:
        verbosity = "normal"

    # Validate format
    output_format = str(output_raw.get("format", "text")).strip().lower()
    if output_format not in {"text", "json"}:
        output_format = "text"

    output = OutputControlConfig(
        verbosity=verbosity,
        format=output_format,
    )

    # Parse prompt configuration
    prompt_raw = data.get("prompt", {}) or {}
    if not isinstance(prompt_raw, dict):
        prompt_raw = {}

    prompt = PromptConfig(
        enable_limits=_coerce_bool(prompt_raw.get("enable_limits"), False),
        max_specs_files=_coerce_int(prompt_raw.get("max_specs_files"), 20),
        max_specs_chars=_coerce_int(prompt_raw.get("max_specs_chars"), 100000),
        max_single_spec_chars=_coerce_int(prompt_raw.get("max_single_spec_chars"), 50000),
        truncate_long_specs=_coerce_bool(prompt_raw.get("truncate_long_specs"), True),
        specs_inclusion_order=str(prompt_raw.get("specs_inclusion_order", "sorted")),
        # Context management settings
        context_total_budget=_coerce_int(prompt_raw.get("context_total_budget"), 50000),
        context_progress_max_lines=_coerce_int(prompt_raw.get("context_progress_max_lines"), 100),
        context_progress_max_chars=_coerce_int(prompt_raw.get("context_progress_max_chars"), 10000),
        context_prune_on_build=_coerce_bool(prompt_raw.get("context_prune_on_build"), True),
        context_archive_old_entries=_coerce_bool(prompt_raw.get("context_archive_old_entries"), True),
        context_archive_dir=str(prompt_raw.get("context_archive_dir", "archive/progress")),
    )

    # Parse authorization configuration
    auth_raw = data.get("authorization", {}) or {}
    if not isinstance(auth_raw, dict):
        auth_raw = {}

    # Import EnforcementMode for type-safe enforcement mode handling
    from .authorization import EnforcementMode

    # Validate enforcement_mode value using enum
    mode_str = str(auth_raw.get("enforcement_mode", "warn")).lower()
    try:
        enforcement_mode = EnforcementMode(mode_str)
    except ValueError:
        enforcement_mode = EnforcementMode.WARN  # Default to warn if invalid

    authorization = AuthorizationConfig(
        enabled=_coerce_bool(auth_raw.get("enabled"), False),
        fallback_to_full_auto=_coerce_bool(auth_raw.get("fallback_to_full_auto"), False),
        permissions_file=str(auth_raw.get("permissions_file", ".ralph/permissions.json")),
        enforcement_mode=enforcement_mode,
    )

    # Parse state configuration
    state_raw = data.get("state", {}) or {}
    if not isinstance(state_raw, dict):
        state_raw = {}

    state = StateConfig(
        auto_cleanup_stale=_coerce_bool(state_raw.get("auto_cleanup_stale"), False),
        validate_on_startup=_coerce_bool(state_raw.get("validate_on_startup"), True),
        warn_on_prd_modified=_coerce_bool(state_raw.get("warn_on_prd_modified"), True),
        protect_current_task=_coerce_bool(state_raw.get("protect_current_task"), True),
        protect_recent_hours=_coerce_int(state_raw.get("protect_recent_hours"), 1),
    )

    # Parse init configuration
    init_raw = data.get("init", {}) or {}
    if not isinstance(init_raw, dict):
        init_raw = {}

    # Parse preserve_sections list
    preserve_raw = init_raw.get("preserve_sections", InitConfig().preserve_sections)
    if isinstance(preserve_raw, list):
        preserve_sections = [str(x) for x in preserve_raw]
    else:
        preserve_sections = InitConfig().preserve_sections

    # Parse merge_sections list
    merge_raw = init_raw.get("merge_sections", InitConfig().merge_sections)
    if isinstance(merge_raw, list):
        merge_sections = [str(x) for x in merge_raw]
    else:
        merge_sections = InitConfig().merge_sections

    init = InitConfig(
        merge_config_on_reinit=_coerce_bool(
            init_raw.get("merge_config_on_reinit"), True
        ),
        merge_strategy=str(init_raw.get("merge_strategy", "user_wins")),
        preserve_sections=preserve_sections,
        merge_sections=merge_sections,
    )

    # Parse adaptive_timeout configuration
    at_raw = data.get("adaptive_timeout", {}) or {}
    if not isinstance(at_raw, dict):
        at_raw = {}

    adaptive_timeout = AdaptiveTimeoutConfig(
        enabled=_coerce_bool(at_raw.get("enabled"), True),
        enable_complexity_scaling=_coerce_bool(
            at_raw.get("enable_complexity_scaling"), True
        ),
        enable_failure_scaling=_coerce_bool(at_raw.get("enable_failure_scaling"), True),
        max_timeout=_coerce_int(at_raw.get("max_timeout"), 3600),
        min_timeout=_coerce_int(at_raw.get("min_timeout"), 60),
        timeout_multiplier_per_failure=float(
            at_raw.get("timeout_multiplier_per_failure", 1.5)
        ),
        default_mode_timeout=_coerce_int(at_raw.get("default_mode_timeout"), 120),
    )

    # Parse unblock configuration
    unblock_raw = data.get("unblock", {}) or {}
    if not isinstance(unblock_raw, dict):
        unblock_raw = {}

    unblock = UnblockConfig(
        auto_suggest=_coerce_bool(unblock_raw.get("auto_suggest"), True),
        max_auto_unblock_attempts=_coerce_int(
            unblock_raw.get("max_auto_unblock_attempts"), 1
        ),
        require_reason=_coerce_bool(unblock_raw.get("require_reason"), True),
        allow_batch_unblock=_coerce_bool(unblock_raw.get("allow_batch_unblock"), True),
    )

    return Config(
        loop=loop,
        files=files,
        runners=runners,
        gates=gates,
        git=git,
        tracker=tracker,
        parallel=parallel,
        repoprompt=repoprompt,
        diagnostics=diagnostics,
        stats=stats,
        watch=watch,
        harness=harness,
        supervisor=supervisor,
        progress=progress,
        templates=templates,
        output=output,
        prompt=prompt,
        state=state,
        authorization=authorization,
        init=init,
        adaptive_timeout=adaptive_timeout,
        unblock=unblock,
    )
