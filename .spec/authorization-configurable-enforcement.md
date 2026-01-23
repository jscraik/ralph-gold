# Authorization Configurable Enforcement Mode

**Date**: 2026-01-20
**Enhancement**: 3 - Authorization with Configurable Enforcement Mode
**Status**: ✅ IMPLEMENTED

---

## Overview

This enhancement adds configurable enforcement modes to the ralph-gold authorization system, allowing users to choose between:
- **Warn mode** (default): Log warnings but allow operations (soft enforcement)
- **Block mode**: Raise exceptions to block unauthorized operations (hard enforcement)

This resolves the ambiguity in the original specification about whether authorization should be soft-warning or hard-block.

---

## Configuration

### TOML Configuration (`.ralph/ralph.toml`)

```toml
[authorization]
enabled = true
enforcement_mode = "warn"  # or "block"
fallback_to_full_auto = false
permissions_file = ".ralph/permissions.json"
```

### Permissions JSON (`.ralph/permissions.json`)

```json
{
  "enabled": true,
  "enforcement_mode": "warn",
  "fallback_to_full_auto": false,
  "permissions": [
    {
      "pattern": "src/**",
      "allow_write": true,
      "reason": "Source code files"
    },
    {
      "pattern": ".git/**",
      "allow_write": false,
      "reason": "Git internals - blocked"
    }
  ]
}
```

---

## Enforcement Modes

### WARN Mode (Default)

**Behavior**: Logs a warning but allows the operation to proceed.

**Use case**: Development environments where you want visibility into potential violations without blocking work.

**Example output**:
```
WARNING  Authorization check failed for /path/to/file: Denied: matches .git/**
```

**Configuration**:
```toml
[authorization]
enforcement_mode = "warn"
```

### BLOCK Mode

**Behavior**: Raises `AuthorizationError` exception to block the operation.

**Use case**: Production environments or sensitive projects where strict enforcement is required.

**Example output**:
```
ERROR  Authorization blocked: Write not permitted: Denied: matches .git/**
```

**Configuration**:
```toml
[authorization]
enforcement_mode = "block"
```

---

## Implementation Details

### Code Changes

**1. `authorization.py`**
- Added `EnforcementMode` enum (`WARN`, `BLOCK`)
- Added `AuthorizationError` exception class
- Added `enforcement_mode` field to `AuthorizationChecker`
- Modified `check_write_permission()` to raise exception in block mode
- Updated `load_authorization_checker()` to load `enforcement_mode` from config

**2. `config.py`**
- Added `enforcement_mode` field to `AuthorizationConfig` (Literal["warn", "block"])
- Added validation for `enforcement_mode` value (defaults to "warn" if invalid)

**3. `loop.py`**
- Updated authorization check to convert config string to `EnforcementMode` enum
- Wrapped check in try-except to handle `AuthorizationError`
- Skip file write when blocked in block mode

### Behavior Summary

| Scenario | WARN Mode | BLOCK Mode |
|----------|-----------|------------|
| Permission allowed | ✅ Operation proceeds | ✅ Operation proceeds |
| Permission denied | ⚠️ Warning logged, operation proceeds | ❌ Exception raised, operation blocked |
| Authorization disabled | ✅ Operation proceeds | ✅ Operation proceeds |
| `--full-auto` flag | ✅ Operation proceeds | ✅ Operation proceeds |

---

## Migration Path

### For Existing Projects

**No action required** - existing projects will continue to work with WARN mode as the default.

### To Enable Block Mode

1. Update `.ralph/ralph.toml`:
   ```toml
   [authorization]
   enforcement_mode = "block"
   ```

2. Or update `.ralph/permissions.json`:
   ```json
   {
     "enabled": true,
     "enforcement_mode": "block",
     "permissions": [...]
   }
   ```

### To Disable Authorization

Set `enabled = false` in config.

---

## Testing

### Test Coverage

All 32 tests pass, including:

- **EnforcementMode enum tests** (3 tests)
- **AuthorizationError exception tests** (2 tests)
- **Warn mode behavior tests** (4 tests)
- **Block mode behavior tests** (4 tests)
- **Config loading tests** (6 tests)
- **Integration tests** (2 tests)

### Running Tests

```bash
uv run pytest tests/test_authorization.py -v
```

---

## Examples

### Example 1: Warn Mode (Development)

**Config**:
```json
{
  "enabled": true,
  "enforcement_mode": "warn",
  "permissions": [
    {"pattern": "production/**", "allow_write": false, "reason": "Production code"}
  ]
}
```

**Behavior**: When attempting to write to `production/deploy.py`:
```
WARNING  Authorization check failed for production/deploy.py: Denied: Production code
[Operation proceeds anyway]
```

### Example 2: Block Mode (Production)

**Config**:
```json
{
  "enabled": true,
  "enforcement_mode": "block",
  "permissions": [
    {"pattern": "production/**", "allow_write": false, "reason": "Production code"}
  ]
}
```

**Behavior**: When attempting to write to `production/deploy.py`:
```
ERROR  Authorization blocked: Write not permitted: Denied: Production code
[Operation is blocked, file not written]
```

### Example 3: Selective Authorization

**Config**:
```json
{
  "enabled": true,
  "enforcement_mode": "block",
  "permissions": [
    {"pattern": "src/**", "allow_write": true, "reason": "Source code allowed"},
    {"pattern": "tests/**", "allow_write": true, "reason": "Tests allowed"},
    {"pattern": "docs/**", "allow_write": true, "reason": "Docs allowed"},
    {"pattern": ".git/**", "allow_write": false, "reason": "Git blocked"},
    {"pattern": "*.env", "allow_write": false, "reason": "Env files blocked"},
    {"pattern": "*.key", "allow_write": false, "reason": "Private keys blocked"}
  ]
}
```

---

## Rollback Procedure

### To Disable Enforcement

**Method 1: Set to WARN mode**
```toml
[authorization]
enforcement_mode = "warn"
```

**Method 2: Disable authorization entirely**
```toml
[authorization]
enabled = false
```

**Method 3: Emergency bypass**
```bash
# Use --full-auto flag to bypass authorization
ralph run --full-auto
```

---

## Security Considerations

### WARN Mode Risks

- Unauthorized operations may proceed silently
- Relies on developers to notice and act on warnings
- Not suitable for production environments with strict security requirements

### BLOCK Mode Risks

- May break existing workflows if permissions are misconfigured
- Requires careful permission design to avoid false positives
- May require `--full-auto` bypass for legitimate operations

### Recommendations

1. **Start with WARN mode** to observe authorization behavior without blocking
2. **Review warning logs** to identify and fix permission rules
3. **Switch to BLOCK mode** once permissions are well-tuned
4. **Always test permissions** in non-production environments first

---

## Frequently Asked Questions

### Q: What happens if I don't specify `enforcement_mode`?

**A**: Defaults to `"warn"` for backward compatibility and safety.

### Q: Can I change modes without restarting ralph?

**A**: Yes, modes are read from config files on each operation. Changes take effect immediately.

### Q: Does block mode affect all file operations?

**A**: Currently, authorization is checked only for anchor file writes (`ANCHOR.md`). Future enhancements may add checks for other operations.

### Q: What if I need to bypass authorization temporarily?

**A**: Use `--full-auto` flag if `fallback_to_full_auto` is enabled, or set `enabled = false` in config.

### Q: Can I have different enforcement modes for different patterns?

**A**: Not currently. Enforcement mode is global for all authorization checks. This could be added as a future enhancement if needed.

---

## Future Enhancements

Possible future improvements:
1. Pattern-specific enforcement modes (e.g., block for secrets, warn for other files)
2. Additional enforcement modes (e.g., "interactive" to prompt user)
3. Authorization for more file operations beyond anchor writes
4. Permission file validation and linting
5. Interactive setup wizard (`ralph auth init`)

---

**Document Version**: 1
**Last Updated**: 2026-01-20
**Related Specs**:
- `.spec/spec-2026-01-20-security-enhancements-resolution.md`
- `.spec/spec-2026-01-20-security-final-review.md`
