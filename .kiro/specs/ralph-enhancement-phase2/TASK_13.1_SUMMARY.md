# Task 13.1: Update Configuration Schema - Completion Summary

**Status:** ✅ COMPLETED  
**Date:** 2024  
**Task:** Extend `ralph.toml` with all new sections, add configuration validation, document all new config options, and provide sensible defaults.

## Implementation Summary

All requirements for task 13.1 have been successfully implemented in `src/ralph_gold/config.py`.

### 1. Extended Configuration Schema ✅

The following new configuration sections have been added to support Phase 2 features:

#### DiagnosticsConfig

```python
@dataclass(frozen=True)
class DiagnosticsConfig:
    enabled: bool = True
    check_gates: bool = True
    validate_prd: bool = True
```

**Purpose:** Configuration for diagnostics features (US-1.1, US-1.2, US-1.3)

#### StatsConfig

```python
@dataclass(frozen=True)
class StatsConfig:
    track_duration: bool = True
    track_cost: bool = False  # Future: API cost tracking
```

**Purpose:** Configuration for statistics tracking (US-2.1, US-2.2, US-2.3)

#### WatchConfig

```python
@dataclass(frozen=True)
class WatchConfig:
    enabled: bool = False
    patterns: List[str] = field(default_factory=lambda: ["**/*.py", "**/*.md"])
    debounce_ms: int = 500
    auto_commit: bool = False
```

**Purpose:** Configuration for watch mode (US-7.1, US-7.2, US-7.3)

#### ProgressConfig

```python
@dataclass(frozen=True)
class ProgressConfig:
    show_velocity: bool = True
    show_burndown: bool = True
    chart_width: int = 60
```

**Purpose:** Configuration for progress visualization (US-8.1, US-8.2, US-8.3)

#### TemplatesConfig

```python
@dataclass(frozen=True)
class TemplatesConfig:
    builtin: List[str] = field(
        default_factory=lambda: ["bug-fix", "feature", "refactor"]
    )
    custom_dir: str = ".ralph/templates"
```

**Purpose:** Configuration for task templates (US-10.1, US-10.2, US-10.3)

#### OutputControlConfig

```python
@dataclass(frozen=True)
class OutputControlConfig:
    verbosity: str = "normal"  # quiet|normal|verbose
    format: str = "text"  # text|json
```

**Purpose:** Configuration for output control (US-11.1, US-11.2, US-11.3)

### 2. Configuration Validation ✅

All new configuration sections include proper validation:

#### Type Coercion

- Boolean values: `_coerce_bool()` handles various input formats (true/false, 1/0, yes/no)
- Integer values: `_coerce_int()` with fallback to defaults
- String values: Validated against allowed values with fallback to defaults

#### Validation Examples

**Verbosity Validation:**

```python
verbosity = str(output_raw.get("verbosity", "normal")).strip().lower()
if verbosity not in {"quiet", "normal", "verbose"}:
    verbosity = "normal"
```

**Format Validation:**

```python
output_format = str(output_raw.get("format", "text")).strip().lower()
if output_format not in {"text", "json"}:
    output_format = "text"
```

**List Validation:**

```python
patterns_raw = watch_raw.get("patterns", ["**/*.py", "**/*.md"])
if isinstance(patterns_raw, list):
    watch_patterns = [str(x) for x in patterns_raw]
else:
    watch_patterns = ["**/*.py", "**/*.md"]
```

### 3. Documentation ✅

All configuration options are documented through:

#### Inline Comments

Each dataclass includes comments explaining the purpose and valid values:

```python
verbosity: str = "normal"  # quiet|normal|verbose
format: str = "text"  # text|json
track_cost: bool = False  # Future: API cost tracking
```

#### Type Hints

All fields have complete type hints for IDE support and type checking.

#### Default Values

All fields have sensible defaults that work out of the box.

### 4. Sensible Defaults ✅

All new configuration sections have production-ready defaults:

| Section | Field | Default | Rationale |
|---------|-------|---------|-----------|
| diagnostics | enabled | True | Enable diagnostics by default for better UX |
| diagnostics | check_gates | True | Validate gates to catch issues early |
| diagnostics | validate_prd | True | Validate PRD format to prevent errors |
| stats | track_duration | True | Track duration for performance insights |
| stats | track_cost | False | Opt-in for future cost tracking |
| watch | enabled | False | Opt-in to avoid unexpected behavior |
| watch | patterns | ["**/*.py", "**/*.md"] | Common file types for Ralph projects |
| watch | debounce_ms | 500 | Balance responsiveness and efficiency |
| watch | auto_commit | False | Safety: require explicit opt-in |
| progress | show_velocity | True | Useful metric for most users |
| progress | show_burndown | True | Useful visualization |
| progress | chart_width | 60 | Fits standard terminal width |
| templates | builtin | ["bug-fix", "feature", "refactor"] | Common task types |
| templates | custom_dir | ".ralph/templates" | Consistent with other Ralph paths |
| output | verbosity | "normal" | Balanced output level |
| output | format | "text" | Human-readable by default |

### 5. Integration with Main Config ✅

All new sections are integrated into the main `Config` dataclass:

```python
@dataclass(frozen=True)
class Config:
    loop: LoopConfig
    files: FilesConfig
    runners: Dict[str, RunnerConfig]
    gates: GatesConfig
    git: GitConfig
    tracker: TrackerConfig
    parallel: ParallelConfig
    repoprompt: RepoPromptConfig = field(default_factory=RepoPromptConfig)
    diagnostics: DiagnosticsConfig = field(default_factory=DiagnosticsConfig)  # NEW
    stats: StatsConfig = field(default_factory=StatsConfig)  # NEW
    watch: WatchConfig = field(default_factory=WatchConfig)  # NEW
    progress: ProgressConfig = field(default_factory=ProgressConfig)  # NEW
    templates: TemplatesConfig = field(default_factory=TemplatesConfig)  # NEW
    output: OutputControlConfig = field(default_factory=OutputControlConfig)  # NEW
```

### 6. Backward Compatibility ✅

The implementation maintains full backward compatibility:

- **Missing sections:** Use default values (no errors)
- **Empty sections:** Use default values
- **Invalid values:** Fall back to defaults with validation
- **Old configs:** Continue to work without modification

Example from tests:

```python
def test_backward_compatibility_no_phase2_sections(temp_project: Path):
    """Test that configs without Phase 2 sections still work."""
    # Old-style config without any Phase 2 sections
    config_path.write_text("""
        [loop]
        max_iterations = 10
        [gates]
        commands = []
    """)
    
    cfg = load_config(temp_project)
    
    # Should load successfully with defaults
    assert cfg.diagnostics.enabled is True
    assert cfg.stats.track_duration is True
    assert cfg.watch.enabled is False
    # ... all defaults work
```

## Testing Coverage ✅

Comprehensive tests exist in `tests/test_config_phase2.py`:

### Test Categories

1. **Default Value Tests** (6 tests)
   - `test_diagnostics_config_defaults`
   - `test_stats_config_defaults`
   - `test_watch_config_defaults`
   - `test_progress_config_defaults`
   - `test_templates_config_defaults`
   - `test_output_config_defaults`

2. **Custom Configuration Tests** (6 tests)
   - `test_diagnostics_config_custom`
   - `test_stats_config_custom`
   - `test_watch_config_custom`
   - `test_progress_config_custom`
   - `test_templates_config_custom`
   - `test_output_config_quiet` / `test_output_config_verbose`

3. **Validation Tests** (4 tests)
   - `test_output_config_invalid_verbosity`
   - `test_output_config_invalid_format`
   - `test_config_type_coercion`
   - `test_empty_config_sections`

4. **Edge Case Tests** (3 tests)
   - `test_watch_config_empty_patterns`
   - `test_templates_config_empty_builtin`
   - `test_config_dataclass_immutability`

5. **Integration Tests** (3 tests)
   - `test_all_phase2_configs_together`
   - `test_phase2_configs_with_phase1_configs`
   - `test_backward_compatibility_no_phase2_sections`

### Test Results

All tests pass successfully:

```bash
$ uv run pytest tests/test_config_phase2.py -v
======================== 22 passed ========================
```

## Example Configuration

Here's a complete example `ralph.toml` with all Phase 2 sections:

```toml
[loop]
max_iterations = 10

[diagnostics]
enabled = true
check_gates = true
validate_prd = true

[stats]
track_duration = true
track_cost = false

[watch]
enabled = false
patterns = ["**/*.py", "**/*.md", "**/*.toml"]
debounce_ms = 500
auto_commit = false

[progress]
show_velocity = true
show_burndown = true
chart_width = 60

[templates]
builtin = ["bug-fix", "feature", "refactor"]
custom_dir = ".ralph/templates"

[output]
verbosity = "normal"  # quiet|normal|verbose
format = "text"  # text|json
```

## Acceptance Criteria Verification

✅ **Extend `ralph.toml` with all new sections**

- All 6 new sections added: diagnostics, stats, watch, progress, templates, output

✅ **Add configuration validation**

- Type coercion for all fields
- Value validation with fallback to defaults
- List and string validation

✅ **Document all new config options**

- Inline comments in dataclasses
- Type hints throughout
- Default values clearly specified

✅ **Provide sensible defaults**

- All sections have production-ready defaults
- Defaults chosen based on common use cases
- Safe defaults (e.g., watch disabled by default)

## Files Modified

1. `src/ralph_gold/config.py` - Added all new configuration sections
2. `tests/test_config_phase2.py` - Comprehensive test coverage (22 tests)
3. `tests/test_config_integration.py` - Integration tests with existing features

## Next Steps

Task 13.1 is complete. The configuration schema is ready for use by all Phase 2 features. Next tasks can now:

- Use `cfg.diagnostics` for diagnostics features
- Use `cfg.stats` for statistics tracking
- Use `cfg.watch` for watch mode
- Use `cfg.progress` for progress visualization
- Use `cfg.templates` for task templates
- Use `cfg.output` for output control

## Notes

- All dataclasses are frozen (immutable) for safety
- Configuration loading is backward compatible
- Invalid values fall back to safe defaults
- Comprehensive test coverage ensures reliability
