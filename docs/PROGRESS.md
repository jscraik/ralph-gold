---
last_validated: 2026-02-28
---

# Progress Visualization

**Version:** 1.0
**Last Updated:** 2026-01-20
**Review Cadence:** Quarterly
**Audience:** Users

---

## Overview

Ralph provides powerful progress tracking and visualization features to help you understand your project's velocity, completion timeline, and task dependencies.

---

`★ Insight ─────────────────────────────────────`
**Progress Metrics Architecture:**
1. **History-based** - All metrics calculated from `.ralph/state.json` history
2. **Incremental** - Velocity updates after each successful iteration
3. **Requires history** - Minimum 2 successful iterations needed for velocity
`─────────────────────────────────────────────────`

---

## Quick Start

### Basic Status

```bash
ralph status
```

Shows:
- Current task
- Tasks completed / total
- Last iteration summary

### Detailed Metrics

```bash
ralph status --detailed
```

Adds:
- Progress bar
- Velocity (tasks/day)
- Estimated completion date (ETA)

### Burndown Chart

```bash
ralph status --chart
```

Shows ASCII chart of tasks remaining over time.

### Dependency Graph

```bash
ralph status --graph
```

Shows task dependency relationships.

---

## Progress Metrics

### Progress Bar

Visual representation of task completion:

```
Progress: [████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 60% (12/20 tasks)
```

**Components:**
- Filled portion: Completed tasks
- Empty portion: Remaining tasks
- Percentage: Completion rate
- Count: Completed / Total

### Task Counts

```
Total Tasks:       20
Completed:         12
In Progress:       1
Blocked:           0
Completion:        60.0%
```

**Metrics:**
- **Total Tasks**: All tasks in PRD
- **Completed**: Tasks marked as done
- **In Progress**: Currently selected task
- **Blocked**: Tasks with unmet dependencies
- **Completion**: Percentage complete

### Velocity

```
Velocity:          1.50 tasks/day
Estimated ETA:     2024-02-15
```

**Velocity Calculation:**
- Based on successful iterations in state.json
- Calculated as: tasks completed / elapsed days
- Requires minimum 2 successful iterations
- Updated after each successful iteration

**ETA Calculation:**
- Projects completion date based on velocity
- Formula: `current_date + (remaining_tasks / velocity)`
- Shows "N/A" if velocity is unavailable

---

## Burndown Chart

### ASCII Chart

```bash
ralph status --chart
```

**Example output:**
```
Tasks
20 │ ●
   │  ●
15 │   ●●
   │     ●
10 │      ●●
   │        ●
 5 │         ●●
   │           ●
 0 └─────────────────
   Day 1  3  5  7  9
```

**Components:**
- **Y-axis**: Number of remaining tasks
- **X-axis**: Days since project start
- **Data Points (●)**: Task completion milestones
- **Trend**: Visual representation of progress velocity

### Interpreting the Chart

**Steep decline** (left to right):
- High velocity
- Many tasks completing quickly
- Project ahead of schedule

**Shallow slope**:
- Lower velocity
- Tasks taking longer
- Project behind schedule

**Flat line**:
- No progress
- Possible blocker
- Check `ralph status` for current task

---

## Dependency Graph

### Visual Representation

```bash
ralph status --graph
```

**Example output:**
```
============================================================
Task Dependency Graph
============================================================

Level 0:
  ○ 1
      (no dependencies)

Level 1:
  ○ 2
      depends on: 1

Level 2:
  ○ 3
      depends on: 1, 2

============================================================
Total tasks: 3
Total dependencies: 3
============================================================
```

**Components:**
- **Levels**: Dependency depth (0 = no dependencies)
- **○**: Task ID
- **depends on**: List of task IDs this task requires

### Circular Dependencies

```bash
ralph diagnose
```

Detects and reports circular dependency cycles:

```
ERRORS:
  ✗ Found 1 circular dependency cycle(s)
    → Remove circular dependencies to allow tasks to execute
    → Circular dependencies detected:
    → Cycle 1: task-2 → task-3 → task-2
    → Break the cycle by removing one or more 'depends_on' relationships
```

---

## Configuration

### Progress Settings

In `.ralph/ralph.toml`:

```toml
[progress]
show_velocity = true           # Show velocity and ETA
show_burndown = true            # Show burndown chart
chart_width = 60               # Chart width in characters
```

**Settings:**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `show_velocity` | bool | `true` | Show velocity and ETA in detailed status |
| `show_burndown` | bool | `true` | Include burndown chart in status |
| `chart_width` | int | `60` | Width of burndown chart (characters) |

---

## Usage Examples

### Daily Standup

Quick progress overview:

```bash
ralph status --detailed
```

**What to share:**
- Current completion percentage
- Velocity from last 24 hours
- Estimated completion date
- Any blocked tasks

### Sprint Planning

Velocity data for future estimates:

```bash
ralph stats --by-task
```

**Shows per-task:**
- Number of attempts per task
- Average duration per task
- Total duration per task

Use this to estimate similar future tasks.

### Stakeholder Updates

Burndown chart for visual progress:

```bash
ralph status --chart
```

Copy/paste the ASCII chart into reports or presentations.

### Bottleneck Detection

Check for no-progress situations:

```bash
ralph status
```

Look for:
- High no-progress streak
- Blocked tasks
- Velocity dropping

---

## Velocity Calculation Details

### How It Works

1. **Track iterations**: Each successful iteration records timestamp and task completion
2. **Calculate elapsed**: Time from first to last iteration
3. **Count completions**: Number of unique tasks completed
4. **Compute rate**: Tasks completed / elapsed days

### Example Timeline

```
Day 1 (2024-01-01): Task 1 completed
Day 2 (2024-01-02): Task 2 completed
Day 3 (2024-01-03): Task 3 completed
Day 4 (2024-01-04): Task 4 completed
Day 5 (2024-01-05): Task 5 completed
```

**Calculation:**
- Completed: 5 tasks
- Elapsed: 5 days
- Velocity: 5 / 5 = 1.0 tasks/day

**ETA Projection:**
- Remaining: 10 tasks
- Velocity: 1.0 tasks/day
- ETA: 10 days from now = 2024-01-15

### Minimum Requirements

- **2 successful iterations** needed for velocity calculation
- History stored in `.ralph/state.json`
- Velocity "N/A" until threshold met

---

## Troubleshooting

### Velocity Shows "N/A"

**Cause:** Less than 2 successful iterations completed

**Solution:** Run more iterations:
```bash
ralph step --agent codex
```

### ETA Shows "N/A"

**Cause:** Velocity unavailable (see above)

**Solution:** Same as velocity - need more iterations

### Burndown Chart Empty

**Cause:** No task completion history yet

**Solution:** Complete at least one task

### Incorrect Progress

**Symptom:** Progress shows wrong task count

**Diagnosis:**
```bash
# Check state
ralph diagnose

# Verify PRD structure
cat .ralph/PRD.md

# Validate state vs PRD
cat .ralph/state.json | jq '.tasks'
```

**Solution:**
```bash
# Clean up stale state
ralph state cleanup --force
```

---

## Statistics Command

For deeper analysis, use the stats command:

```bash
ralph stats
```

**Shows:**
- Total iterations
- Success rate
- Duration statistics (avg, min, max)

### Per-Task Breakdown

```bash
ralph stats --by-task
```

**Shows:**
- Attempts per task
- Duration per task
- Success/failure counts
- Sorted by total duration (slowest first)

### Export for Analysis

```bash
ralph stats --export stats.csv
```

**CSV includes:**
- Overall statistics
- Per-task breakdown
- Timestamps and durations

Import into spreadsheet tools for custom analysis and reporting.

---

## Integration with Other Tools

### JSON Output

For programmatic access:

```bash
ralph status --format json
```

**Example output:**
```json
{
  "total_tasks": 20,
  "completed": 12,
  "in_progress": 1,
  "blocked": 0,
  "completion_percentage": 60.0,
  "velocity": 1.5,
  "eta": "2024-02-15"
}
```

### jq Queries

Extract specific metrics:

```bash
# Get completion percentage
ralph status --format json | jq '.completion_percentage'

# Get velocity
ralph status --format json | jq '.velocity'

# Get blocked task count
ralph status --format json | jq '.blocked'
```

---

## Related Documentation

- **Commands:** `docs/COMMANDS.md` - `ralph status` command reference
- **Configuration:** `docs/CONFIGURATION.md` - Progress settings
- **Project Structure:** `docs/PROJECT_STRUCTURE.md` - state.json format

---

**Document Owner:** maintainers
**Next Review:** 2026-04-20
**Change Log:**
- 2026-01-20: Initial version (v1.0)
