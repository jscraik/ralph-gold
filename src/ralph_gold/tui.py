from __future__ import annotations

import curses
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import load_config
from .loop import IterationResult, _resolve_loop_mode, next_iteration_number, run_iteration
from .trackers import make_tracker


@dataclass
class _RunState:
    running: bool = False
    mode: str = "idle"  # idle|step|run
    agent: str = "codex"
    target_iters: int = 0
    done_iters: int = 0
    last_result: Optional[IterationResult] = None
    error: Optional[str] = None


def _read_last_history(project_root: Path) -> dict:
    state_path = project_root / ".ralph" / "state.json"
    try:
        import json

        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            hist = state.get("history")
            if isinstance(hist, list) and hist:
                last = hist[-1]
                if isinstance(last, dict):
                    return last
    except Exception:
        return {}
    return {}


def _tail_text(path: Path, max_lines: int = 20) -> str:
    try:
        if not path.exists():
            return ""
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        tail = lines[-max_lines:]
        return "\n".join(tail)
    except Exception:
        return ""


def run_tui(project_root: Path) -> int:
    """A minimal interactive control surface.

    Keys:
      s: run one iteration
      r: run N iterations (default from config)
      a: cycle agent
      p: pause/resume (run mode only; pause takes effect between iterations)
      q: quit (stop after current iteration)
    """

    cfg = load_config(project_root)
    cfg, _ = _resolve_loop_mode(cfg)
    agents = list(cfg.runners.keys())
    if not agents:
        agents = ["codex"]

    state = _RunState(agent=agents[0])
    stop_flag = threading.Event()
    pause_flag = threading.Event()

    def worker_run(target_iters: int) -> None:
        state.running = True
        state.mode = "run" if target_iters > 1 else "step"
        state.target_iters = target_iters
        state.done_iters = 0
        state.error = None

        try:
            for _ in range(target_iters):
                if stop_flag.is_set():
                    break
                while pause_flag.is_set() and not stop_flag.is_set():
                    time.sleep(0.1)

                iter_n = next_iteration_number(project_root)
                res = run_iteration(project_root, agent=state.agent, cfg=cfg, iteration=iter_n)
                state.last_result = res
                state.done_iters += 1
        except Exception as e:
            state.error = str(e)
        finally:
            state.running = False
            state.mode = "idle"

    def _curses_main(stdscr) -> int:
        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.timeout(200)

        t: Optional[threading.Thread] = None

        while True:
            # Refresh data
            tracker = make_tracker(project_root, cfg)
            try:
                done, total = tracker.counts()
            except Exception:
                done, total = 0, 0
            try:
                next_task = tracker.select_next_task()
            except Exception:
                next_task = None

            last_hist = _read_last_history(project_root)
            last_log_path = None
            if last_hist.get("log"):
                last_log_path = project_root / ".ralph" / "logs" / str(last_hist.get("log"))

            stdscr.erase()
            h, w = stdscr.getmaxyx()

            def add_line(y: int, text: str) -> None:
                if y >= h:
                    return
                clipped = text[: max(0, w - 1)]
                try:
                    stdscr.addstr(y, 0, clipped)
                except Exception:
                    pass

            add_line(0, f"ralph-gold TUI  |  root: {project_root}")
            add_line(1, f"agent: {state.agent}  |  tracker: {cfg.tracker.kind}  |  prd: {cfg.files.prd}")
            add_line(2, f"progress: {done}/{total} done")
            if next_task:
                add_line(3, f"next: {next_task.id}  {next_task.title}")
            else:
                add_line(3, "next: (none)")

            mode = "RUNNING" if state.running else "IDLE"
            if state.running and pause_flag.is_set():
                mode = "PAUSED"
            add_line(5, f"mode: {mode}  |  done_iters: {state.done_iters}/{state.target_iters}")
            if state.last_result:
                lr = state.last_result
                add_line(
                    6,
                    f"last: iter={lr.iteration} rc={lr.return_code} gates={lr.gates_ok} judge={lr.judge_ok} clean={lr.repo_clean} exit={lr.exit_signal}",
                )
                add_line(7, f"log: {lr.log_path}")
            elif last_hist:
                add_line(6, f"last(state): iter={last_hist.get('iteration')} rc={last_hist.get('return_code')} gates={last_hist.get('gates_ok')} clean={last_hist.get('repo_clean')}")
                add_line(7, f"log: {last_hist.get('log')}")

            if state.error:
                add_line(9, f"error: {state.error}")

            add_line(11, "keys: s=step  r=run(max_iterations)  a=cycle agent  p=pause/resume  q=quit")

            # Log tail
            if last_log_path:
                tail = _tail_text(last_log_path, max_lines=max(0, h - 14))
                if tail:
                    add_line(13, "--- last log (tail) ---")
                    for i, line in enumerate(tail.splitlines()[: max(0, h - 14)], start=14):
                        add_line(i, line)

            stdscr.refresh()

            try:
                ch = stdscr.getch()
            except Exception:
                ch = -1

            if ch == -1:
                continue

            key = chr(ch) if 0 <= ch < 256 else ""

            if key.lower() == "q":
                stop_flag.set()
                if t and t.is_alive():
                    # Wait briefly; can't interrupt a running iteration.
                    t.join(timeout=0.5)
                return 0

            if key.lower() == "a":
                if state.running:
                    continue
                idx = agents.index(state.agent) if state.agent in agents else 0
                state.agent = agents[(idx + 1) % len(agents)]

            if key.lower() == "p":
                if not state.running:
                    continue
                if pause_flag.is_set():
                    pause_flag.clear()
                else:
                    pause_flag.set()

            if key.lower() == "s":
                if state.running:
                    continue
                stop_flag.clear()
                pause_flag.clear()
                t = threading.Thread(target=worker_run, args=(1,), daemon=True)
                t.start()

            if key.lower() == "r":
                if state.running:
                    continue
                stop_flag.clear()
                pause_flag.clear()
                iters = int(cfg.loop.max_iterations) if int(cfg.loop.max_iterations) > 0 else 10
                t = threading.Thread(target=worker_run, args=(iters,), daemon=True)
                t.start()

    return curses.wrapper(_curses_main)
