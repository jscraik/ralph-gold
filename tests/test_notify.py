from ralph_gold.notify import send_notification


def test_send_notification_command_backend_builds_argv(monkeypatch):
    calls = []

    def _run_subprocess(argv, **kwargs):
        calls.append(list(argv))

        class R:
            returncode = 0

        return R()

    monkeypatch.setattr("ralph_gold.notify.run_subprocess", _run_subprocess)

    ok = send_notification(
        title="T",
        message="M",
        backend="command",
        command_argv=["my-notify", "--flag"],
    )
    assert ok is True
    assert calls == [["my-notify", "--flag", "T", "M"]]

