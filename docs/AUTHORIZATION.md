---
last_validated: 2026-02-28
---

# Authorization System

**Version:** 1.0
**Last Updated:** 2026-01-20
**Review Cadence:** Quarterly
**Audience:** Users and security administrators

---

## Overview

Ralph-gold provides a configurable authorization system to control what files agents can write during loop execution. This helps prevent accidental modifications to sensitive files, configuration, or infrastructure code.

### Key Features

- **Pattern-based permissions** - Use glob patterns to define what agents can modify
- **Enforcement modes** - Choose between warning (soft) or blocking (hard) enforcement
- **Opt-in design** - Disabled by default; enable when needed
- **Flexible bypass** - Support for `--full-auto` flag fallback

---

`★ Insight ─────────────────────────────────────`
**Authorization Architecture:**
1. **Fail-open default** - If no patterns match, operations are allowed (safe default)
2. **Pattern matching** - Uses `fnmatch` for glob patterns like `*.py`, `.git/**`, `src/**`
3. **Checked at write time** - Currently validates anchor file writes (`ANCHOR.md`)
`─────────────────────────────────────────────────`

---

## Quick Start

### 1. Create Permissions File

Create `.ralph/permissions.json` in your project root:

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
      "pattern": "tests/**",
      "allow_write": true,
      "reason": "Test files"
    },
    {
      "pattern": ".git/**",
      "allow_write": false,
      "reason": "Git internals - blocked"
    },
    {
      "pattern": "*.env",
      "allow_write": false,
      "reason": "Environment files blocked"
    }
  ]
}
```

### 2. Configure Enforcement Mode

In `.ralph/ralph.toml`:

```toml
[authorization]
enabled = true
enforcement_mode = "warn"  # or "block"
fallback_to_full_auto = false
permissions_file = ".ralph/permissions.json"
```

### 3. Run the Loop

```bash
ralph run --agent codex
```

Watch for authorization messages in output:
- **WARN mode:** `WARNING  Authorization check failed for ...`
- **BLOCK mode:** `ERROR  Authorization blocked: Write not permitted: ...`

---

## Enforcement Modes

### WARN Mode (Default)

**Behavior:** Logs a warning but allows the operation to proceed.

**Use Case:** Development environments where you want visibility into potential violations without blocking work.

**Configuration:**
```json
{
  "enforcement_mode": "warn"
}
```

**Example Output:**
```
WARNING  Authorization check failed for production/deploy.py: Denied: Production code
[Operation proceeds anyway]
```

**When to Use:**
- Initial setup and testing of permission rules
- Development environments where blocking would be too disruptive
- Learning which patterns agents need access to

---

### BLOCK Mode

**Behavior:** Raises `AuthorizationError` to block the operation entirely.

**Use Case:** Production environments, sensitive projects, or when strict enforcement is required.

**Configuration:**
```json
{
  "enforcement_mode": "block"
}
```

**Example Output:**
```
ERROR  Authorization blocked: Write not permitted: Denied: matches .git/**
[Operation is blocked, file not written]
```

**When to Use:**
- Production environments with strict security requirements
- Protecting critical infrastructure files
- Compliance requirements (e.g., SOC2, HIPAA)

---

## Permission Patterns

### Pattern Syntax

Permissions use glob patterns matched against file paths:

| Pattern | Matches | Example |
|---------|---------|---------|
| `*.py` | Any `.py` file in root | `main.py`, `app.py` |
| `src/**` | All files under `src/` | `src/auth/login.py` |
| `.git/**` | All files under `.git/` | `.git/config`, `.git/HEAD` |
| `**/*.env` | Any `.env` file anywhere | `.env`, `config/.env` |
| `production/**` | All files under `production/` | `production/deploy.py` |

### Pattern Evaluation Order

Patterns are evaluated **in order** from first to last:

1. First matching pattern wins
2. Put more specific patterns earlier
3. End with catch-all patterns if needed

**Example:**
```json
{
  "permissions": [
    {
      "pattern": "src/public/**",
      "allow_write": true,
      "reason": "Public source code"
    },
    {
      "pattern": "src/**",
      "allow_write": false,
      "reason": "All other source code blocked"
    }
  ]
}
```

In this example:
- `src/public/api.py` → ✅ Allowed (matches first pattern)
- `src/internal/auth.py` → ❌ Blocked (matches second pattern)

---

## Configuration Reference

### `.ralph/permissions.json`

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `enabled` | boolean | No | `false` | Enable authorization checking |
| `enforcement_mode` | string | No | `"warn"` | `"warn"` or `"block"` |
| `fallback_to_full_auto` | boolean | No | `false` | Allow bypass when `--full-auto` flag present |
| `permissions` | array | No | `[]` | List of permission rules |

### Permission Rule Object

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `pattern` | string | Yes | Glob pattern to match file paths |
| `allow_write` | boolean | No | `true` to allow, `false` to deny |
| `reason` | string | No | Human-readable explanation |

---

## Common Patterns

### Protect Git and Secrets

```json
{
  "permissions": [
    {"pattern": ".git/**", "allow_write": false, "reason": "Git internals"},
    {"pattern": "*.env", "allow_write": false, "reason": "Environment files"},
    {"pattern": "*.key", "allow_write": false, "reason": "Private keys"},
    {"pattern": "*.pem", "allow_write": false, "reason": "Certificates"},
    {"pattern": "secrets/**", "allow_write": false, "reason": "Secrets directory"}
  ]
}
```

### Allow Source, Block Infrastructure

```json
{
  "permissions": [
    {"pattern": "src/**", "allow_write": true, "reason": "Source code"},
    {"pattern": "tests/**", "allow_write": true, "reason": "Test files"},
    {"pattern": "docs/**", "allow_write": true, "reason": "Documentation"},
    {"pattern": "infrastructure/**", "allow_write": false, "reason": "Infrastructure code"},
    {"pattern": "deploy/**", "allow_write": false, "reason": "Deployment scripts"}
  ]
}
```

### Development vs Production

```json
{
  "permissions": [
    {"pattern": "dev/**", "allow_write": true, "reason": "Development environment"},
    {"pattern": "staging/**", "allow_write": true, "reason": "Staging environment"},
    {"pattern": "production/**", "allow_write": false, "reason": "Production - blocked"}
  ]
}
```

---

## Migration Path

### From WARN to BLOCK Mode

**Step 1:** Start with WARN mode to observe behavior without blocking:

```json
{"enforcement_mode": "warn"}
```

**Step 2:** Run iterations and review warnings:

```bash
ralph run --agent codex --max-iterations 10
```

**Step 3:** Update permissions to reduce false positives:

```json
{
  "permissions": [
    // Add patterns that were incorrectly blocked
    {"pattern": "needed/path/**", "allow_write": true, "reason": "Actually needed"}
  ]
}
```

**Step 4:** Switch to BLOCK mode once warnings are acceptable:

```json
{"enforcement_mode": "block"}
```

---

## Bypass Methods

### Method 1: Disable Authorization

```toml
[authorization]
enabled = false
```

### Method 2: Use WARN Mode

```toml
[authorization]
enforcement_mode = "warn"
```

### Method 3: Full-Auto Bypass

Enable fallback in config:

```toml
[authorization]
fallback_to_full_auto = true
```

Then run with `--full-auto` flag:

```bash
ralph run --agent codex --full-auto
```

**Warning:** This bypasses ALL authorization checks. Use only in trusted environments.

---

## Troubleshooting

### Authorization blocked my operation

**Problem:** `AuthorizationError: Write not permitted`

**Solutions:**
1. Check the denied pattern in your `.ralph/permissions.json`
2. Add a more specific allow pattern earlier in the list
3. Switch to WARN mode temporarily to understand what's being blocked
4. Use `--full-auto` bypass if `fallback_to_full_auto` is enabled

### Too many false positives

**Problem:** Legitimate operations are being blocked

**Solutions:**
1. Use WARN mode to collect all violations
2. Review logs to identify patterns you need to add
3. Add allow patterns **before** deny patterns (order matters)
4. Test permissions with a single iteration: `ralph step --agent codex`

### Authorization not working

**Problem:** Operations proceed even when they should be blocked

**Check:**
1. Verify `enabled = true` in both TOML and JSON
2. Confirm `permissions_file` path is correct
3. Check JSON syntax is valid (use `jq . .ralph/permissions.json`)
4. Verify patterns match the actual file paths being written

---

## Security Considerations

### WARN Mode Risks

- Unauthorized operations proceed with only a log warning
- Relies on developers to notice and act on warnings
- Not suitable for production environments with strict security requirements

### BLOCK Mode Risks

- May break existing workflows if permissions are misconfigured
- Requires careful permission design to avoid false positives
- May require bypass for legitimate operations

### Recommendations

1. **Start with WARN mode** to observe authorization behavior
2. **Review warning logs** to identify and fix permission rules
3. **Switch to BLOCK mode** once permissions are well-tuned
4. **Test in non-production** before enforcing in production
5. **Monitor logs** for blocked operations that indicate permission issues

---

## Technical Details

### What Gets Authorized

Currently, authorization is checked for:
- Anchor file writes (`.ralph/context/*/ANCHOR.md`)

Future enhancements may add authorization for:
- Other file writes by agents
- File reads (for sensitive files)
- Command execution

### Path Matching

Authorization uses `fnmatch` pattern matching:
- Case-sensitive on Unix, case-insensitive on Windows
- `**` matches zero or more directories
- `*` matches any sequence of characters (not `/`)
- `?` matches any single character

### Performance Impact

- Authorization checks add minimal overhead (<1ms per file write)
- Patterns are compiled and cached
- Early exit on first match

---

## Related Documentation

- **Security Policy:** `SECURITY.md` - Overall security posture and reporting
- **Path Validation:** `.spec/path-validation-security-posture.md` - Path traversal protection
- **Configuration:** `docs/CONFIGURATION.md` - Complete configuration reference
- **Authorization Spec:** `.spec/authorization-configurable-enforcement.md` - Implementation details

---

## FAQ

**Q: What happens if I don't specify `enforcement_mode`?**

A: Defaults to `"warn"` for backward compatibility and safety.

**Q: Can I change modes without restarting ralph?**

A: Yes, modes are read from config files on each operation. Changes take effect immediately.

**Q: Does block mode affect all file operations?**

A: Currently, authorization is checked only for anchor file writes. Future enhancements may add checks for other operations.

**Q: What if I need to bypass authorization temporarily?**

A: Use `--full-auto` flag if `fallback_to_full_auto` is enabled, or set `enabled = false` in config.

**Q: Can I have different enforcement modes for different patterns?**

A: Not currently. Enforcement mode is global for all authorization checks.

---

**Document Owner:** jscraik
**Next Review:** 2026-04-20
**Change Log:**
- 2026-01-20: Initial version (v1.0)
