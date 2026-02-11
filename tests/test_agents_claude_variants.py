from ralph_gold.agents import build_agent_invocation
from ralph_gold.config import RunnerConfig


def test_claude_zai_injects_p_flag():
    argv, stdin = build_agent_invocation(
        "claude-zai",
        "do the thing",
        RunnerConfig(argv=["claude-zai"]),
    )
    assert argv[:2] == ["claude-zai", "-p"]
    assert argv[2] == "do the thing"
    assert stdin is None


def test_claude_kimi_injects_p_flag():
    argv, stdin = build_agent_invocation(
        "claude-kimi",
        "do the thing",
        RunnerConfig(argv=["claude-kimi"]),
    )
    assert argv[:2] == ["claude-kimi", "-p"]
    assert argv[2] == "do the thing"
    assert stdin is None

