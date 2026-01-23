schema_version: 1
# API Test Harness Outline — JSON-RPC over stdio

## 1) Purpose

Provide a minimal, repeatable harness to execute JSON-RPC requests against `ralph bridge` over stdio and validate response schemas.  
Evidence: .spec/foundation-2026-01-23-ralph-gold-prd-api-spec.md.

## 2) Harness approach (outline)

- Spawn `ralph bridge` as a subprocess.  
- Send newline-delimited JSON-RPC requests to stdin.  
- Read stdout line-by-line and parse JSON responses/notifications.  
- Validate against expected schemas and field types.  
Evidence: docs/VSCODE_BRIDGE_PROTOCOL.md.

## 3) Minimal interface

- `send(method, params, id)` -> writes JSON request line.  
- `recv()` -> returns next response or event.  
- `expect_result(id)` -> waits for matching response id.  
- `expect_event(type)` -> waits for event notification.  
Evidence: .spec/foundation-2026-01-23-ralph-gold-prd-api-spec.md.

## 4) Example flow (pseudo)

```text
start bridge
send ping
expect result id=1
send status
expect result id=2
send step (agent optional)
expect result id=3
expect event iteration_started
expect event iteration_finished
send stop
expect result id=4
```

Evidence: docs/VSCODE_BRIDGE_PROTOCOL.md.

## 5) Validation rules

- Enforce required fields per method and event schema.  
- Reject unknown field types for required fields.  
- Tolerate additional fields (forward compatibility).  
Evidence: .spec/foundation-2026-01-23-ralph-gold-prd-api-spec.md.

## 6) Test data / environment

- Repo with `.ralph/` scaffold initialized.  
- At least one task in tracker for step/run events.  
- Agent CLI available (codex/claude/copilot).  
Evidence: README.md; AGENTS.md.

## 7) Rate-limit test (manual or scripted)

- Fire >10 requests/sec for 2 seconds.  
- Expect at least one `-32001` response.  
Evidence: .spec/foundation-2026-01-23-ralph-gold-prd-api-spec.md.

## 8) Exit/cleanup

- Send `stop` if a run is active.  
- Terminate subprocess cleanly.  
- Ensure stdout/stderr drained.  
Evidence: docs/VSCODE_BRIDGE_PROTOCOL.md.
