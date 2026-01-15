from __future__ import annotations

import json
import sys
import threading
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from . import __version__
from .config import Config, load_config
from .loop import IterationResult, next_iteration_number, run_iteration
from .trackers import make_tracker


def _utc_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


class JsonRpcError(Exception):
    def __init__(self, code: int, message: str, data: Any | None = None):
        super().__init__(message)
        self.code = int(code)
        self.message = str(message)
        self.data = data


class BridgeServer:
    """JSON-RPC 2.0 bridge over stdio (NDJSON).

    Designed to be spawned by a VS Code extension:
    - stdin: JSON-RPC requests (one JSON object per line)
    - stdout: JSON-RPC responses + event notifications (one JSON object per line)

    The bridge never attempts to control the editor; it only orchestrates the
    Golden Ralph Loop in the current repo.
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self._write_lock = threading.Lock()

        self._run_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        self._active_run_id: Optional[str] = None

    # -------------------------
    # I/O helpers
    # -------------------------

    def _send(self, obj: Dict[str, Any]) -> None:
        line = json.dumps(obj, ensure_ascii=False)
        with self._write_lock:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()

    def _respond(self, req_id: Any, result: Any) -> None:
        self._send({"jsonrpc": "2.0", "id": req_id, "result": result})

    def _error(self, req_id: Any, code: int, message: str, data: Any | None = None) -> None:
        err: Dict[str, Any] = {"code": int(code), "message": str(message)}
        if data is not None:
            err["data"] = data
        self._send({"jsonrpc": "2.0", "id": req_id, "error": err})

    def _event(self, event_type: str, **params: Any) -> None:
        payload = {"type": event_type, "ts": _utc_ts(), **params}
        self._send({"jsonrpc": "2.0", "method": "event", "params": payload})

    # -------------------------
    # State
    # -------------------------

    def _cfg(self) -> Config:
        return load_config(self.project_root)

    def _status(self) -> Dict[str, Any]:
        cfg = self._cfg()
        tracker = make_tracker(self.project_root, cfg)
        done, total = 0, 0
        next_task = None

        try:
            done, total = tracker.counts()
        except Exception:
            done, total = 0, 0

        try:
            t = tracker.peek_next_task()
            if t is not None:
                next_task = {"id": t.id, "title": t.title, "kind": t.kind}
        except Exception:
            next_task = None

        state_path = self.project_root / ".ralph" / "state.json"
        last = None
        if state_path.exists():
            try:
                state = json.loads(state_path.read_text(encoding="utf-8"))
                hist = state.get("history", [])
                if isinstance(hist, list) and hist:
                    last_entry = hist[-1]
                    if isinstance(last_entry, dict):
                        last = last_entry
            except Exception:
                last = None

        return {
            "version": __version__,
            "cwd": str(self.project_root),
            "prd": cfg.files.prd,
            "progress": cfg.files.progress,
            "agents": cfg.files.agents,
            "prompt": cfg.files.prompt,
            "done": done,
            "total": total,
            "next": next_task,
            "running": self._run_thread is not None and self._run_thread.is_alive(),
            "paused": bool(self._pause_event.is_set()),
            "activeRunId": self._active_run_id,
            "last": last,
        }

    # -------------------------
    # Commands
    # -------------------------

    def _ensure_not_running(self) -> None:
        if self._run_thread is not None and self._run_thread.is_alive():
            raise JsonRpcError(409, "A run is already active")

    def _handle_ping(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "ok": True,
            "version": __version__,
            "cwd": str(self.project_root),
            "time": _utc_ts(),
        }

    def _handle_status(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return self._status()

    def _iter_result_to_dict(self, res: IterationResult) -> Dict[str, Any]:
        return {
            "iteration": res.iteration,
            "agent": res.agent,
            "story_id": res.story_id,
            "exit_signal": res.exit_signal,
            "return_code": res.return_code,
            "log_path": str(res.log_path),
            "progress_made": res.progress_made,
            "no_progress_streak": res.no_progress_streak,
            "gates_ok": res.gates_ok,
            "repo_clean": res.repo_clean,
            "judge_ok": res.judge_ok,
        }

    def _handle_step(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_not_running()

        agent = str(params.get("agent") or "codex")
        cfg = self._cfg()
        tracker = make_tracker(self.project_root, cfg)

        # Preselect for deterministic event emission; pass into run_iteration to avoid drift.
        try:
            task = tracker.peek_next_task()
        except Exception:
            task = None

        iter_n = next_iteration_number(self.project_root)
        run_id = f"manual-{_utc_ts()}"

        self._event(
            "iteration_started",
            runId=run_id,
            iteration=iter_n,
            agent=agent,
            storyId=(task.id if task else None),
            title=(task.title if task else None),
        )

        start = time.time()
        res = run_iteration(self.project_root, agent=agent, cfg=cfg, iteration=iter_n)
        dur = time.time() - start

        self._event(
            "iteration_finished",
            runId=run_id,
            iteration=res.iteration,
            agent=agent,
            storyId=res.story_id,
            exitSignal=res.exit_signal,
            returnCode=res.return_code,
            repoClean=res.repo_clean,
            gatesOk=res.gates_ok,
            judgeOk=res.judge_ok,
            durationSeconds=round(dur, 2),
            logPath=str(res.log_path),
        )

        return self._iter_result_to_dict(res)

    def _start_run_thread(self, agent: str, max_iterations: Optional[int]) -> str:
        self._ensure_not_running()

        self._stop_event.clear()
        self._pause_event.clear()

        run_id = f"run-{_utc_ts()}"
        self._active_run_id = run_id

        cfg = self._cfg()
        limit = int(max_iterations) if max_iterations is not None else int(cfg.loop.max_iterations)
        start_iter = next_iteration_number(self.project_root)

        def worker() -> None:
            reason = "unknown"
            try:
                self._event("run_started", runId=run_id, agent=agent, maxIterations=limit, startIteration=start_iter)

                tracker = make_tracker(self.project_root, cfg)

                for offset in range(limit):
                    if self._stop_event.is_set():
                        reason = "stopped"
                        break

                    while self._pause_event.is_set() and not self._stop_event.is_set():
                        time.sleep(0.2)

                    iter_n = start_iter + offset

                    try:
                        task = tracker.peek_next_task()
                    except Exception:
                        task = None

                    self._event(
                        "iteration_started",
                        runId=run_id,
                        iteration=iter_n,
                        agent=agent,
                        storyId=(task.id if task else None),
                        title=(task.title if task else None),
                    )

                    start = time.time()
                    res = run_iteration(
                        self.project_root,
                        agent=agent,
                        cfg=cfg,
                        iteration=iter_n,
                    )
                    dur = time.time() - start

                    self._event(
                        "iteration_finished",
                        runId=run_id,
                        iteration=res.iteration,
                        agent=agent,
                        storyId=res.story_id,
                        exitSignal=res.exit_signal,
                        returnCode=res.return_code,
                        repoClean=res.repo_clean,
                        gatesOk=res.gates_ok,
                        judgeOk=res.judge_ok,
                        durationSeconds=round(dur, 2),
                        logPath=str(res.log_path),
                    )

                    # Stop conditions mirror the CLI run_loop.
                    try:
                        done = tracker.all_done()
                    except Exception:
                        done = False

                    if res.no_progress_streak >= cfg.loop.no_progress_limit:
                        reason = "no_progress"
                        break

                    if done and res.exit_signal is True:
                        reason = "complete"
                        break

                    if cfg.loop.sleep_seconds_between_iters > 0:
                        time.sleep(cfg.loop.sleep_seconds_between_iters)

                else:
                    reason = "max_iterations"

            except Exception as e:
                reason = "error"
                self._event("error", runId=run_id, message=str(e))
            finally:
                self._event("run_stopped", runId=run_id, reason=reason)
                self._active_run_id = None

        t = threading.Thread(target=worker, name="ralph-bridge-run", daemon=True)
        self._run_thread = t
        t.start()
        return run_id

    def _handle_run(self, params: Dict[str, Any]) -> Dict[str, Any]:
        agent = str(params.get("agent") or "codex")
        max_iter = params.get("maxIterations")
        if max_iter is None:
            max_iterations = None
        else:
            try:
                max_iterations = int(max_iter)
            except Exception:
                raise JsonRpcError(400, "maxIterations must be an integer")

        run_id = self._start_run_thread(agent=agent, max_iterations=max_iterations)
        return {"runId": run_id}

    def _handle_stop(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if self._run_thread is None or not self._run_thread.is_alive():
            return {"ok": True, "stopped": False}
        self._stop_event.set()
        self._pause_event.clear()
        return {"ok": True, "stopped": True}

    def _handle_pause(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if self._run_thread is None or not self._run_thread.is_alive():
            return {"ok": True, "paused": False}
        self._pause_event.set()
        self._event("run_paused", runId=self._active_run_id)
        return {"ok": True, "paused": True}

    def _handle_resume(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if self._run_thread is None or not self._run_thread.is_alive():
            return {"ok": True, "paused": False}
        self._pause_event.clear()
        self._event("run_resumed", runId=self._active_run_id)
        return {"ok": True, "paused": False}

    # -------------------------
    # Main loop
    # -------------------------

    def serve(self) -> None:
        """Serve until stdin closes."""

        self._event("bridge_started", version=__version__, cwd=str(self.project_root))

        while True:
            line = sys.stdin.readline()
            if not line:
                break
            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
            except Exception:
                # Ignore non-JSON noise.
                continue

            if not isinstance(msg, dict):
                continue

            # JSON-RPC request
            req_id = msg.get("id")
            method = msg.get("method")
            params = msg.get("params") or {}
            if not isinstance(params, dict):
                params = {}

            # Notifications (no id) can be ignored.
            if req_id is None:
                continue

            try:
                if method == "ping":
                    result = self._handle_ping(params)
                elif method == "status":
                    result = self._handle_status(params)
                elif method == "step":
                    result = self._handle_step(params)
                elif method == "run":
                    result = self._handle_run(params)
                elif method == "stop":
                    result = self._handle_stop(params)
                elif method == "pause":
                    result = self._handle_pause(params)
                elif method == "resume":
                    result = self._handle_resume(params)
                else:
                    raise JsonRpcError(404, f"Unknown method: {method}")

                self._respond(req_id, result)

            except JsonRpcError as e:
                self._error(req_id, e.code, e.message, e.data)
            except Exception as e:
                self._error(req_id, -32603, "Internal error", {"message": str(e)})

        # Attempt to stop an active run before exit.
        self._stop_event.set()
        self._pause_event.clear()
        self._event("bridge_stopped")
