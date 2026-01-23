# Backend Design: RALPH Agent Effectiveness Improvements

**Schema Version:** 1
**Status:** Design Draft
**Date:** 2026-01-20
**Author:** Claude (backend-design skill)

---

## SYSTEM_CONTEXT

RALPH (Ralph Autonomous Loop Process Handler) Gold is a deterministic loop orchestrator that runs AI agent sessions (Codex, Claude Code, Copilot) against a filesystem-backed task queue. The system coordinates task selection, agent invocation, quality gates, and state persistence.

### Current Problem Statement

Agents are consistently failing to write files despite:
1. Explicit prompt authorization ("You are authorized to write code directly")
2. No-files detection warnings being emitted
3. Claims of completion (EXIT_SIGNAL: true)

**Observed Failure Modes:**
- Agent prepares code "mentally" but doesn't invoke Write tool
- Agent claims completion without implementation
- EXIT_SIGNAL ignored when repo dirty (safety feature working correctly)
- Quality gates failing (missing tools like swiftformat/swiftlint)
- Tasks marked "done" in PRD despite no files written

**Root Cause Analysis:**

**Issue 1: No-Files Pattern** (from earlier iterations)
The gap between prompt instructions and agent execution suggests:
1. Prompt may be insufficiently directive about tool usage patterns
2. No intermediate check reinforcing tool usage during execution
3. Agent may be optimizing for "helpful explanation" over "code delivery"
4. Missing feedback loop when agent claims completion without evidence

**Issue 2: Timeout-Induced Blocking** (from production data)
Analysis of 81 iterations reveals:
- **12 tasks blocked** after 3 failed attempts each = **36 wasted iterations (44% of total)**
- **All blocked tasks are UI-heavy** (SwiftUI views, Charts, CLI integration)
- **Current timeout: 120s (speed mode)** is insufficient for complex UI work
- **Tasks 22-43** represent Analytics/Diagnostics UI requiring:
  - Multiple file modifications
  - Chart rendering code (SwiftCharts, custom views)
  - Complex view hierarchies
  - Test setup with mock data

**Data-Driven Pattern:**
```
Tasks 1-21  (Backend/Security):  ✅ Completed (mostly)
Tasks 22-43 (UI/Analytics):     ❌ Blocked (12/22 = 55% blocked)
```

**Root Cause:** One-size-fits-all timeout doesn't account for task complexity variance.

---

## ARCHITECTURE_PATTERN

**Selected Pattern:** Event-Driven Pipeline with Adaptive Intervention

### Justification

The current architecture is already a pipeline (Task Selection → Agent Execution → Gates → State Update). The enhancement adds **adaptive intervention points** where the system detects problematic patterns and applies corrective feedback.

This differs from pure Clean Architecture (rules are already framework-agnostic) or Hexagonal (swapability not the concern). The focus is on **runtime behavior correction** through staged intervention.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            RALPH LOOP ITERATION                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                   │
│  │ Task         │    │ Agent        │    │ Gates        │                   │
│  │ Selection    │───▶│ Execution    │───▶│ Validation   │                   │
│  └──────────────┘    └──────┬───────┘    └──────┬───────┘                   │
│                             │                     │                           │
│                             ▼                     ▼                           │
│                    ┌─────────────────────────────────┐                       │
│                    │  ADAPTIVE INTERVENTION LAYER   │                       │
│                    │  ┌─────────────────────────┐   │                       │
│                    │  │ 1. No-Files Detection  │   │                       │
│                    │  │    (existing)          │   │                       │
│                    │  ├─────────────────────────┤   │                       │
│                    │  │ 2. Evidence Validation │   │  ◄── NEW: Validate    │
│                    │  │    (NEW)               │   │      claimed work     │
│                    │  ├─────────────────────────┤   │                       │
│                    │  │ 3. Mid-Stream Prompt   │   │  ◄── NEW: Reinforce   │
│                    │  │    Injection (NEW)     │   │      tool usage        │
│                    │  ├─────────────────────────┤   │                       │
│                    │  │ 4. False Completion    │   │  ◄── NEW: Detect     │
│                    │  │    Detection (NEW)     │   │      EXIT_SIGNAL lies  │
│                    │  └─────────────────────────┘   │                       │
│                    └─────────────────────────────────┘                       │
│                                      │                                        │
│                                      ▼                                        │
│                           ┌──────────────────┐                               │
│                           │ State Update     │                               │
│                           │ + Feedback       │                               │
│                           └──────────────────┘                               │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## DOMAIN_MODEL

### Core Entities

```python
@dataclass(frozen=True)
class InterventionEvent:
    """Record of an adaptive intervention during iteration."""
    iteration: int
    event_type: Literal[
        "no_files_detected",
        "evidence_validation_failed",
        "mid_stream_prompt_injected",
        "false_completion_detected",
        "agent_reinforced",
    ]
    timestamp: str
    severity: Literal["info", "warning", "critical"]
    details: Dict[str, Any]
    remediation_attempted: bool

@dataclass
class AgentBehaviorProfile:
    """Track agent behavior patterns over time."""
    agent_id: str
    total_iterations: int
    no_files_count: int
    false_completion_count: int
    avg_files_per_iteration: float
    avg_evidence_count: float
    last_reinforcement: Optional[str]
    intervention_history: List[InterventionEvent]
```

### Invariants

1. **No-Files Detection Must Trigger**: If agent returns success (rc=0) and git HEAD unchanged, file snapshot comparison must occur
2. **Evidence Validation**: If agent claims file writes, evidence must be extractable and verifiable
3. **EXIT_SIGNAL Validation**: Agent's EXIT_SIGNAL claim must be validated against actual state changes
4. **Intervention Idempotency**: Same intervention never applied twice in same iteration

---

## API_CONTRACT

### Internal APIs (no external HTTP)

#### 1. Intervention Detection Service

```python
class InterventionDetector:
    """Detects need for adaptive intervention during iteration."""

    async def detect_no_files(
        self,
        before_snapshot: set[str],
        after_snapshot: set[str],
        agent_result: SubprocessResult,
    ) -> Optional[InterventionEvent]:
        """Detect if agent wrote no files despite success.

        Returns InterventionEvent if detection triggered, None otherwise.
        """

    async def validate_evidence(
        self,
        agent_output: str,
        claimed_files: List[str],
        project_root: Path,
    ) -> tuple[bool, Optional[InterventionEvent]]:
        """Validate that agent's claimed work has supporting evidence.

        Returns (is_valid, intervention_event_if_invalid).
        """

    async def detect_false_completion(
        self,
        exit_signal_claim: bool,
        actual_state_changes: bool,
        files_written: bool,
    ) -> Optional[InterventionEvent]:
        """Detect if agent falsely claimed completion.

        Agent claims EXIT_SIGNAL: true but:
        - No files written
        - No state changes
        - No progress made

        Returns InterventionEvent if false completion detected.
        """
```

#### 2. Adaptive Reinforcement Service

```python
class AdaptiveReinforcement:
    """Applies corrective feedback to agent during execution."""

    async def inject_mid_stream_prompt(
        self,
        agent_process: subprocess.Popen,
        reinforcement_prompt: str,
    ) -> bool:
        """Inject reinforcement prompt into running agent process.

        WARNING: This is advanced/fallback. Requires agent stdin to be
        accepting input during execution.

        Returns True if injection succeeded, False otherwise.
        """

    async def apply_iteration_feedback(
        self,
        profile: AgentBehaviorProfile,
        event: InterventionEvent,
    ) -> str:
        """Generate feedback message for next iteration's prompt.

        Returns feedback string to be appended to next prompt.
        """
```

---

## DATA_DESIGN

### New Persistence Artifacts

```
.ralph/
├── interventions/
│   ├── events.json           # Array of InterventionEvent
│   ├── profile.json          # AgentBehaviorProfile per agent
│   └── feedback.txt          # Accumulated feedback for next iteration
└── metrics.json              # Existing (enhanced with intervention metrics)
```

### Schema: interventions/events.json

```json
{
  "$schema": "ralph_gold.interventions.v1",
  "events": [
    {
      "iteration": 2,
      "event_type": "no_files_detected",
      "timestamp": "2026-01-20T20:35:00Z",
      "severity": "critical",
      "details": {
        "task_id": "E1-02",
        "agent_return_code": 0,
        "exit_signal_claimed": true,
        "files_written": 0,
        "evidence_count": 0
      },
      "remediation_attempted": true
    }
  ]
}
```

### Schema: interventions/profile.json

```json
{
  "$schema": "ralph_gold.profile.v1",
  "agent_id": "claude",
  "total_iterations": 10,
  "no_files_count": 2,
  "false_completion_count": 1,
  "avg_files_per_iteration": 0.3,
  "avg_evidence_count": 1.2,
  "last_reinforcement": "2026-01-20T20:40:00Z",
  "intervention_threshold_exceeded": true
}
```

### Migration Strategy

No database migration needed. New files created on-first-use.

---

## AUTHN_AUTHZ

**Not Applicable** — This is internal loop enhancement, no external auth.

---

## RELIABILITY

### Failure Mode Handling

| Failure Mode | Detection | Mitigation |
|--------------|-----------|------------|
| No files written | Snapshot comparison | Warning + feedback for next iteration |
| False completion | EXIT_SIGNAL vs reality check | Override signal, force task open |
| Evidence missing | Regex extraction fails | Request explicit evidence in next prompt |
| Mid-stream injection fails | Process stdin closed | Fallback to next-iteration feedback |

### Idempotency

- Intervention events are append-only log
- Same detection conditions don't create duplicate events
- Feedback accumulation is idempotent (same message appended once)

### Circuit Breaker

If agent exceeds intervention threshold (e.g., 3 no-files events in 5 iterations):

```python
if profile.no_files_count >= 3 and profile.total_iterations <= 5:
    # Apply aggressive reinforcement
    # Consider suspending agent for manual review
    # Log critical incident
```

---

## OBSERVABILITY

### New Metrics

```python
@dataclass
class InterventionMetrics:
    """Metrics for intervention effectiveness."""
    total_interventions: int
    interventions_by_type: Dict[str, int]
    interventions_by_severity: Dict[str, int]
    intervention_rate_per_100_iterations: float
    avg_remediation_success_rate: float
```

### Logging

```python
logger.warning(
    "intervention_triggered",
    extra={
        "iteration": iteration,
        "event_type": "no_files_detected",
        "severity": "critical",
        "task_id": story_id,
        "agent": agent,
    }
)
```

### Tracing

Add span for intervention detection:

```
[TRACE] iteration:2 → agent_execution → intervention_detection → evidence_validation
```

---

## PERFORMANCE

### Overhead Analysis

| Operation | Overhead | Frequency |
|-----------|----------|-----------|
| Snapshot comparison | O(n) files | Every iteration |
| Evidence extraction | O(output_size) | Every iteration |
| False completion check | O(1) | Every iteration |
| Profile persistence | O(profile_size) | On intervention |

**Target:** < 100ms additional overhead per iteration

### Optimization

- Cache snapshot results if no filesystem changes detected
- Lazy load intervention history
- Compress old intervention events (older than 30 days)

---

## INTEGRATION_SURFACES

### CLI Integration

```bash
# View intervention history
ralph interventions --last 10

# View agent behavior profile
ralph profile --agent claude

# Reset intervention history
ralph interventions --reset
```

### Prompt Integration

Feedback automatically appended to next prompt:

```markdown
## Previous Iteration Feedback (DO NOT IGNORE)

**CRITICAL**: In iteration 2, you claimed completion but wrote NO FILES.
- EXIT_SIGNAL: true was IGNORED because no files were written
- Task E1-02 remains OPEN
- You MUST use the Write tool to create/modify files

**Evidence Required**: List all file changes with line numbers.
```

---

## APPS_SDK_REQUIREMENTS

**Not Applicable** — No mobile/Apps SDK integration.

---

## RISK_CHECKLIST

| Risk | Severity | Mitigation |
|------|----------|------------|
| Over-intervention chokes agent progress | High | Configurable thresholds, opt-out flag |
| False positives (files written but not detected) | Medium | Git HEAD + snapshot的双重检查 |
| Feedback accumulation bloating prompts | Medium | Rotate/summarize old feedback |
| Mid-stream injection crashes agent | Low | Fallback to next-iteration only |
| State corruption from concurrent writes | Low | File locking on intervention artifacts |

---

## FILE_PLAN

### New Files

```
src/ralph_gold/interventions/
├── __init__.py
├── models.py          # InterventionEvent, AgentBehaviorProfile
├── detection.py       # InterventionDetector
├── reinforcement.py   # AdaptiveReinforcement
└── persistence.py     # Load/save intervention data

src/ralph_gold/evidence/
├── __init__.py
├── extraction.py      # Extract evidence from agent output
└── validation.py      # Validate evidence matches claims

tests/
├── test_interventions.py
├── test_evidence.py
├── test_reinforcement.py
└── test_adaptive_timeout.py

src/ralph_gold/adaptive_timeout/
├── __init__.py
├── models.py          # TaskComplexity, AdaptiveTimeoutConfig
├── classifier.py      # estimate_task_complexity()
├── calculator.py      # calculate_adaptive_timeout()
└── unblock.py         # BlockedTaskManager
```

### Modified Files

```
src/ralph_gold/loop.py
├── Import InterventionDetector, AdaptiveReinforcement
├── Add intervention detection after agent execution
├── Add evidence validation before accepting completion
├── Add false completion detection before EXIT_SIGNAL processing
├── Append feedback to prompt for next iteration
├── Integrate adaptive timeout calculation before agent execution
└── Add task complexity classification to task selection flow

src/ralph_gold/cli.py
├── Add `ralph blocked --suggest` command
├── Add `ralph unblock <task-id>` command
├── Add `ralph retry-blocked` command
└── Add timeout display to status output

src/ralph_gold/config.py
├── Add [interventions] section
│   ├── enabled = true
│   ├── threshold_no_files = 3
│   ├── threshold_false_completion = 2
│   ├── feedback_rotation_days = 30
│   └── aggressive_mode = false
├── Add [adaptive_timeout] section
│   ├── enabled = true
│   ├── complexity_scaling = true
│   ├── failure_scaling = true
│   ├── max_timeout = 3600
│   ├── min_timeout = 60
│   └── timeout_multiplier_per_failure = 1.5
├── Add [unblock] section
│   ├── auto_suggest = true
│   └── max_auto_unblock_attempts = 1

src/ralph_gold/templates/PROMPT_build.md
├── Add "PREVIOUS ITERATION FEEDBACK" section (dynamic)
└── Strengthen "REQUIRED: Evidence of File Writes" section
```

### Documentation

```
docs/INTERVENTIONS.md           # New: Intervention system docs
docs/PROMPT_ANATOMY.md          # New: How prompts are constructed
docs/ADAPTIVE_TIMEOUT.md        # New: Adaptive timeout configuration
docs/UNBLOCK_GUIDE.md           # New: How to unblock and retry tasks
docs/TROUBLESHOOTING.md         # Update: Intervention + timeout troubleshooting
README.md                        # Update: Mention intervention + adaptive features
```

---

## ADAPTIVE_TIMEOUT_UNBLOCK

### Problem Summary

From production data (81 iterations):
- 12 tasks blocked after timeout (44% of iterations wasted)
- UI tasks need 5-10x more time than backend tasks
- Current model: fixed timeout per mode, no adaptation

### Solution: Task-Type-Aware Adaptive Timeout

#### 1. Task Complexity Classification

```python
@dataclass(frozen=True)
class TaskComplexity:
    """Estimated complexity level for timeout allocation."""
    level: Literal["simple", "medium", "complex", "ui_heavy"]
    base_timeout_seconds: int
    multiplier: float

# Complexity Matrix
COMPLEXITY_LEVELS = {
    "simple": TaskComplexity(level="simple", base_timeout_seconds=60, multiplier=1.0),
    "medium": TaskComplexity(level="medium", base_timeout_seconds=180, multiplier=1.5),
    "complex": TaskComplexity(level="complex", base_timeout_seconds=300, multiplier=2.0),
    "ui_heavy": TaskComplexity(level="ui_heavy", base_timeout_seconds=600, multiplier=3.0),
}
```

**Classification Heuristics:**
```python
def estimate_task_complexity(task: SelectedTask) -> TaskComplexity:
    """Estimate task complexity from title/description/acceptance.

    Heuristics:
    - Keywords: "UI", "View", "Chart", "Dashboard" → ui_heavy
    - Keywords: "test", "mock", "fixture" → medium
    - Keywords: "CLI", "command", "parser" → complex
    - Keywords: "fix", "update", "refactor" → simple
    - Acceptance criteria count: > 3 items → increase complexity
    """
```

#### 2. Adaptive Timeout Scaling

```python
@dataclass
class AdaptiveTimeoutConfig:
    """Configure adaptive timeout behavior."""
    base_timeout: int = 120  # From mode config
    enable_complexity_scaling: bool = True
    enable_failure_scaling: bool = True
    max_timeout: int = 3600  # 1 hour absolute max
    timeout_multiplier_per_failure: float = 1.5  # 50% increase per timeout
    min_timeout: int = 60  # 1 minute absolute min

def calculate_adaptive_timeout(
    task: SelectedTask,
    previous_failures: int,
    config: AdaptiveTimeoutConfig,
    mode_timeout: int,
) -> int:
    """Calculate adaptive timeout for task attempt.

    Formula:
    timeout = min(mode_timeout * complexity_multiplier * failure_multiplier, max_timeout)
    """
    complexity = estimate_task_complexity(task)
    failure_multiplier = config.timeout_multiplier_per_failure ** previous_failures

    timeout = int(
        mode_timeout
        * complexity.multiplier
        * failure_multiplier
    )

    return max(config.min_timeout, min(timeout, config.max_timeout))
```

#### 3. Unblock & Retry Mechanism

```python
class BlockedTaskManager:
    """Manage blocked task unblocking and retry."""

    def list_blocked_tasks(self) -> List[SelectedTask]:
        """List all blocked tasks with retry metadata."""

    def unblock_task(
        self,
        task_id: str,
        reason: str,
        new_timeout: Optional[int] = None,
    ) -> bool:
        """Unblock a task for retry with optional new timeout.

        Records unblock reason in attempt history.
        """

    def suggest_unblock_strategy(self, task: SelectedTask) -> str:
        """Suggest unblock strategy based on block reason.

        Returns:
            Strategy recommendation (e.g., "increase_timeout", "skip_subtasks", "manual_review")
        """
```

#### 4. CLI Integration

```bash
# View blocked tasks with suggested actions
ralph blocked --suggest

# Unblock specific task with increased timeout
ralph unblock <task-id> --timeout 1800

# Unblock all UI tasks with 3x timeout
ralph unblock --filter "ui_heavy" --timeout-multiplier 3.0

# Batch retry blocked tasks
ralph retry-blocked --max-attempts 1
```

### Configuration

```toml
# .ralph/ralph.toml
[adaptive_timeout]
enabled = true
complexity_scaling = true
failure_scaling = true
max_timeout = 3600
min_timeout = 60
timeout_multiplier_per_failure = 1.5

[adaptive_timeout.complexity.simple]
multiplier = 1.0
keywords = ["fix", "update", "refactor", "add"]

[adaptive_timeout.complexity.ui_heavy]
multiplier = 3.0
keywords = ["UI", "View", "Chart", "Dashboard", "SwiftUI"]

[unblock]
auto_suggest = true
max_auto_unblock_attempts = 1
```

### Implementation Priority

| Sub-feature | Priority | Effort |
|-------------|----------|--------|
| Task complexity classifier | HIGH | 4-6 hours |
| Adaptive timeout calculation | HIGH | 2-3 hours |
| Unblock CLI commands | MEDIUM | 3-4 hours |
| Complexity config parsing | LOW | 2 hours |

**Total:** 11-15 hours additional effort

---

## NEXT STEPS

### Phase 1: Core Detection (Priority: CRITICAL)
1. Implement `InterventionDetector` with no-files detection
2. Implement `EvidenceValidator` for basic evidence extraction
3. Add integration to loop.py (existing detection enhancement)
4. Add tests for detection accuracy

**Success Criteria:** No-files events always detected, evidence validated

### Phase 2: Feedback Loop (Priority: HIGH)
1. Implement `AdaptiveReinforcement` with next-iteration feedback
2. Add prompt template update for feedback section
3. Implement feedback rotation (prevent bloat)
4. Add tests for feedback efficacy

**Success Criteria:** Agent behavior improves over iterations

### Phase 3: Advanced Intervention (Priority: MEDIUM)
1. Implement false completion detection
2. Add mid-stream prompt injection (experimental)
3. Implement agent behavior profiling
4. Add CLI commands for intervention visibility

**Success Criteria:** False completions caught and corrected

### Phase 4: Evaluation (Priority: HIGH)
1. Run 100-iteration test with measurement
2. Compare: baseline vs intervention-enabled
3. Measure: files-per-iteration, completion rate, intervention frequency
4. Document: threshold tuning guide

**Success Criteria:** Measurable improvement in agent effectiveness

### Phase 5: Adaptive Timeout & Unblock (Priority: CRITICAL)
1. Implement `TaskComplexity` classifier with keyword heuristics
2. Implement `calculate_adaptive_timeout()` for dynamic timeout allocation
3. Implement `BlockedTaskManager` for unblock/retry operations
4. Add CLI commands: `ralph blocked`, `ralph unblock`, `ralph retry-blocked`
5. Update config parsing for `[adaptive_timeout]` section

**Success Criteria:** UI tasks get appropriate timeouts, blocked tasks can be recovered

**Target Metrics:**
- Reduce blocked task rate from 55% to < 20%
- Reduce wasted iterations from 44% to < 15%
- Increase completion rate for tasks 22-43 from 45% to > 80%

---

## IMPLEMENTATION NOTES

### Critical Design Decisions

1. **No Mid-Stream Injection by Default**: Too risky (agent crashes, stdin race conditions). Focus on next-iteration feedback.

2. **EXIT_SIGNAL Override**: When false completion detected, system overrides agent's claim. This is safe because it's protecting the loop from incorrect state.

3. **Evidence is Required but Not Sufficient**: Agent must provide evidence, but evidence alone doesn't prove work (could be hallucinated). File snapshot is ground truth.

4. **Configurable Thresholds**: Different agents/projects may need different sensitivity. Provide defaults but allow override.

5. **Keyword-Based Complexity Classification**: Heuristics over ML/prediction. Simpler, faster, but may misclassify. Trade-off acceptable: 80% accuracy better than 0% (current).

6. **Unblock is Manual-by-Default**: Auto-unblock could cause infinite loops. Require explicit user action or strict limits.

### Trade-offs

| Decision | Pro | Con |
|----------|-----|-----|
| Next-iteration feedback (not mid-stream) | Safe, reliable | Slower correction |
| EXIT_SIGNAL override | Protects loop integrity | Agent may be "right" occasionally |
| Evidence required | Improves quality | Some agents may struggle with format |
| Intervention artifacts | Debuggable, auditable | More files to manage |
| Keyword-based complexity | Simple, fast, explainable | May misclassify edge cases |
| Adaptive timeout scaling | Reduces wasted iterations | May extend runtime for slow agents |
| Manual unblock default | Prevents infinite loops | Requires operator attention |

---

**Document Status:** Ready for Implementation Review
**Next Review:** After Phase 1 completion
**Estimated Implementation Effort:** 35-45 hours across 5 phases (updated with Phase 5)
