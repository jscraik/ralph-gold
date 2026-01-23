# VS Code Bridge Protocol (v1)

The **Golden Ralph Loop** can be controlled from VS Code using a **JSON-RPC 2.0** bridge over **stdio**.

Transport:
- Newline-delimited JSON (one JSON object per line)
- Requests flow **stdin → bridge**, responses/events flow **bridge → stdout**

The bridge is started with:

```bash
ralph bridge
```

The process runs in the project root (cwd) and uses the same files as the CLI:
- `ralph.toml`
- `PROMPT_build.md`, `PROMPT_plan.md`, `PROMPT_judge.md`, `PROMPT_review.md`, `PROMPT.md`, `AGENTS.md`, PRD file, `progress.md`, `FEEDBACK.md`
- `.ralph/state.json`, `.ralph/logs/*`
- `.ralph/receipts/*`, `.ralph/context/*`, `.ralph/attempts/*`

---

## Request / Response format

Requests:

```json
{"jsonrpc":"2.0","id":1,"method":"status","params":{}}
```

Responses:

```json
{"jsonrpc":"2.0","id":1,"result":{...}}
```

Errors:

```json
{"jsonrpc":"2.0","id":1,"error":{"code":-32603,"message":"Internal error","data":{...}}}
```

Standard error codes:
- `-32600` Invalid Request
- `-32601` Method not found
- `-32602` Invalid params
- `-32603` Internal error
- `-32001` Rate limited

Notifications (events):

```json
{"jsonrpc":"2.0","method":"event","params":{"type":"iteration_finished", ...}}
```

---

## Methods

### `ping`
Health check.

Params: `{}`

Result:
- `ok: true`
- `version`
- `cwd`
- `time` (UTC)

### `status`
Returns current PRD progress + run state.

Params: `{}`

Result fields:
- `version`
- `cwd`
- `prd`, `progress`, `agents`, `prompt`
- `done`, `total`
- `next` (nullable): `{task_id,title,kind}`
- `running`: boolean
- `paused`: boolean
- `activeRunId`: nullable
- `last`: nullable (last iteration entry from `.ralph/state.json`)

Minimum `last` fields:
- `iteration_id`
- `task_id`
- `status`
- `exit_code`
- `started_at`
- `finished_at`

### `step`
Runs exactly one Ralph iteration (fresh agent invocation).

Params:
- `agent` (optional, default: `codex`)

Result:
- `iteration`, `agent`, `task_id`
- `exit_signal`
- `return_code`
- `log_path`
- `progress_made`
- `no_progress_streak`
- `gates_ok`
- `repo_clean`
- `judge_ok` (nullable)
- `review_ok` (nullable)
- `blocked` (boolean)
- `attempt_id` (nullable)
- `receipts_dir` (nullable)
- `context_dir` (nullable)
- `task_title` (nullable)

### `run`
Starts a long-running loop in a background thread.

Params:
- `agent` (optional, default: `codex`)
- `maxIterations` (optional; if omitted uses `loop.max_iterations` from `ralph.toml`)

Result:
- `runId`

### `stop`
Signals the background run to stop.

Params: `{}`

Result:
- `ok: true`
- `stopped: true|false`

### `pause` / `resume`
Pauses/resumes an active background run.

Result:
- `ok: true|false`
- `runId` (nullable)
- `paused` (boolean)

---

## Events

All events are emitted as JSON-RPC notifications with method `event`.

Common fields:
- `type`: event type
- `ts`: UTC timestamp

### `bridge_started`
Emitted once when the bridge starts.

### `bridge_stopped`
Emitted once when the bridge is exiting.

### `run_started`
Fields:
- `runId`, `agent`, `maxIterations`, `startIteration`

### `run_stopped`
Fields:
- `runId`, `reason` (`complete|no_progress|max_iterations|stopped|error|unknown`)

### `run_paused` / `run_resumed`
Fields:
- `runId`

### `iteration_started`
Fields:
- `runId`, `iteration`, `agent`
- `task_id` (nullable)
- `title` (nullable)

### `iteration_finished`
Fields:
- `runId`, `iteration`, `agent`
- `task_id` (nullable)
- `exitSignal`
- `returnCode`
- `repoClean`
- `gatesOk` (nullable)
- `judgeOk` (nullable)
- `reviewOk` (nullable)
- `blocked` (boolean)
- `attemptId` (nullable)
- `receiptsDir` (nullable)
- `contextDir` (nullable)
- `durationSeconds`
- `logPath`

### `error`
Fields:
- `runId`
- `message`
