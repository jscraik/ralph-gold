from ralph_gold.agents import build_agent_invocation
from ralph_gold.config import RunnerConfig


def test_generic_agent_uses_stdin_when_dash_present():
    prompt = "hello world"
    argv, stdin = build_agent_invocation(
        "custom-agent",
        prompt,
        RunnerConfig(argv=["my-wrapper", "-"]),
    )
    assert argv == ["my-wrapper", "-"]
    assert stdin == prompt

