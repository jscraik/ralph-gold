from pathlib import Path

from ralph_gold.config import load_config
from ralph_gold.doctor import check_tools


def test_doctor_checks_configured_runner_bins(tmp_path: Path):
    ralph_dir = tmp_path / ".ralph"
    ralph_dir.mkdir()

    (ralph_dir / "ralph.toml").write_text(
        """
[runners.custom-agent]
argv = ["custom-agent", "--flag"]
""".lstrip(),
        encoding="utf-8",
    )

    cfg = load_config(tmp_path)
    tools = check_tools(cfg)
    names = [t.name for t in tools]
    assert "custom-agent" in names

