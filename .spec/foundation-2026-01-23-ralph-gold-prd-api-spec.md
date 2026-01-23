schema_version: 1
# API Spec — Ralph Gold VS Code Bridge (JSON-RPC v1)

## 1) API purpose and scope

Define the JSON-RPC 2.0 contract for the local VS Code bridge (`ralph bridge`) used to control loop execution and query status. Scope is local IPC over stdio; no remote network exposure.  
Evidence: docs/VSCODE_BRIDGE_PROTOCOL.md; .spec/foundation-2026-01-23-ralph-gold-prd.md.

## 2) Auth and authorization model

- AuthN: none (local process run by the current OS user).  
- AuthZ: relies on filesystem permissions and the authorization guard for write operations.  
- Secrets/PII: do not include secrets in params; treat `.ralph/*` as sensitive artifacts.  
Evidence: docs/VSCODE_BRIDGE_PROTOCOL.md; docs/AUTHORIZATION.md; AGENTS.md.

## 3) Endpoint catalog (method, path, description)

Transport: newline-delimited JSON-RPC 2.0 over stdio. There are no HTTP paths.  
Evidence: docs/VSCODE_BRIDGE_PROTOCOL.md.

| Method | Description |
| --- | --- |
| `ping` | Health check and bridge metadata. |
| `status` | Current PRD progress + run state. |
| `step` | Run exactly one iteration. |
| `run` | Start background loop run. |
| `stop` | Stop background loop. |
| `pause` | Pause background loop. |
| `resume` | Resume background loop. |

## 4) Request/response schemas (examples + field constraints)

### Base request
```json
{"jsonrpc":"2.0","id":1,"method":"status","params":{}}
```

Schema:
- `jsonrpc` (string, required) = "2.0"
- `id` (string|number, required for request/response; omitted for notifications)
- `method` (string, required)
- `params` (object, optional)

### Base response
```json
{"jsonrpc":"2.0","id":1,"result":{}}
```

### Error response
```json
{"jsonrpc":"2.0","id":1,"error":{"code":-32603,"message":"Internal error","data":{}}}
```

#### Method: `ping`
Params: `{}`  
Result:
- `ok` (bool)
- `version` (string)
- `cwd` (string)
- `time` (string, UTC)

#### Method: `status`
Params: `{}`  
Result:
- `version` (string)
- `cwd` (string)
- `prd` (string)
- `progress` (string)
- `agents` (array of string)
- `prompt` (string)
- `done` (int)
- `total` (int)
- `next` (object|null): `{task_id,title,kind}`
- `running` (bool)
- `paused` (bool)
- `activeRunId` (string|null)
- `last` (object|null) minimal state from `.ralph/state.json`

`agents` schema (array of string):  
- Example: `["codex","claude","copilot"]`

`last` schema (minimum fields):  
- `iteration_id` (string)  
- `task_id` (string)  
- `status` (string)  
- `exit_code` (int)  
- `started_at` (string, ISO-8601)  
- `finished_at` (string, ISO-8601)

#### Method: `step`
Params:
- `agent` (string, optional; default `codex`)

Result:
- `iteration` (int)
- `agent` (string)
- `task_id` (string|null)
- `exit_signal` (bool)
- `return_code` (int)
- `log_path` (string)
- `progress_made` (bool)
- `no_progress_streak` (int)
- `gates_ok` (bool|null)
- `repo_clean` (bool)
- `judge_ok` (bool|null)
- `review_ok` (bool|null)
- `blocked` (bool)
- `attempt_id` (string|null)
- `receipts_dir` (string|null)
- `context_dir` (string|null)
- `task_title` (string|null)

#### Method: `run`
Params:
- `agent` (string, optional; default `codex`)
- `maxIterations` (int, optional)

Result:
- `runId` (string)

#### Method: `stop`
Params: `{}`  
Result:
- `ok` (bool)
- `stopped` (bool)

#### Method: `pause` / `resume`
Params: `{}`  
Result:
- `ok` (bool)
- `runId` (string|null)
- `paused` (bool)

### Notifications (events)
```json
{"jsonrpc":"2.0","method":"event","params":{"type":"iteration_finished", "ts":"..."}}
```
Common fields:
- `type` (string)
- `ts` (string, UTC)

Event types: `bridge_started`, `bridge_stopped`, `run_started`, `run_stopped`, `run_paused`, `run_resumed`, `iteration_started`, `iteration_finished`, `error`.  
Evidence: docs/VSCODE_BRIDGE_PROTOCOL.md.

Event schemas (minimum required fields):
- `bridge_started`: `type`, `ts`, `version`, `cwd`
- `bridge_stopped`: `type`, `ts`
- `run_started`: `type`, `ts`, `runId`, `agent`, `maxIterations`, `startIteration`
- `run_stopped`: `type`, `ts`, `runId`, `reason`
- `run_paused`: `type`, `ts`, `runId`
- `run_resumed`: `type`, `ts`, `runId`
- `iteration_started`: `type`, `ts`, `runId`, `iteration`, `agent`, `task_id` (nullable), `title` (nullable)
- `iteration_finished`: `type`, `ts`, `runId`, `iteration`, `agent`, `task_id` (nullable), `exitSignal`, `returnCode`, `repoClean`, `gatesOk` (nullable), `judgeOk` (nullable), `reviewOk` (nullable), `blocked`, `attemptId` (nullable), `receiptsDir` (nullable), `contextDir` (nullable), `durationSeconds`, `logPath`
- `error`: `type`, `ts`, `runId` (nullable), `message`

## 5) Error model (codes, messages, recovery)

- `-32600` Invalid Request: malformed JSON or missing required fields.  
- `-32601` Method not found: unknown method name.  
- `-32602` Invalid params: params fail validation.  
- `-32603` Internal error: unexpected bridge failure.  
- `-32000` Bridge busy: concurrent run in progress (optional custom code).  
- `-32001` Rate limited: too many requests per second.  
Recovery: client retries for transient errors; do not retry on `-32602` without fixing params.  
Evidence: docs/VSCODE_BRIDGE_PROTOCOL.md.

## 6) Idempotency, pagination, rate limits

- Idempotent: `ping`, `status`, `stop`, `pause`, `resume` (repeated calls safe).  
- Non-idempotent: `step`, `run`.  
- Pagination: not applicable.  
- Rate limits: local clients should limit to <= 10 requests/sec; bridge may throttle above this with `-32001`.  
Evidence: docs/VSCODE_BRIDGE_PROTOCOL.md; local IPC assumption.

## 7) Versioning and compatibility

- Protocol version: `v1` (JSON-RPC 2.0).  
- Backward compatibility: additive fields only; new methods must not break existing clients.  
- Breaking changes require a new version string in `ping` and `status`.  
Evidence: docs/VSCODE_BRIDGE_PROTOCOL.md.

## 8) Validation and quality gates (tests/lint)

- Client/server contract tests for each method response schema.  
- Integration tests for `step`, `run`, `status`, `pause`, `resume`, `stop`.  
- Error tests for invalid params and unknown methods.  
- Commands: `uv run pytest -q`.  
Evidence: AGENTS.md.
