from pathlib import Path
from ralph_gold.config import load_config, SmartGateConfig

def test_smart_gate_config(tmp_path: Path):
    """Test that [gates.smart] is correctly parsed from ralph.toml."""
    config_dir = tmp_path / ".ralph"
    config_dir.mkdir()
    config_file = config_dir / "ralph.toml"
    
    config_file.write_text("""
[gates.smart]
enabled = true
skip_gates_for = ["*.md", "docs/**"]
""", encoding="utf-8")
    
    config = load_config(tmp_path)
    
    assert isinstance(config.gates.smart, SmartGateConfig)
    assert config.gates.smart.enabled is True
    assert config.gates.smart.skip_gates_for == ["*.md", "docs/**"]

def test_smart_gate_config_defaults(tmp_path: Path):
    """Test that [gates.smart] has correct defaults when missing."""
    # Empty config
    config = load_config(tmp_path)
    
    assert isinstance(config.gates.smart, SmartGateConfig)
    assert config.gates.smart.enabled is False
    assert config.gates.smart.skip_gates_for == []
