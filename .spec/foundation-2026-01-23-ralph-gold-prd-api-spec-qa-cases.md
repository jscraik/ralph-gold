schema_version: 1
# QA Test Cases — Ralph Gold API Spec (VS Code Bridge)

## 1) Test case list (Given/When/Then + expected result)

**Test Case ID:** API-TC-001 (Ping)  
**Given** the bridge is running  
**When** I send a `ping` request  
**Then** I receive `ok=true` with `version`, `cwd`, and `time`.  
**Expected result:** response matches schema; fields are non-empty.  

**Test Case ID:** API-TC-002 (Status schema)  
**Given** the bridge is running  
**When** I send a `status` request  
**Then** the response includes all required fields and `agents` is an array of strings.  
**Expected result:** response matches schema; `next.task_id` type is string when present.  

**Test Case ID:** API-TC-003 (Status last state)  
**Given** at least one iteration has run  
**When** I send a `status` request  
**Then** `last` includes required minimum fields with correct types.  
**Expected result:** `iteration_id`, `task_id`, `status`, `exit_code`, `started_at`, `finished_at` all present.  

**Test Case ID:** API-TC-004 (Step default agent)  
**Given** no agent is specified  
**When** I send a `step` request with empty params  
**Then** the iteration runs using default agent and returns `task_id`.  
**Expected result:** response includes `agent`, `iteration`, `task_id`, and exit fields.  

**Test Case ID:** API-TC-005 (Run start)  
**Given** no run is active  
**When** I send a `run` request  
**Then** I receive a `runId`.  
**Expected result:** `runId` is non-empty.  

**Test Case ID:** API-TC-006 (Pause/Resume)  
**Given** a run is active  
**When** I send `pause` and then `resume`  
**Then** each response includes `ok`, `runId`, and `paused` status.  
**Expected result:** `paused` toggles accordingly.  

**Test Case ID:** API-TC-007 (Stop)  
**Given** a run is active  
**When** I send `stop`  
**Then** I receive `ok=true` and `stopped=true`.  
**Expected result:** background run ends.  

**Test Case ID:** API-TC-008 (Invalid method)  
**Given** the bridge is running  
**When** I send an unknown method  
**Then** I receive error `-32601`.  
**Expected result:** error code and message present.  

**Test Case ID:** API-TC-009 (Invalid params)  
**Given** the bridge is running  
**When** I send a `run` request with invalid param types  
**Then** I receive error `-32602`.  
**Expected result:** error code and message present.  

**Test Case ID:** API-TC-010 (Rate limiting)  
**Given** I send >10 requests/sec  
**When** the bridge throttles  
**Then** I receive error `-32001`.  
**Expected result:** error code indicates rate limit.  

**Test Case ID:** API-TC-011 (Event schemas)  
**Given** a run starts and finishes  
**When** I listen for `event` notifications  
**Then** each event payload matches the required schema for its type.  
**Expected result:** required fields present for `run_started`, `iteration_started`, `iteration_finished`, `run_stopped`.  

## 2) Coverage map (criteria -> cases)

| Acceptance Criteria | Test Case ID | Test Type | Status |
| --- | --- | --- | --- |
| Ping schema | API-TC-001 | integration | planned |
| Status schema | API-TC-002 | integration | planned |
| Last state schema | API-TC-003 | integration | planned |
| Step default agent | API-TC-004 | integration | planned |
| Run returns runId | API-TC-005 | integration | planned |
| Pause/Resume schema | API-TC-006 | integration | planned |
| Stop response | API-TC-007 | integration | planned |
| Unknown method error | API-TC-008 | unit | planned |
| Invalid params error | API-TC-009 | unit | planned |
| Rate limiting error | API-TC-010 | manual | planned |
| Event schemas | API-TC-011 | integration | planned |

## 3) Manual vs automated split

- Automated: API-TC-001 through API-TC-009, API-TC-011.  
- Manual: API-TC-010 (rate limiting).  

## 4) Data and environment prerequisites

- Bridge running via `ralph bridge`.  
- Sample repo with `.ralph/` scaffold and at least one iteration for `last` state.  
- Test client capable of JSON-RPC over stdio.  

## Traceability matrix (required)

| Acceptance Criteria | Test Case ID | Test Type | Status |
| --- | --- | --- | --- |
| Ping response | API-TC-001 | integration | planned |
| Status response | API-TC-002 | integration | planned |
| Last state fields | API-TC-003 | integration | planned |
| Step response | API-TC-004 | integration | planned |
| Run response | API-TC-005 | integration | planned |
| Pause/Resume | API-TC-006 | integration | planned |
| Stop response | API-TC-007 | integration | planned |
| Method not found | API-TC-008 | unit | planned |
| Invalid params | API-TC-009 | unit | planned |
| Rate limit | API-TC-010 | manual | planned |
| Events schema | API-TC-011 | integration | planned |
