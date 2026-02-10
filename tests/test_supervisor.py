from pathlib import Path

from ralph_gold.config import load_config
from ralph_gold.loop import IterationResult
from ralph_gold.supervisor import run_supervisor


def _write_minimal_project(tmp_path: Path, prd_text: str) -> None:
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()
    (ralph_dir / "PRD.md").write_text(prd_text, encoding="utf-8")
    (ralph_dir / "ralph.toml").write_text(
        """
[tracker]
kind = "markdown"
""".lstrip(),
        encoding="utf-8",
    )


def _fake_iter(
    *,
    iteration: int = 1,
    story_id: str | None = None,
    exit_signal: bool | None = True,
    return_code: int = 0,
    no_progress_streak: int = 0,
) -> IterationResult:
    return IterationResult(
        iteration=iteration,
        agent="codex",
        story_id=story_id,
        exit_signal=exit_signal,
        return_code=return_code,
        log_path=Path("/tmp/ralph-test.log"),
        progress_made=False,
        no_progress_streak=no_progress_streak,
        gates_ok=None,
        repo_clean=True,
        judge_ok=None,
        review_ok=None,
    )


def test_supervise_complete_sends_notification(monkeypatch, tmp_path: Path):
    _write_minimal_project(
        tmp_path,
        """# PRD

## Tasks

- [x] Done
""",
    )
    cfg = load_config(tmp_path)

    sent: list[tuple[str, str]] = []

    def _send_notification(*, title: str, message: str, backend: str = "auto", command_argv=None):
        sent.append((title, message))
        return True

    monkeypatch.setattr("ralph_gold.supervisor.send_notification", _send_notification)
    monkeypatch.setattr("ralph_gold.supervisor.run_iteration", lambda *a, **k: _fake_iter())

    res = run_supervisor(
        tmp_path,
        agent="codex",
        cfg=cfg,
        max_runtime_seconds=0,
        heartbeat_seconds=0,
        sleep_seconds_between_runs=0,
        on_no_progress_limit="stop",
        on_rate_limit="stop",
        notify_enabled=True,
        notify_events=["complete", "stopped", "error"],
        notify_backend="none",
        notify_command_argv=[],
    )

    assert res.exit_code == 0
    assert res.reason == "complete"
    assert sent, "expected notification"
    assert "Complete" in sent[0][1]


def test_supervise_all_blocked_sends_notification(monkeypatch, tmp_path: Path):
    _write_minimal_project(
        tmp_path,
        """# PRD

## Tasks

- [-] Blocked
""",
    )
    cfg = load_config(tmp_path)

    sent: list[str] = []

    def _send_notification(*, title: str, message: str, backend: str = "auto", command_argv=None):
        sent.append(message)
        return True

    monkeypatch.setattr("ralph_gold.supervisor.send_notification", _send_notification)
    monkeypatch.setattr(
        "ralph_gold.supervisor.run_iteration",
        lambda *a, **k: _fake_iter(return_code=1, story_id=None, exit_signal=True),
    )

    res = run_supervisor(
        tmp_path,
        agent="codex",
        cfg=cfg,
        max_runtime_seconds=0,
        heartbeat_seconds=0,
        sleep_seconds_between_runs=0,
        on_no_progress_limit="stop",
        on_rate_limit="stop",
        notify_enabled=True,
        notify_events=["complete", "stopped", "error"],
        notify_backend="none",
        notify_command_argv=[],
    )

    assert res.exit_code == 1
    assert res.reason == "all_blocked"
    assert sent
    assert "all blocked" in sent[0].lower()


def test_supervise_rate_limit_waits_then_completes(monkeypatch, tmp_path: Path):
    _write_minimal_project(
        tmp_path,
        """# PRD

## Tasks

- [x] Done
""",
    )
    cfg = load_config(tmp_path)

    sleeps: list[int] = []
    sent: list[str] = []

    def _sleep(n: int):
        sleeps.append(int(n))

    calls = {"rl": 0}

    def _rate_limit_ok(_state, _per_hour):
        calls["rl"] += 1
        if calls["rl"] == 1:
            return False, 1
        return True, 0

    def _send_notification(*, title: str, message: str, backend: str = "auto", command_argv=None):
        sent.append(message)
        return True

    monkeypatch.setattr("ralph_gold.supervisor.time.sleep", _sleep)
    monkeypatch.setattr("ralph_gold.supervisor._rate_limit_ok", _rate_limit_ok)
    monkeypatch.setattr("ralph_gold.supervisor.send_notification", _send_notification)
    monkeypatch.setattr("ralph_gold.supervisor.run_iteration", lambda *a, **k: _fake_iter())

    res = run_supervisor(
        tmp_path,
        agent="codex",
        cfg=cfg,
        max_runtime_seconds=0,
        heartbeat_seconds=0,
        sleep_seconds_between_runs=0,
        on_no_progress_limit="stop",
        on_rate_limit="wait",
        notify_enabled=True,
        notify_events=["complete", "stopped", "error"],
        notify_backend="none",
        notify_command_argv=[],
    )

    assert sleeps and sleeps[0] == 1
    assert res.exit_code == 0
    assert res.reason == "complete"


def test_supervise_no_progress_stops(monkeypatch, tmp_path: Path):
    _write_minimal_project(
        tmp_path,
        """# PRD

## Tasks

- [ ] Open
""",
    )
    cfg = load_config(tmp_path)

    sent: list[str] = []

    def _send_notification(*, title: str, message: str, backend: str = "auto", command_argv=None):
        sent.append(message)
        return True

    monkeypatch.setattr("ralph_gold.supervisor.send_notification", _send_notification)
    monkeypatch.setattr(
        "ralph_gold.supervisor.run_iteration",
        lambda *a, **k: _fake_iter(exit_signal=False, no_progress_streak=cfg.loop.no_progress_limit),
    )

    res = run_supervisor(
        tmp_path,
        agent="codex",
        cfg=cfg,
        max_runtime_seconds=0,
        heartbeat_seconds=0,
        sleep_seconds_between_runs=0,
        on_no_progress_limit="stop",
        on_rate_limit="stop",
        notify_enabled=True,
        notify_events=["complete", "stopped", "error"],
        notify_backend="none",
        notify_command_argv=[],
    )

    assert res.exit_code == 1
    assert res.reason == "no_progress"
    assert sent
    assert "no progress" in sent[0].lower()
