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
- `PROMPT.md`, `AGENTS.md`, PRD file, `progress.md`
- `.ralph/state.json`, `.ralph/logs/*`

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
- `next` (nullable): `{id,title,kind}`
- `running`: boolean
- `paused`: boolean
- `activeRunId`: nullable
- `last`: nullable (last iteration entry from `.ralph/state.json`)

### `step`
Runs exactly one Ralph iteration (fresh agent invocation).

Params:
- `agent` (optional, default: `codex`)

Result:
- `iteration`, `agent`, `story_id`
- `exit_signal`
- `return_code`
- `log_path`
- `progress_made`
- `no_progress_streak`
- `gates_ok`
- `repo_clean`

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
- `storyId` (nullable)
- `title` (nullable)

### `iteration_finished`
Fields:
- `runId`, `iteration`, `agent`
- `storyId` (nullable)
- `exitSignal`
- `returnCode`
- `repoClean`
- `gatesOk` (nullable)
- `durationSeconds`
- `logPath`

### `error`
Fields:
- `runId`
- `message`
