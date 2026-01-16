# Ralph-Gold v0.7.0: Parallel Execution + GitHub Issues - Design

## Architecture Overview

v0.7.0 adds six major subsystems to ralph-gold:

1. **Tracker Abstraction Layer** - Unified interface for YAML, GitHub Issues, JSON, Markdown
2. **Parallel Execution Engine** - Worker pool + git worktree management
3. **Enhanced State Management** - Track parallel workers, groups, and metrics
4. **Lifecycle Hooks System** - Pre/post execution hooks for custom workflows
5. **Session Management** - Resumable loops with isolated session state
6. **Feedback Channel** - Runtime feedback injection for course correction

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Ralph CLI / TUI                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Loop Orchestrator                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Sequential  │  │   Parallel   │  │    State     │     │
│  │   Executor   │  │   Executor   │  │   Manager    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Hooks      │  │   Session    │  │  Feedback    │     │
│  │   Manager    │  │   Manager    │  │   Channel    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Tracker Interface                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │   YAML   │ │  GitHub  │ │   JSON   │ │ Markdown │      │
│  │ Tracker  │ │  Issues  │ │ Tracker  │ │ Tracker  │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  Git Worktree Manager                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Worktree   │  │    Branch    │  │    Merge     │     │
│  │   Lifecycle  │  │   Manager    │  │   Manager    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Component Designs

### 1. Tracker Abstraction Layer

**File:** `src/ralph_gold/trackers.py` (extend existing)

**Interface Extension:**

```python
class Tracker(ABC):
    """Base tracker interface (existing)."""
    
    @abstractmethod
    def claim_next_task(self) -> Optional[SelectedTask]:
        """Claim the next available task."""
        pass
    
    @abstractmethod
    def is_task_done(self, task_id: str) -> bool:
        """Check if a task is marked done."""
        pass
    
    # NEW: Parallel support
    def get_parallel_groups(self) -> dict[str, list[SelectedTask]]:
        """Return tasks grouped by parallel group.
        
        Default implementation: all tasks in "default" group.
        Trackers that support grouping override this.
        """
        return {"default": self.get_all_tasks()}
    
    def get_all_tasks(self) -> list[SelectedTask]:
        """Return all tasks (for parallel scheduling)."""
        raise NotImplementedError("Parallel mode requires get_all_tasks()")
```

**New Trackers:**

```python
# src/ralph_gold/trackers/yaml_tracker.py
class YamlTracker(Tracker):
    """YAML-based task tracker with native parallel grouping."""
    
    def __init__(self, project_root: Path, cfg: Config):
        self.path = project_root / cfg.files.prd
        self.data = self._load_and_validate()
    
    def _load_and_validate(self) -> dict:
        """Load YAML and validate against schema."""
        with open(self.path) as f:
            data = yaml.safe_load(f)
        
        # Validate schema
        if data.get("version") != 1:
            raise ValueError("Unsupported YAML version")
        
        if "tasks" not in data or not isinstance(data["tasks"], list):
            raise ValueError("YAML must have 'tasks' list")
        
        return data
    
    def get_parallel_groups(self) -> dict[str, list[SelectedTask]]:
        """Group tasks by 'group' field."""
        groups: dict[str, list[SelectedTask]] = {}
        
        for task_data in self.data["tasks"]:
            if task_data.get("completed"):
                continue
            
            group = str(task_data.get("group", "default"))
            task = self._task_from_data(task_data)
            
            if group not in groups:
                groups[group] = []
            groups[group].append(task)
        
        return groups
```

```python
# src/ralph_gold/trackers/github_issues.py
class GitHubIssuesTracker(Tracker):
    """GitHub Issues-based task tracker."""
    
    def __init__(self, project_root: Path, cfg: Config):
        self.repo = cfg.tracker.github.repo
        self.label_filter = cfg.tracker.github.label_filter
        self.exclude_labels = cfg.tracker.github.exclude_labels
        self.cache_path = project_root / ".ralph" / "github_cache.json"
        self.auth = self._setup_auth(cfg)
        self._sync_cache()
    
    def _setup_auth(self, cfg: Config) -> GitHubAuth:
        """Setup GitHub authentication (gh CLI or token)."""
        if cfg.tracker.github.auth_method == "gh_cli":
            return GhCliAuth()
        else:
            token = os.getenv(cfg.tracker.github.token_env)
            return TokenAuth(token)
    
    def _sync_cache(self) -> None:
        """Fetch issues from GitHub and cache locally."""
        # Check cache age
        if self._cache_is_fresh():
            return
        
        # Fetch issues via auth method
        issues = self.auth.list_issues(
            repo=self.repo,
            labels=[self.label_filter],
            state="open"
        )
        
        # Filter out excluded labels
        filtered = [
            issue for issue in issues
            if not any(label in issue["labels"] for label in self.exclude_labels)
        ]
        
        # Save to cache
        self._save_cache(filtered)
    
    def claim_next_task(self) -> Optional[SelectedTask]:
        """Return highest priority open issue."""
        self._sync_cache()
        issues = self._load_cache()
        
        if not issues:
            return None
        
        # Sort by priority (milestone, then created date)
        sorted_issues = sorted(
            issues,
            key=lambda i: (i.get("milestone", {}).get("number", 999), i["created_at"])
        )
        
        return self._issue_to_task(sorted_issues[0])
```

### 2. Parallel Execution Engine

**File:** `src/ralph_gold/parallel.py` (new)

**Core Classes:**

```python
@dataclass
class WorkerState:
    """State of a single parallel worker."""
    worker_id: int
    task: SelectedTask
    worktree_path: Path
    branch_name: str
    status: str  # queued|running|success|failed
    started_at: Optional[float]
    completed_at: Optional[float]
    iteration_result: Optional[IterationResult]
    error: Optional[str]


class WorktreeManager:
    """Manages git worktrees for parallel execution."""
    
    def __init__(self, project_root: Path, worktree_root: Path):
        self.project_root = project_root
        self.worktree_root = worktree_root
        self.worktree_root.mkdir(parents=True, exist_ok=True)
    
    def create_worktree(self, task: SelectedTask, worker_id: int) -> tuple[Path, str]:
        """Create isolated worktree for task.
        
        Returns: (worktree_path, branch_name)
        """
        # Generate unique branch name
        branch_name = self._generate_branch_name(task, worker_id)
        
        # Generate worktree path
        worktree_path = self.worktree_root / f"worker-{worker_id}-{task.id}"
        
        # Create worktree
        subprocess.run(
            ["git", "worktree", "add", "-b", branch_name, str(worktree_path)],
            cwd=str(self.project_root),
            check=True,
            capture_output=True
        )
        
        return worktree_path, branch_name
    
    def remove_worktree(self, worktree_path: Path) -> None:
        """Remove worktree and clean up."""
        subprocess.run(
            ["git", "worktree", "remove", str(worktree_path), "--force"],
            cwd=str(self.project_root),
            check=True,
            capture_output=True
        )
```

```python
class ParallelExecutor:
    """Executes tasks in parallel using worker pool."""
    
    def __init__(self, project_root: Path, cfg: Config):
        self.project_root = project_root
        self.cfg = cfg
        self.worktree_mgr = WorktreeManager(
            project_root,
            project_root / cfg.parallel.worktree_root
        )
        self.workers: dict[int, WorkerState] = {}
        self.executor = ThreadPoolExecutor(max_workers=cfg.parallel.max_workers)
    
    def run_parallel(self, agent: str, tracker: Tracker) -> list[IterationResult]:
        """Execute tasks in parallel."""
        # Get parallel groups
        groups = tracker.get_parallel_groups()
        
        # Schedule tasks
        if self.cfg.parallel.strategy == "queue":
            tasks = self._flatten_groups(groups)
        else:  # "group"
            tasks = self._schedule_by_groups(groups)
        
        # Execute workers
        futures = []
        for worker_id, task in enumerate(tasks):
            future = self.executor.submit(
                self._run_worker,
                worker_id=worker_id,
                task=task,
                agent=agent
            )
            futures.append(future)
        
        # Wait for completion
        results = []
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                # Log worker failure
                pass
        
        return results
    
    def _run_worker(self, worker_id: int, task: SelectedTask, agent: str) -> IterationResult:
        """Run single worker in isolated worktree."""
        # Create worktree
        worktree_path, branch_name = self.worktree_mgr.create_worktree(task, worker_id)
        
        # Initialize worker state
        worker = WorkerState(
            worker_id=worker_id,
            task=task,
            worktree_path=worktree_path,
            branch_name=branch_name,
            status="running",
            started_at=time.time(),
            completed_at=None,
            iteration_result=None,
            error=None
        )
        self.workers[worker_id] = worker
        
        try:
            # Run iteration in worktree
            result = run_iteration(
                project_root=worktree_path,
                agent=agent,
                cfg=self.cfg,
                iteration=worker_id + 1,
                task_override=task
            )
            
            worker.status = "success" if result.gates_ok else "failed"
            worker.iteration_result = result
            
            # Handle merge if successful
            if result.gates_ok and self.cfg.parallel.merge_policy == "auto_merge":
                self._merge_worker(worker)
            
            return result
            
        except Exception as e:
            worker.status = "failed"
            worker.error = str(e)
            raise
        
        finally:
            worker.completed_at = time.time()
```

### 3. Enhanced State Management

**File:** `src/ralph_gold/loop.py` (extend existing)

**State Schema Extension:**

```python
# .ralph/state.json schema extension
{
  "createdAt": "2024-01-15T10:00:00Z",
  "invocations": [...],
  "noProgressStreak": 0,
  "history": [...],
  
  # NEW: Parallel execution state
  "parallel": {
    "enabled": true,
    "last_run": "2024-01-15T12:00:00Z",
    "workers": [
      {
        "worker_id": 0,
        "task_id": "1",
        "branch": "ralph/worker-0-task-1",
        "worktree": ".ralph/worktrees/worker-0-1",
        "status": "success",
        "started_at": 1705320000.0,
        "completed_at": 1705320120.0,
        "duration_seconds": 120.0,
        "gates_ok": true
      }
    ]
  }
}
```

**Integration with Existing Loop:**

```python
def run_loop(
    project_root: Path,
    agent: str,
    max_iterations: Optional[int] = None,
    cfg: Optional[Config] = None,
    parallel: bool = False
) -> list[IterationResult]:
    """Run loop (sequential or parallel)."""
    cfg = cfg or load_config(project_root)
    tracker = make_tracker(project_root, cfg)
    
    # Parallel mode
    if parallel or cfg.parallel.enabled:
        executor = ParallelExecutor(project_root, cfg)
        return executor.run_parallel(agent, tracker)
    
    # Sequential mode (existing)
    results = []
    for i in range(max_iterations or cfg.loop.max_iterations):
        result = run_iteration(project_root, agent, cfg, i + 1)
        results.append(result)
        if should_exit(result, tracker):
            break
    
    return results
```

### 4. TUI Enhancements

**File:** `src/ralph_gold/tui.py` (extend existing)

**Parallel Status Display:**

```
┌─ Ralph Gold v0.7.0 ─────────────────────────────────────────┐
│ Mode: Parallel (3 workers)                                   │
│ Tracker: YAML (tasks.yaml)                                   │
│ Progress: 5/12 tasks complete                                │
└──────────────────────────────────────────────────────────────┘

┌─ Workers ────────────────────────────────────────────────────┐
│ [0] ✓ Task 1: Auth login      [120s] ralph/worker-0-task-1  │
│ [1] ⚙ Task 2: UI profile      [45s]  ralph/worker-1-task-2  │
│ [2] ✗ Task 3: API endpoint    [90s]  ralph/worker-2-task-3  │
│     └─ Gates failed: typecheck                               │
└──────────────────────────────────────────────────────────────┘

┌─ Actions ────────────────────────────────────────────────────┐
│ [v] View worker logs  [c] Clean worktrees  [q] Quit          │
└──────────────────────────────────────────────────────────────┘
```

**Implementation:**

```python
class ParallelStatusPanel:
    """TUI panel for parallel execution status."""
    
    def render(self, executor: ParallelExecutor) -> str:
        """Render parallel status."""
        lines = []
        lines.append("┌─ Workers " + "─" * 50 + "┐")
        
        for worker_id, worker in executor.workers.items():
            status_icon = self._status_icon(worker.status)
            duration = self._format_duration(worker)
            
            line = f"│ [{worker_id}] {status_icon} {worker.task.title[:20]:<20} "
            line += f"[{duration}] {worker.branch_name[:30]:<30} │"
            lines.append(line)
            
            # Show error if failed
            if worker.error:
                lines.append(f"│     └─ {worker.error[:50]:<50} │")
        
        lines.append("└" + "─" * 60 + "┘")
        return "\n".join(lines)
    
    def _status_icon(self, status: str) -> str:
        return {
            "queued": "⏳",
            "running": "⚙",
            "success": "✓",
            "failed": "✗"
        }.get(status, "?")
```

### 5. Lifecycle Hooks System

**File:** `src/ralph_gold/hooks.py` (new)

**Design Rationale:** Hooks enable extensibility without modifying core loop logic. They allow users to integrate Ralph with existing workflows (Slack notifications, task syncing, cleanup scripts) without requiring plugin development.

**Core Classes:**

```python
@dataclass
class HookConfig:
    """Configuration for a single hook."""
    name: str
    commands: list[str]
    timeout_seconds: int = 30
    continue_on_error: bool = True
    log_output: bool = True


@dataclass
class HooksConfig:
    """Configuration for all lifecycle hooks."""
    pre_run: list[str] = field(default_factory=list)
    start_iteration: list[str] = field(default_factory=list)
    end_iteration: list[str] = field(default_factory=list)
    on_gate_fail: list[str] = field(default_factory=list)
    timeout_seconds: int = 30
    continue_on_error: bool = True
    log_output: bool = True


class HooksManager:
    """Manages lifecycle hook execution."""
    
    def __init__(self, cfg: HooksConfig, project_root: Path):
        self.cfg = cfg
        self.project_root = project_root
        self.log_path = project_root / ".ralph" / "logs" / "hooks.log"
    
    def run_hook(self, hook_type: str, context: dict[str, Any]) -> None:
        """Execute hooks for a specific lifecycle event.
        
        Args:
            hook_type: One of pre_run, start_iteration, end_iteration, on_gate_fail
            context: Context data (iteration number, task ID, etc.)
        """
        commands = getattr(self.cfg, hook_type, [])
        
        if not commands:
            return
        
        self._log(f"Running {hook_type} hooks ({len(commands)} commands)")
        
        for cmd in commands:
            try:
                # Expand context variables in command
                expanded_cmd = self._expand_context(cmd, context)
                
                # Execute with timeout
                result = subprocess.run(
                    expanded_cmd,
                    shell=True,
                    cwd=str(self.project_root),
                    timeout=self.cfg.timeout_seconds,
                    capture_output=True,
                    text=True
                )
                
                if self.cfg.log_output:
                    self._log(f"Hook output: {result.stdout}")
                
                if result.returncode != 0:
                    self._log(f"Hook failed (exit {result.returncode}): {result.stderr}")
                    if not self.cfg.continue_on_error:
                        raise HookExecutionError(f"Hook failed: {cmd}")
                
            except subprocess.TimeoutExpired:
                self._log(f"Hook timed out after {self.cfg.timeout_seconds}s: {cmd}")
                if not self.cfg.continue_on_error:
                    raise
            except Exception as e:
                self._log(f"Hook error: {e}")
                if not self.cfg.continue_on_error:
                    raise
    
    def _expand_context(self, cmd: str, context: dict[str, Any]) -> str:
        """Expand context variables in command string."""
        # Support ${VAR} syntax for context variables
        for key, value in context.items():
            cmd = cmd.replace(f"${{{key}}}", str(value))
        return cmd
    
    def _log(self, message: str) -> None:
        """Log hook execution."""
        timestamp = datetime.now().isoformat()
        with open(self.log_path, "a") as f:
            f.write(f"[{timestamp}] {message}\n")


class HookExecutionError(Exception):
    """Hook execution failed."""
    pass
```

**Integration with Loop:**

```python
def run_loop(
    project_root: Path,
    agent: str,
    max_iterations: Optional[int] = None,
    cfg: Optional[Config] = None,
    parallel: bool = False,
    until_done: bool = False
) -> list[IterationResult]:
    """Run loop (sequential or parallel)."""
    cfg = cfg or load_config(project_root)
    tracker = make_tracker(project_root, cfg)
    hooks = HooksManager(cfg.hooks, project_root)
    
    # Pre-run hooks
    hooks.run_hook("pre_run", {"agent": agent})
    
    # Determine loop condition
    if until_done:
        # Run until tracker has no more tasks
        iteration = 0
        results = []
        while True:
            iteration += 1
            
            # Check if tracker has tasks
            task = tracker.claim_next_task()
            if task is None:
                break
            
            # Start iteration hooks
            hooks.run_hook("start_iteration", {
                "iteration": iteration,
                "task_id": task.id
            })
            
            # Run iteration
            result = run_iteration(project_root, agent, cfg, iteration, task)
            results.append(result)
            
            # End iteration hooks
            hooks.run_hook("end_iteration", {
                "iteration": iteration,
                "task_id": task.id,
                "gates_ok": result.gates_ok
            })
            
            # Gate failure hooks
            if not result.gates_ok:
                hooks.run_hook("on_gate_fail", {
                    "iteration": iteration,
                    "task_id": task.id,
                    "gates": result.gates
                })
        
        return results
    
    # Original max_iterations logic with hooks
    # ... (similar hook integration)
```

### 6. Session Management

**File:** `src/ralph_gold/session.py` (new)

**Design Rationale:** Sessions enable resumable loops and better debugging. Each run gets isolated logs and state, making it easy to audit past runs and resume interrupted work.

**Core Classes:**

```python
@dataclass
class SessionMetadata:
    """Metadata for a single session."""
    session_id: str
    started_at: str
    ended_at: Optional[str]
    agent: str
    tracker_kind: str
    parallel_enabled: bool
    max_workers: int
    iterations_completed: int
    tasks_completed: int
    gates_passed: int
    gates_failed: int
    status: str  # running|completed|interrupted|failed


class SessionManager:
    """Manages session lifecycle and state."""
    
    def __init__(self, project_root: Path, cfg: Config):
        self.project_root = project_root
        self.cfg = cfg
        self.sessions_root = project_root / ".ralph" / "sessions"
        self.sessions_root.mkdir(parents=True, exist_ok=True)
    
    def create_session(self, agent: str, tracker_kind: str) -> str:
        """Create a new session and return session ID."""
        session_id = self._generate_session_id()
        session_path = self.sessions_root / session_id
        session_path.mkdir(parents=True, exist_ok=True)
        
        # Create session metadata
        metadata = SessionMetadata(
            session_id=session_id,
            started_at=datetime.now().isoformat(),
            ended_at=None,
            agent=agent,
            tracker_kind=tracker_kind,
            parallel_enabled=self.cfg.parallel.enabled,
            max_workers=self.cfg.parallel.max_workers,
            iterations_completed=0,
            tasks_completed=0,
            gates_passed=0,
            gates_failed=0,
            status="running"
        )
        
        self._save_metadata(session_id, metadata)
        return session_id
    
    def resume_session(self, session_id: str) -> SessionMetadata:
        """Resume an existing session."""
        metadata = self._load_metadata(session_id)
        
        if metadata.status == "completed":
            raise ValueError(f"Session {session_id} already completed")
        
        metadata.status = "running"
        self._save_metadata(session_id, metadata)
        return metadata
    
    def complete_session(self, session_id: str, results: list[IterationResult]) -> None:
        """Mark session as complete and update metrics."""
        metadata = self._load_metadata(session_id)
        metadata.ended_at = datetime.now().isoformat()
        metadata.status = "completed"
        metadata.iterations_completed = len(results)
        metadata.gates_passed = sum(1 for r in results if r.gates_ok)
        metadata.gates_failed = sum(1 for r in results if not r.gates_ok)
        self._save_metadata(session_id, metadata)
    
    def list_sessions(self) -> list[SessionMetadata]:
        """List all sessions."""
        sessions = []
        for session_dir in self.sessions_root.iterdir():
            if session_dir.is_dir():
                try:
                    metadata = self._load_metadata(session_dir.name)
                    sessions.append(metadata)
                except Exception:
                    continue
        return sorted(sessions, key=lambda s: s.started_at, reverse=True)
    
    def get_session_log_path(self, session_id: str) -> Path:
        """Get path to session log directory."""
        return self.sessions_root / session_id / "logs"
    
    def clean_old_sessions(self, retention_days: int) -> int:
        """Delete sessions older than retention_days."""
        cutoff = datetime.now() - timedelta(days=retention_days)
        deleted = 0
        
        for session in self.list_sessions():
            started = datetime.fromisoformat(session.started_at)
            if started < cutoff:
                session_path = self.sessions_root / session.session_id
                shutil.rmtree(session_path)
                deleted += 1
        
        return deleted
    
    def _generate_session_id(self) -> str:
        """Generate unique session ID."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        random_suffix = "".join(random.choices(string.ascii_lowercase, k=6))
        return f"{timestamp}-{random_suffix}"
    
    def _save_metadata(self, session_id: str, metadata: SessionMetadata) -> None:
        """Save session metadata."""
        path = self.sessions_root / session_id / "metadata.json"
        with open(path, "w") as f:
            json.dump(asdict(metadata), f, indent=2)
    
    def _load_metadata(self, session_id: str) -> SessionMetadata:
        """Load session metadata."""
        path = self.sessions_root / session_id / "metadata.json"
        with open(path) as f:
            data = json.load(f)
        return SessionMetadata(**data)
```

**Integration with Loop:**

```python
def run_loop(
    project_root: Path,
    agent: str,
    max_iterations: Optional[int] = None,
    cfg: Optional[Config] = None,
    parallel: bool = False,
    until_done: bool = False,
    session_id: Optional[str] = None,
    continue_session: bool = False
) -> list[IterationResult]:
    """Run loop with session management."""
    cfg = cfg or load_config(project_root)
    tracker = make_tracker(project_root, cfg)
    
    # Session management
    if cfg.session.enabled:
        session_mgr = SessionManager(project_root, cfg)
        
        if continue_session:
            # Resume most recent session
            sessions = session_mgr.list_sessions()
            if not sessions:
                raise ValueError("No sessions to resume")
            session_id = sessions[0].session_id
            session_mgr.resume_session(session_id)
        elif session_id:
            # Resume specific session
            session_mgr.resume_session(session_id)
        else:
            # Create new session
            session_id = session_mgr.create_session(agent, cfg.tracker.kind)
        
        # Redirect logs to session directory
        log_path = session_mgr.get_session_log_path(session_id)
        log_path.mkdir(parents=True, exist_ok=True)
    
    # Run loop (existing logic)
    results = []
    # ... loop execution ...
    
    # Complete session
    if cfg.session.enabled:
        session_mgr.complete_session(session_id, results)
    
    return results
```

### 7. Feedback Channel

**File:** `src/ralph_gold/feedback.py` (new)

**Design Rationale:** Feedback enables runtime course correction without stopping the loop. Users can inject guidance while Ralph is running, which is critical for long-running AFK loops.

**Core Classes:**

```python
@dataclass
class FeedbackItem:
    """A single feedback item."""
    id: str
    timestamp: str
    content: str
    task_id: Optional[str]
    iteration: Optional[int]
    author: str


class FeedbackChannel:
    """Manages feedback injection and retrieval."""
    
    def __init__(self, project_root: Path, cfg: Config):
        self.project_root = project_root
        self.cfg = cfg
        self.feedback_path = project_root / cfg.feedback.file
        self.max_items = cfg.feedback.max_items
    
    def add_feedback(
        self,
        content: str,
        task_id: Optional[str] = None,
        author: str = "user"
    ) -> FeedbackItem:
        """Add feedback to the channel."""
        item = FeedbackItem(
            id=self._generate_id(),
            timestamp=datetime.now().isoformat(),
            content=content,
            task_id=task_id,
            iteration=None,
            author=author
        )
        
        # Append to NDJSON file
        with open(self.feedback_path, "a") as f:
            f.write(json.dumps(asdict(item)) + "\n")
        
        return item
    
    def get_recent_feedback(
        self,
        task_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> list[FeedbackItem]:
        """Get recent feedback items."""
        limit = limit or self.max_items
        
        if not self.feedback_path.exists():
            return []
        
        # Read all feedback
        items = []
        with open(self.feedback_path) as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    items.append(FeedbackItem(**data))
        
        # Filter by task_id if specified
        if task_id:
            items = [item for item in items if item.task_id == task_id]
        
        # Return most recent N items
        return items[-limit:]
    
    def clear_feedback(self, task_id: Optional[str] = None) -> int:
        """Clear feedback items."""
        if not self.feedback_path.exists():
            return 0
        
        if task_id is None:
            # Clear all feedback
            count = sum(1 for _ in open(self.feedback_path))
            self.feedback_path.unlink()
            return count
        
        # Clear feedback for specific task
        items = []
        with open(self.feedback_path) as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    if data.get("task_id") != task_id:
                        items.append(line)
        
        # Rewrite file without cleared items
        with open(self.feedback_path, "w") as f:
            f.writelines(items)
        
        return len(items)
    
    def format_for_prompt(self, task_id: Optional[str] = None) -> str:
        """Format recent feedback for inclusion in agent prompt."""
        items = self.get_recent_feedback(task_id=task_id)
        
        if not items:
            return ""
        
        lines = ["## Recent Feedback\n"]
        for item in items:
            timestamp = item.timestamp.split("T")[1][:8]  # HH:MM:SS
            task_info = f" (Task {item.task_id})" if item.task_id else ""
            lines.append(f"- [{timestamp}]{task_info} {item.content}")
        
        return "\n".join(lines)
    
    def _generate_id(self) -> str:
        """Generate unique feedback ID."""
        return str(uuid.uuid4())[:8]
```

**Integration with Loop:**

```python
def run_iteration(
    project_root: Path,
    agent: str,
    cfg: Config,
    iteration: int,
    task: Optional[SelectedTask] = None
) -> IterationResult:
    """Run single iteration with feedback injection."""
    
    # Get feedback for this task
    if cfg.feedback.enabled:
        feedback_channel = FeedbackChannel(project_root, cfg)
        feedback_text = feedback_channel.format_for_prompt(
            task_id=task.id if task else None
        )
    else:
        feedback_text = ""
    
    # Build prompt with feedback
    prompt = build_prompt(
        task=task,
        iteration=iteration,
        feedback=feedback_text  # Inject feedback into prompt
    )
    
    # Run agent
    result = run_agent(agent, prompt, cfg)
    
    return result
```

## Data Flow

### Sequential Execution (Existing)

```
CLI → load_config() → make_tracker() → run_loop()
  → run_iteration() → agent → gates → update_tracker()
  → save_state() → done
```

### Sequential Execution with Hooks and Feedback (New)

```
CLI → load_config() → make_tracker() → session_mgr.create_session()
  → hooks.run_hook("pre_run")
  → run_loop(until_done=True)
    → while tracker.has_tasks():
        → hooks.run_hook("start_iteration")
        → feedback_channel.get_recent_feedback()
        → run_iteration(with_feedback)
        → hooks.run_hook("end_iteration")
        → if gates_fail: hooks.run_hook("on_gate_fail")
  → session_mgr.complete_session()
  → save_state() → done
```

### Parallel Execution (New)

```
CLI --parallel → load_config() → make_tracker()
  → ParallelExecutor.run_parallel()
    → tracker.get_parallel_groups()
    → schedule_tasks()
    → for each task:
        → WorktreeManager.create_worktree()
        → ThreadPoolExecutor.submit(_run_worker)
          → run_iteration(worktree_path)
          → gates in worktree
          → merge_if_success()
        → WorktreeManager.remove_worktree()
    → aggregate_results()
  → save_state() → done
```

### GitHub Issues Sync Flow

```
GitHubIssuesTracker.claim_next_task()
  → _sync_cache()
    → check cache age
    → if stale:
        → auth.list_issues(repo, labels)
        → filter by exclude_labels
        → save to .ralph/github_cache.json
    → load from cache
  → sort by priority
  → return top issue

After task completion:
  → tracker.mark_task_done(task_id)
    → auth.close_issue(issue_number)
    → auth.add_comment(issue_number, summary)
    → auth.add_labels(issue_number, ["completed"])
```

### Feedback Injection Flow

```
User (in separate terminal):
  → ralph feedback "Don't change the public API"
  → FeedbackChannel.add_feedback()
    → append to .ralph/feedback.ndjson

Running loop:
  → run_iteration()
    → FeedbackChannel.get_recent_feedback()
    → format_for_prompt()
    → inject into agent prompt
    → agent sees feedback and adjusts behavior
```

### Session Resume Flow

```
User:
  → ralph run --continue
  → SessionManager.list_sessions()
  → find most recent session
  → SessionManager.resume_session()
  → restore session state
  → continue from last iteration
```

## File Structure

```
src/ralph_gold/
├── __init__.py
├── cli.py                    # Add --parallel, --until-done, --session, --feedback flags
├── config.py                 # Add ParallelConfig, GitHubConfig, HooksConfig, SessionConfig, FeedbackConfig
├── loop.py                   # Extend run_loop() for parallel, hooks, sessions, feedback
├── trackers.py               # Extend Tracker interface
├── trackers/                 # NEW: Tracker implementations
│   ├── __init__.py
│   ├── yaml_tracker.py       # NEW: YAML tracker
│   ├── github_issues.py      # NEW: GitHub Issues tracker
│   ├── json_tracker.py       # Refactor from trackers.py
│   └── markdown_tracker.py   # Refactor from trackers.py
├── parallel.py               # NEW: Parallel execution engine
├── worktree.py               # NEW: Git worktree management
├── github_auth.py            # NEW: GitHub authentication
├── hooks.py                  # NEW: Lifecycle hooks system
├── session.py                # NEW: Session management
├── feedback.py               # NEW: Feedback channel
└── tui.py                    # Add parallel status panel

tests/
├── test_yaml_tracker.py      # NEW
├── test_github_issues.py     # NEW
├── test_parallel.py           # NEW
├── test_worktree.py           # NEW
├── test_hooks.py              # NEW
├── test_session.py            # NEW
├── test_feedback.py           # NEW
└── test_integration_parallel.py  # NEW

.ralph/
├── ralph.toml                # Add [parallel], [tracker.github], [hooks], [session], [feedback]
├── state.json                # Add parallel state
├── github_cache.json         # NEW: GitHub Issues cache
├── feedback.ndjson           # NEW: Feedback items
├── sessions/                 # NEW: Session directories
│   ├── 20240115-120000-abc123/
│   │   ├── metadata.json
│   │   └── logs/
│   └── 20240115-140000-def456/
│       ├── metadata.json
│       └── logs/
├── logs/
│   ├── hooks.log             # NEW: Hook execution logs
│   ├── github-api.log        # NEW: GitHub API logs
│   └── parallel-{timestamp}.log  # NEW: Parallel execution logs
└── worktrees/                # NEW: Parallel worktrees
    ├── worker-0-task-1/
    ├── worker-1-task-2/
    └── worker-2-task-3/
```

## Configuration Design

### Extended Config Schema

```python
@dataclass(frozen=True)
class ParallelConfig:
    enabled: bool = False
    max_workers: int = 3
    worktree_root: str = ".ralph/worktrees"
    strategy: str = "queue"  # queue|group
    merge_policy: str = "manual"  # manual|auto_merge|pr


@dataclass(frozen=True)
class GitHubTrackerConfig:
    repo: str = ""
    auth_method: str = "gh_cli"  # gh_cli|token
    token_env: str = "GITHUB_TOKEN"
    label_filter: str = "ready"
    exclude_labels: list[str] = field(default_factory=lambda: ["blocked"])
    close_on_done: bool = True
    comment_on_done: bool = True
    add_labels_on_start: list[str] = field(default_factory=lambda: ["in-progress"])
    add_labels_on_done: list[str] = field(default_factory=lambda: ["completed"])
    cache_ttl_seconds: int = 300


@dataclass(frozen=True)
class TrackerConfig:
    kind: str = "auto"  # auto|markdown|json|yaml|github_issues
    plugin: str = ""
    github: GitHubTrackerConfig = field(default_factory=GitHubTrackerConfig)


@dataclass(frozen=True)
class HooksConfig:
    """Lifecycle hooks configuration."""
    pre_run: list[str] = field(default_factory=list)
    start_iteration: list[str] = field(default_factory=list)
    end_iteration: list[str] = field(default_factory=list)
    on_gate_fail: list[str] = field(default_factory=list)
    timeout_seconds: int = 30
    continue_on_error: bool = True
    log_output: bool = True


@dataclass(frozen=True)
class LoopConfig:
    """Loop control configuration."""
    max_iterations: int = 10
    until_done: bool = False  # Run until tracker is empty
    timeout_minutes: int = 120
    exit_on_no_progress: bool = True


@dataclass(frozen=True)
class SessionConfig:
    """Session management configuration."""
    enabled: bool = True
    auto_continue: bool = False
    retention_days: int = 30
    log_level: str = "info"


@dataclass(frozen=True)
class FeedbackConfig:
    """Feedback channel configuration."""
    enabled: bool = True
    max_items: int = 10
    format: str = "ndjson"  # ndjson|markdown
    file: str = ".ralph/feedback.ndjson"


@dataclass(frozen=True)
class Config:
    loop: LoopConfig
    files: FilesConfig
    runners: dict[str, RunnerConfig]
    gates: GatesConfig
    git: GitConfig
    tracker: TrackerConfig
    parallel: ParallelConfig
    hooks: HooksConfig  # NEW
    session: SessionConfig  # NEW
    feedback: FeedbackConfig  # NEW
```

## Error Handling

### Worktree Failures

```python
class WorktreeError(Exception):
    """Base exception for worktree operations."""
    pass


class WorktreeCreationError(WorktreeError):
    """Failed to create worktree."""
    pass


class WorktreeMergeError(WorktreeError):
    """Failed to merge worktree."""
    pass


# Handling
try:
    worktree_path, branch = worktree_mgr.create_worktree(task, worker_id)
except WorktreeCreationError as e:
    # Log error
    # Mark worker as failed
    # Continue with other workers
    pass
```

### GitHub API Failures

```python
class GitHubError(Exception):
    """Base exception for GitHub operations."""
    pass


class GitHubAuthError(GitHubError):
    """Authentication failed."""
    pass


class GitHubRateLimitError(GitHubError):
    """Rate limit exceeded."""
    pass


# Handling
try:
    issues = github_tracker._sync_cache()
except GitHubRateLimitError as e:
    # Use cached data
    # Log warning
    # Continue with stale cache
except GitHubAuthError as e:
    # Fail fast
    # Suggest running 'gh auth login'
    raise
```

### Parallel Worker Failures

```python
# Worker failures are isolated
# Failed workers don't affect successful workers
# All worker state is preserved for debugging

def _run_worker(self, worker_id: int, task: SelectedTask, agent: str):
    try:
        result = run_iteration(...)
        return result
    except Exception as e:
        # Log full error
        self.workers[worker_id].status = "failed"
        self.workers[worker_id].error = str(e)
        
        # Preserve worktree for debugging
        # Don't remove worktree on failure
        
        # Re-raise to mark future as failed
        raise
```

### Hook Execution Failures

```python
class HookExecutionError(Exception):
    """Hook execution failed."""
    pass


# Handling
try:
    hooks.run_hook("pre_run", context)
except HookExecutionError as e:
    if cfg.hooks.continue_on_error:
        # Log error and continue
        logger.error(f"Hook failed: {e}")
    else:
        # Fail fast
        raise
```

### Session Errors

```python
class SessionError(Exception):
    """Base exception for session operations."""
    pass


class SessionNotFoundError(SessionError):
    """Session does not exist."""
    pass


class SessionAlreadyCompletedError(SessionError):
    """Cannot resume completed session."""
    pass


# Handling
try:
    session_mgr.resume_session(session_id)
except SessionNotFoundError:
    # Suggest listing available sessions
    print("Session not found. Use 'ralph session list' to see available sessions.")
except SessionAlreadyCompletedError:
    # Suggest creating new session
    print("Session already completed. Start a new session with 'ralph run'.")
```

## Testing Strategy

### Unit Tests

**YAML Tracker:**

```python
def test_yaml_tracker_load():
    """Test YAML loading and validation."""
    
def test_yaml_tracker_parallel_groups():
    """Test parallel group extraction."""
    
def test_yaml_tracker_invalid_schema():
    """Test error handling for invalid YAML."""
```

**GitHub Issues Tracker:**

```python
def test_github_tracker_gh_cli_auth():
    """Test gh CLI authentication."""
    
def test_github_tracker_cache():
    """Test issue caching."""
    
def test_github_tracker_rate_limit():
    """Test rate limit handling."""
    
def test_github_tracker_close_issue():
    """Test issue closing."""
```

**Parallel Executor:**

```python
def test_parallel_executor_queue_strategy():
    """Test queue-based task scheduling."""
    
def test_parallel_executor_group_strategy():
    """Test group-based task scheduling."""
    
def test_parallel_executor_worker_isolation():
    """Test that workers don't interfere."""
    
def test_parallel_executor_failure_handling():
    """Test that one failure doesn't kill all workers."""
```

**Worktree Manager:**

```python
def test_worktree_create():
    """Test worktree creation."""
    
def test_worktree_remove():
    """Test worktree cleanup."""
    
def test_worktree_branch_naming():
    """Test unique branch name generation."""
```

### Integration Tests

```python
def test_end_to_end_yaml_parallel():
    """Test full parallel execution with YAML tracker."""
    # Setup: Create tasks.yaml with 3 tasks in 2 groups
    # Execute: ralph run --parallel --max-workers 2
    # Assert: 
    #   - 2 tasks complete in parallel
    #   - 3rd task runs after first completes
    #   - All worktrees cleaned up
    #   - All branches created
    #   - State.json updated correctly

def test_end_to_end_github_issues():
    """Test full GitHub Issues workflow."""
    # Setup: Mock GitHub API with 3 issues
    # Execute: ralph run --tracker github_issues
    # Assert:
    #   - Issue fetched and cached
    #   - Task executed
    #   - Issue closed on success
    #   - Comment added with results

def test_parallel_with_github_issues():
    """Test parallel execution with GitHub Issues."""
    # Setup: Mock GitHub API with 5 issues, 2 groups
    # Execute: ralph run --parallel --tracker github_issues
    # Assert:
    #   - Issues grouped correctly
    #   - Parallel execution works
    #   - All issues closed on success

def test_parallel_failure_recovery():
    """Test that parallel execution handles failures gracefully."""
    # Setup: 3 tasks, one will fail gates
    # Execute: ralph run --parallel
    # Assert:
    #   - Failed task preserved for debugging
    #   - Successful tasks merged
    #   - State reflects mixed results

def test_hooks_lifecycle():
    """Test lifecycle hooks execution."""
    # Setup: Configure hooks for all lifecycle events
    # Execute: ralph run with hooks
    # Assert:
    #   - pre_run hooks execute before loop
    #   - start_iteration hooks execute at start
    #   - end_iteration hooks execute at end
    #   - on_gate_fail hooks execute on failure
    #   - All hook output logged

def test_session_resume():
    """Test session resumption."""
    # Setup: Start loop, interrupt after 2 iterations
    # Execute: ralph run --continue
    # Assert:
    #   - Session resumes from iteration 3
    #   - Session metadata updated
    #   - Logs preserved in session directory

def test_feedback_injection():
    """Test feedback channel."""
    # Setup: Start loop
    # Execute: ralph feedback "test message" (in parallel)
    # Assert:
    #   - Feedback appears in next iteration prompt
    #   - Feedback persists across iterations
    #   - Task-specific feedback filters correctly

def test_until_done_mode():
    """Test run-until-done mode."""
    # Setup: Tracker with 5 tasks
    # Execute: ralph run --until-done
    # Assert:
    #   - Loop runs exactly 5 iterations
    #   - Loop exits when tracker empty
    #   - All tasks marked complete
```

### Performance Tests

```python
def test_parallel_speedup():
    """Measure parallel execution speedup."""
    # Setup: 3 independent tasks (30s each)
    # Execute: Sequential vs Parallel (3 workers)
    # Assert: Parallel completes in ~30s (vs 90s sequential)
    # Target: 3x speedup

def test_worktree_overhead():
    """Measure worktree creation overhead."""
    # Execute: Create 10 worktrees
    # Assert: Average creation time < 2s per worktree

def test_github_cache_efficiency():
    """Measure GitHub API call reduction."""
    # Setup: 100 issues in cache
    # Execute: 10 iterations with cache
    # Assert: < 2 API calls per iteration (vs 100 without cache)

def test_hook_overhead():
    """Measure hook execution overhead."""
    # Setup: Configure 5 hooks per lifecycle event
    # Execute: 10 iterations with hooks
    # Assert: Hook overhead < 5s per iteration

def test_feedback_latency():
    """Measure feedback injection latency."""
    # Setup: Running loop
    # Execute: Add feedback
    # Assert: Feedback appears in next iteration (< 1 iteration delay)

def test_session_persistence_overhead():
    """Measure session state persistence overhead."""
    # Execute: 100 iterations with session tracking
    # Assert: Session save time < 100ms per iteration
```

## Security Considerations

### GitHub Token Handling

```python
# NEVER log tokens
# NEVER store tokens in state.json
# NEVER pass tokens in command line args

# Prefer gh CLI (uses system keychain)
# If token auth: read from env var only
# Validate token before use
# Clear token from memory after use

class TokenAuth:
    def __init__(self, token: str):
        if not token:
            raise GitHubAuthError("Token not provided")
        self._token = token  # Private
    
    def __del__(self):
        # Clear token on cleanup
        self._token = None
    
    def __repr__(self):
        return "TokenAuth(***)"  # Never show token
```

### Worktree Isolation

```python
# Each worktree is fully isolated
# Workers cannot access each other's worktrees
# Workers cannot modify main worktree
# Failed worktrees preserved for forensics
# Successful worktrees cleaned up automatically

# Worktree paths are predictable but isolated
# .ralph/worktrees/worker-{id}-{task_id}/
```

### Hook Script Security

**Design Rationale:** Hooks execute arbitrary user scripts, which is inherently risky. We mitigate this by requiring explicit configuration and running hooks in isolated environments.

```python
# Hooks must be explicitly configured in ralph.toml
# No auto-discovery of hook scripts
# Hooks run with project root as CWD (not system-wide)
# Hooks have timeout protection
# Hook failures are logged but don't expose sensitive data
# Hooks cannot access Ralph's internal state

# Security best practices:
# 1. Review hook scripts before adding to config
# 2. Use absolute paths for critical operations
# 3. Validate hook script permissions (not world-writable)
# 4. Use continue_on_error=false for security-critical hooks
```

### Feedback Sanitization

```python
# Feedback is user-provided text injected into prompts
# Must sanitize to prevent prompt injection attacks

class FeedbackChannel:
    def format_for_prompt(self, task_id: Optional[str] = None) -> str:
        """Format feedback with sanitization."""
        items = self.get_recent_feedback(task_id=task_id)
        
        if not items:
            return ""
        
        lines = ["## Recent Feedback\n"]
        for item in items:
            # Sanitize content: remove control characters, limit length
            content = self._sanitize_content(item.content)
            timestamp = item.timestamp.split("T")[1][:8]
            task_info = f" (Task {item.task_id})" if item.task_id else ""
            lines.append(f"- [{timestamp}]{task_info} {content}")
        
        return "\n".join(lines)
    
    def _sanitize_content(self, content: str) -> str:
        """Sanitize feedback content."""
        # Remove control characters
        content = "".join(c for c in content if c.isprintable() or c.isspace())
        # Limit length
        max_length = 500
        if len(content) > max_length:
            content = content[:max_length] + "..."
        return content
```

### Session Data Privacy

```python
# Session logs may contain sensitive data
# Session directories should have restricted permissions
# Old sessions should be cleaned up automatically

class SessionManager:
    def create_session(self, agent: str, tracker_kind: str) -> str:
        """Create session with secure permissions."""
        session_id = self._generate_session_id()
        session_path = self.sessions_root / session_id
        session_path.mkdir(parents=True, exist_ok=True, mode=0o700)  # Owner-only
        
        # ... rest of implementation
```

## Migration Path

### From v0.6.0 to v0.7.0

**No Breaking Changes:**

- All existing configs work unchanged
- All existing trackers work unchanged
- Sequential execution is default
- Parallel mode is opt-in

**Opt-in to New Features:**

```bash
# 1. Enable parallel execution
# Edit .ralph/ralph.toml:
[parallel]
enabled = true
max_workers = 3

# 2. Switch to YAML tracker (optional)
ralph convert .ralph/prd.json tasks.yaml

# Edit .ralph/ralph.toml:
[files]
prd = "tasks.yaml"

# 3. Switch to GitHub Issues (optional)
# Edit .ralph/ralph.toml:
[tracker]
kind = "github_issues"

[tracker.github]
repo = "owner/repo"
label_filter = "ready"
```

### Rollback Plan

If v0.7.0 has issues, users can:

```bash
# 1. Disable parallel mode
[parallel]
enabled = false

# 2. Revert to old tracker
[tracker]
kind = "json"  # or "markdown"

# 3. Clean up worktrees
ralph parallel clean

# 4. Downgrade to v0.6.0
uv tool install ralph-gold==0.6.0
```

## Performance Targets

### Parallel Execution

- **Speedup:** 3x for 3 independent tasks, 5x for 5 independent tasks
- **Overhead:** < 2s per worktree creation
- **Memory:** < 100MB additional per worker
- **Disk:** ~500MB per worktree (depends on repo size)

### GitHub Issues

- **Cache hit rate:** > 90% during normal operation
- **API calls:** < 10 per run (with cache)
- **Sync time:** < 10s for 100 issues
- **Rate limit buffer:** Stay below 80% of limit

### YAML Tracker

- **Parse time:** < 100ms for 1000 tasks
- **Write time:** < 50ms for 1000 tasks
- **Validation time:** < 10ms

### Lifecycle Hooks

- **Execution overhead:** < 5s per iteration (for typical hooks)
- **Timeout enforcement:** Hooks killed after configured timeout
- **Log write latency:** < 10ms per hook execution

### Session Management

- **Session creation:** < 100ms
- **State persistence:** < 100ms per iteration
- **Session list query:** < 50ms for 100 sessions
- **Cleanup:** < 1s per 100 old sessions

### Feedback Channel

- **Write latency:** < 10ms per feedback item
- **Read latency:** < 50ms for 100 items
- **Injection delay:** Feedback appears in next iteration (< 1 iteration)
- **Storage overhead:** < 1KB per feedback item

## Observability

### Logging

```python
# .ralph/logs/parallel-{timestamp}.log
[2024-01-15 12:00:00] Parallel execution started (3 workers)
[2024-01-15 12:00:01] Worker 0: Created worktree at .ralph/worktrees/worker-0-1
[2024-01-15 12:00:01] Worker 0: Created branch ralph/worker-0-task-1
[2024-01-15 12:00:02] Worker 1: Created worktree at .ralph/worktrees/worker-1-2
[2024-01-15 12:02:00] Worker 0: Iteration complete (gates: PASS)
[2024-01-15 12:02:01] Worker 0: Merged branch ralph/worker-0-task-1
[2024-01-15 12:02:02] Worker 0: Removed worktree
[2024-01-15 12:03:00] Worker 1: Iteration complete (gates: FAIL)
[2024-01-15 12:03:01] Worker 1: Preserved worktree for debugging
[2024-01-15 12:03:02] Parallel execution complete (2/3 success)

# .ralph/logs/github-api-{timestamp}.log
[2024-01-15 12:00:00] GET /repos/owner/repo/issues?labels=ready (200)
[2024-01-15 12:00:01] Cached 15 issues
[2024-01-15 12:02:00] PATCH /repos/owner/repo/issues/123 (200)
[2024-01-15 12:02:01] POST /repos/owner/repo/issues/123/comments (201)

# .ralph/logs/hooks.log
[2024-01-15 12:00:00] Running pre_run hooks (2 commands)
[2024-01-15 12:00:01] Hook output: Synced 5 tasks from Jira
[2024-01-15 12:00:02] Running start_iteration hooks (1 command)
[2024-01-15 12:00:03] Hook output: Cleaned temp directory
[2024-01-15 12:05:00] Running end_iteration hooks (2 commands)
[2024-01-15 12:05:01] Hook output: Posted summary to Slack
[2024-01-15 12:05:02] Running on_gate_fail hooks (1 command)
[2024-01-15 12:05:03] Hook output: Collected debug snapshot
```

### Metrics

```python
# .ralph/state.json
{
  "parallel": {
    "total_runs": 10,
    "total_workers": 30,
    "success_rate": 0.87,
    "avg_speedup": 2.8,
    "avg_worker_duration": 120.5
  },
  "github": {
    "total_syncs": 20,
    "cache_hits": 180,
    "cache_misses": 20,
    "api_calls": 25,
    "rate_limit_remaining": 4975
  },
  "hooks": {
    "total_executions": 150,
    "failures": 3,
    "avg_duration_seconds": 2.5,
    "timeouts": 0
  },
  "sessions": {
    "total_sessions": 25,
    "active_sessions": 1,
    "completed_sessions": 24,
    "avg_iterations_per_session": 8.5
  },
  "feedback": {
    "total_items": 45,
    "items_by_task": {
      "task-1": 5,
      "task-2": 3
    },
    "avg_items_per_iteration": 1.2
  }
}
```

### Session Metadata

```python
# .ralph/sessions/{session_id}/metadata.json
{
  "session_id": "20240115-120000-abc123",
  "started_at": "2024-01-15T12:00:00Z",
  "ended_at": "2024-01-15T14:30:00Z",
  "agent": "codex",
  "tracker_kind": "yaml",
  "parallel_enabled": true,
  "max_workers": 3,
  "iterations_completed": 12,
  "tasks_completed": 10,
  "gates_passed": 10,
  "gates_failed": 2,
  "status": "completed"
}
```

## Correctness Properties

### Property 1: Worker Isolation

**Property:** Workers never modify each other's worktrees or branches.

**Test:**

```python
def test_worker_isolation():
    # Run 3 workers in parallel
    # Each modifies a different file
    # Assert: No conflicts, all changes preserved
```

### Property 2: Task Completion Verification

**Property:** Task is only marked done if gates pass AND tracker state updates.

**Test:**

```python
def test_task_completion_verification():
    # Run task that passes gates
    # Mock tracker.mark_task_done() to fail
    # Assert: Task remains open, worktree preserved
```

### Property 3: GitHub Sync Consistency

**Property:** GitHub Issues state always matches local tracker state after sync.

**Test:**

```python
def test_github_sync_consistency():
    # Complete task locally
    # Sync with GitHub
    # Assert: Issue closed, labels updated, comment added
    # Fetch issue again
    # Assert: State matches local
```

### Property 4: Parallel Speedup

**Property:** N independent tasks complete in ~1/N time with N workers.

**Test:**

```python
def test_parallel_speedup_property():
    # Run N tasks sequentially: measure time T_seq
    # Run N tasks in parallel (N workers): measure time T_par
    # Assert: T_par < T_seq / (N * 0.8)  # 80% efficiency
```

### Property 5: Hook Execution Order

**Property:** Hooks execute in the correct lifecycle order and never skip.

**Test:**

```python
def test_hook_execution_order():
    # Configure hooks for all lifecycle events
    # Run loop with 3 iterations
    # Assert: Hook execution order is:
    #   pre_run → start_iteration → end_iteration → start_iteration → ...
    # Assert: No hooks skipped
```

### Property 6: Session State Consistency

**Property:** Session state always reflects actual loop progress.

**Test:**

```python
def test_session_state_consistency():
    # Run loop with session tracking
    # Interrupt after N iterations
    # Assert: Session metadata shows N iterations_completed
    # Resume session
    # Assert: Loop continues from iteration N+1
```

### Property 7: Feedback Injection Guarantee

**Property:** Feedback added during iteration N appears in iteration N+1 prompt.

**Test:**

```python
def test_feedback_injection_guarantee():
    # Start loop
    # Add feedback during iteration 1
    # Assert: Feedback appears in iteration 2 prompt
    # Assert: Feedback does not appear in iteration 1 prompt
```

## Open Questions

1. **Merge conflict resolution:** Should we implement AI-powered resolution in v0.7.0 or defer to v0.8.0?
   - **Decision:** Defer to v0.8.0. Manual resolution is safer for initial release.

2. **Worker priority:** Should we support task prioritization within groups?
   - **Decision:** Not in v0.7.0. Simple FIFO within groups is sufficient.

3. **Dynamic worker scaling:** Should we adjust max_workers based on system resources?
   - **Decision:** Not in v0.7.0. Fixed max_workers is simpler and predictable.

4. **GitHub Projects integration:** Should we support GitHub Projects in addition to Issues?
   - **Decision:** Not in v0.7.0. Issues are sufficient for most teams.

5. **Distributed execution:** Should we support running workers on different machines?
   - **Decision:** Not in v0.7.0. Local parallel execution is the 80/20 solution.

6. **Hook sandboxing:** Should hooks run in sandboxed environments (containers, VMs)?
   - **Decision:** Not in v0.7.0. Hooks run in project context with timeout protection. Full sandboxing adds complexity without clear benefit for trusted user scripts.

7. **Session encryption:** Should session logs be encrypted at rest?
   - **Decision:** Not in v0.7.0. Use filesystem permissions (mode 0o700) for protection. Users with encryption needs can use encrypted filesystems.

8. **Feedback authentication:** Should feedback items be cryptographically signed?
   - **Decision:** Not in v0.7.0. Feedback is local-only and user-provided. Authentication adds complexity without clear threat model.

9. **Hook retry logic:** Should failed hooks be automatically retried?
   - **Decision:** Not in v0.7.0. Hooks fail once and log the error. Retry logic can be implemented in the hook script itself if needed.

10. **Session sharing:** Should sessions be shareable across users/machines?
    - **Decision:** Not in v0.7.0. Sessions are local to the machine. Sharing would require remote state management and conflict resolution.
