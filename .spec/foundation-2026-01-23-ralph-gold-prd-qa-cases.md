schema_version: 1
# QA Test Cases — Ralph Gold (PRD-derived)

## 1) Test case list (Given/When/Then + expected result)

**Test Case ID:** TC-001 (Init scaffold)  
**Given** a fresh repo without `.ralph/`  
**When** I run `ralph init`  
**Then** `.ralph/ralph.toml`, `.ralph/PRD.md`, `.ralph/progress.md`, and prompt files exist.  
**Expected result:** scaffold created with correct paths.  

**Test Case ID:** TC-002 (Single iteration)  
**Given** a configured repo  
**When** I run `ralph step --agent <agent>`  
**Then** exactly one iteration runs and `ralph status` reports the new state.  
**Expected result:** exit code matches docs; status updated.  

**Test Case ID:** TC-003 (Max iterations)  
**Given** a configured repo  
**When** I run `ralph run --max-iterations 1`  
**Then** the loop stops after one iteration.  
**Expected result:** run completes with documented exit code.  

**Test Case ID:** TC-004 (Review gate)  
**Given** `review.enabled = true` and `review.required_token = "SHIP"`  
**When** the loop reaches exit conditions  
**Then** it does not exit until the token is provided.  
**Expected result:** exit blocked until token provided.  

**Test Case ID:** TC-005 (Receipts + context)  
**Given** a completed iteration  
**When** I inspect `.ralph/receipts/` and `.ralph/context/`  
**Then** the latest receipt and ANCHOR exist.  
**Expected result:** receipt JSON and ANCHOR.md present.  

**Test Case ID:** TC-006 (Interactive selection)  
**Given** multiple tasks in the tracker  
**When** I run `ralph step --interactive`  
**Then** I can select a task and it is executed.  
**Expected result:** selection maps to chosen task.  

**Test Case ID:** TC-007 (TUI control surface)  
**Given** a configured repo  
**When** I run `ralph tui` and press `s`/`r`/`a`/`p`/`q`  
**Then** each key performs the documented action.  
**Expected result:** TUI responds correctly to each key.  

**Test Case ID:** TC-008 (Authorization guard)  
**Given** restrictive authorization rules  
**When** an iteration attempts to write outside allowed paths  
**Then** the write is blocked or rejected.  
**Expected result:** unauthorized writes do not occur.  

**Test Case ID:** TC-009 (Watch mode enablement)  
**Given** `watch.enabled = false`  
**When** I run `ralph watch`  
**Then** I receive a clear enablement instruction.  
**Expected result:** user is told to enable watch mode.  

**Test Case ID:** TC-010 (Watch mode behavior)  
**Given** `watch.enabled = true` with patterns  
**When** I edit a matching file  
**Then** gates run after debounce.  
**Expected result:** gate output shown once per change.  

**Test Case ID:** TC-011 (Status UX clarity)  
**Given** a gate failure  
**When** I run `ralph status`  
**Then** output includes a text label and next-step guidance.  
**Expected result:** no color-only status; guidance present.  

**Test Case ID:** TC-012 (Performance target)  
**Given** a repo with <= 5k files  
**When** I run `time ralph status` 10 times  
**Then** median wall time is <= 500ms.  
**Expected result:** performance budget met.  

## 2) Coverage map (criteria -> cases)

| Acceptance Criteria | Test Case ID | Test Type | Status |
| --- | --- | --- | --- |
| `ralph init` scaffolds `.ralph/` files | TC-001 | integration | planned |
| `ralph step` runs single iteration | TC-002 | integration | planned |
| `ralph run --max-iterations` bounded | TC-003 | integration | planned |
| Review gate requires SHIP | TC-004 | integration | planned |
| Receipts/context written | TC-005 | integration | planned |
| Interactive selection works | TC-006 | unit/manual | planned |
| TUI keybindings | TC-007 | manual | planned |
| Authorization rules enforce writes | TC-008 | integration | planned |
| Watch enablement instruction | TC-009 | manual | planned |
| Watch mode runs gates | TC-010 | manual | planned |
| Status UX clarity | TC-011 | manual | planned |
| Status perf budget | TC-012 | manual | planned |

## 3) Manual vs automated split

- Automated (candidate): TC-001, TC-002, TC-003, TC-004, TC-005, TC-008.  
- Manual: TC-006, TC-007, TC-009, TC-010, TC-011, TC-012.  

## 4) Data and environment prerequisites

- Repo initialized with `.ralph/` scaffolding.  
- Test agent CLI available (codex/claude/copilot).  
- Sample PRD/task tracker with at least 2 tasks for interactive selection.  
- Watch mode config in `.ralph/ralph.toml` with patterns.  
- Authorization rules configured for negative tests.  

## Traceability matrix (required)

| Acceptance Criteria | Test Case ID | Test Type | Status |
| --- | --- | --- | --- |
| CLI scaffold created | TC-001 | integration | planned |
| Single iteration | TC-002 | integration | planned |
| Max iterations | TC-003 | integration | planned |
| Review gate | TC-004 | integration | planned |
| Receipts + context | TC-005 | integration | planned |
| Interactive selection | TC-006 | unit/manual | planned |
| TUI control surface | TC-007 | manual | planned |
| Authorization guard | TC-008 | integration | planned |
| Watch enablement | TC-009 | manual | planned |
| Watch behavior | TC-010 | manual | planned |
| Status UX clarity | TC-011 | manual | planned |
| Performance budget | TC-012 | manual | planned |
