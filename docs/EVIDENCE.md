---
last_validated: 2026-02-28
---

# Evidence System

**Version:** 1.0
**Last Updated:** 2026-01-20
**Review Cadence:** Quarterly
**Audience:** Users and contributors

---

## Overview

The evidence system captures and tracks citations from agent outputs, providing transparency into what sources agents reference during their work. This creates an audit trail of files, commands, tests, and URLs that agents use as evidence.

### Key Features

- **Automatic extraction** - Parses evidence from agent output using patterns
- **Multiple formats** - Supports file references, commands, tests, and URLs
- **Receipt storage** - Stores evidence receipts in `.ralph/receipts/`
- **JSON or regex** - Supports both structured JSON and pattern-based extraction

---

`★ Insight ─────────────────────────────────────`
**Evidence Architecture:**
1. **Non-blocking** - Evidence extraction never fails iterations; it's purely informational
2. **Minimal overhead** - Regex-based extraction is fast and lightweight
3. **Opt-in structured** - JSON evidence provides richer data but isn't required
`─────────────────────────────────────────────────`

---

## Evidence Types

### File References

Citations to source code files with line numbers.

**Format:** `**Evidence**: path/to/file.py:42`

**Examples:**
```
**Evidence**: src/auth/login.py:42
**Evidence**: src/models/user.py:100-105
**Evidence**: tests/test_auth.py:25
```

**Supported patterns:**
- `file.py:42` - Single line
- `file.py:42:47` - Line range (alternative format)
- `file.py:42-47` - Line range (preferred)

### Command Blocks

Bash/shell command executions with output.

**Format:** Triple-backtick code blocks with `bash` or `sh` language

**Example:**
````markdown
**Evidence**:
```bash
pytest tests/test_auth.py -v
======================== test session starts =========================
collected 3 items

tests/test_auth.py::test_login PASSED
tests/test_auth.py::test_logout PASSED
========================= 2 passed in 0.5s =========================
```
````

### Test Results

Pytest test execution results.

**Format:** `**Evidence**: pytest path/to/test.py::test_name - PASS|FAIL`

**Examples:**
```
**Evidence**: pytest tests/test_auth.py::test_login - PASS
**Evidence**: pytest tests/test_api.py::test_create_user - FAIL
```

### URL References

Web links to documentation, issues, or resources.

**Format:** `**Evidence**: [link text](url)`

**Examples:**
```
**Evidence**: [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/)
**Evidence**: [GitHub Issue #123](https://github.com/owner/repo/issues/123)
```

---

## Structured JSON Evidence

For richer evidence data, agents can output structured JSON:

**Format 1: Evidence array**
```json
```json
{
  "evidence": [
    {
      "type": "file",
      "reference": "src/auth/login.py:42",
      "context": "Implemented JWT token validation"
    },
    {
      "type": "test",
      "reference": "pytest tests/test_auth.py::test_login - PASS",
      "context": "Test verifies login functionality"
    }
  ]
}
```
```

**Format 2: Citations array**
```json
```json
{
  "citations": [
    {
      "type": "command",
      "reference": "pytest tests/ -v",
      "context": "All tests passing"
    },
    {
      "type": "url",
      "reference": "Documentation: https://example.com/docs"
    }
  ]
}
```
```

**JSON extraction behavior:**
- Requires `enable_json = true` in prompt configuration
- Falls back to regex extraction if JSON parsing fails
- Only looks for JSON in code blocks or at end of output

---

## Receipt Format

Evidence receipts are stored as JSON in `.ralph/receipts/evidence-<attempt_id>.json`:

```json
{
  "_schema": "ralph_gold.evidence.v1",
  "attempt_id": "20260120-123456-iter0001",
  "timestamp": "2026-01-20T12:34:56.789Z",
  "citation_count": 3,
  "citations": [
    {
      "type": "file",
      "reference": "src/auth/login.py:42",
      "context": "Implemented JWT token validation..."
    },
    {
      "type": "test",
      "reference": "pytest tests/test_auth.py::test_login - PASS",
      "context": null
    },
    {
      "type": "command",
      "reference": "pytest tests/ -v",
      "context": "======================== test session starts..."
    }
  ],
  "raw_output_hash": "a1b2c3d4e5f6...",
  "metadata": {
    "task_id": "1",
    "task_title": "Implement authentication"
  }
}
```

---

## Configuration

### Enable JSON Evidence

In `.ralph/ralph.toml`:

```toml
[prompt]
enable_limits = true
# JSON extraction is attempted when limits are enabled
```

**Note:** JSON extraction is automatically attempted when `prompt.enable_limits = true`.

### View Evidence Count

Evidence count is tracked in iteration state:

```bash
ralph status
```

Output includes:
```
Evidence citations: 5
```

---

## Usage in Agent Prompts

### For Prompt Authors

Encourage agents to cite evidence using the `**Evidence**:` prefix:

**Example prompt instruction:**
```markdown
When referencing files, tests, or commands, use this format:

**Evidence**: path/to/file.py:42
**Evidence**: pytest tests/test_example.py - PASS
**Evidence**: ```bash\n<command>\n```
```

### For Agent Users

Simply include evidence markers in your agent responses:

```markdown
I've implemented the authentication feature.

**Evidence**: src/auth/login.py:42-56
**Evidence**: tests/test_auth.py::test_login - PASS

The login function now validates JWT tokens correctly.
```

Ralph will automatically extract and store these citations.

---

## Viewing Evidence

### Check Receipts Directory

```bash
# List all evidence receipts
ls -la .ralph/receipts/evidence-*.json

# View the most recent receipt
cat .ralph/receipts/evidence-$(ls -t .ralph/receipts/evidence-*.json | head -1 | sed 's/.*evidence-//' | sed 's/\.json//')
```

### Parse with jq

```bash
# Get citation count
jq '.citation_count' .ralph/receipts/evidence-*.json

# List all citations
jq '.citations[] | "\(.type): \(.reference)"' .ralph/receipts/evidence-*.json

# Filter by type
jq '.citations[] | select(.type == "file")' .ralph/receipts/evidence-*.json
```

---

## Examples

### Example 1: File References

**Agent output:**
```markdown
I've fixed the authentication bug.

The issue was in the token validation logic:
**Evidence**: src/auth/login.py:42-45
**Evidence**: src/auth/jwt.py:100

The fix validates tokens before decoding.
```

**Extracted citations:**
- file: src/auth/login.py:42-45
- file: src/auth/jwt.py:100

### Example 2: Test Results

**Agent output:**
```markdown
All tests are passing:

**Evidence**: pytest tests/test_auth.py::test_login - PASS
**Evidence**: pytest tests/test_auth.py::test_logout - PASS
**Evidence**: pytest tests/test_api.py::test_create_user - PASS
```

**Extracted citations:**
- test: pytest tests/test_auth.py::test_login - PASS
- test: pytest tests/test_auth.py::test_logout - PASS
- test: pytest tests/test_api.py::test_create_user - PASS

### Example 3: Structured JSON

**Agent output:**
```markdown
Task complete. Evidence:

```json
{
  "evidence": [
    {"type": "file", "reference": "src/auth.py:42", "context": "Added JWT validation"},
    {"type": "test", "reference": "pytest tests/test_auth.py - PASS", "context": "All 3 tests passed"},
    {"type": "url", "reference": "JWT Spec: https://tools.ietf.org/html/rfc7519"}
  ]
}
```
```

**Extracted citations:**
- file: src/auth.py:42 (context: "Added JWT validation")
- test: pytest tests/test_auth.py - PASS (context: "All 3 tests passed")
- url: JWT Spec: https://tools.ietf.org/html/rfc7519

---

## Troubleshooting

### Evidence Not Being Extracted

**Problem:** Evidence markers not being recognized

**Solutions:**
1. Check format: Must be `**Evidence**:` (exact spelling, bold markdown)
2. No space allowed between `**Evidence**` and `:`
3. File references must match pattern: `file.py:line` or `file.py:line-range`

**Correct:**
```
**Evidence**: src/file.py:42
```

**Incorrect:**
```
**Evidence** : src/file.py:42  (space before colon)
**Evidence**: src/file.py (no line number)
Evidence: src/file.py:42 (not bold)
```

### JSON Evidence Not Working

**Problem:** JSON evidence not being extracted

**Check:**
1. `prompt.enable_limits = true` in config
2. JSON must be in ```json code block or at end of output
3. JSON must validate (check with `jq .`)

**Test JSON extraction:**
```bash
# Validate JSON structure
echo '{"evidence": [{"type": "file", "reference": "test.py:1"}]}' | jq .
```

---

## Technical Details

### Regex Patterns

**File reference pattern:**
```regex
\*\*Evidence\*\*:\s*([a-zA-Z0-9_/\.\-]+:\d+(?::\d+)?(?:-\d+)?)
```

Matches:
- `src/file.py:42`
- `src/file.py:42:47` (alternative range format)
- `src/file.py:42-47` (preferred range format)

**Command block pattern:**
```regex
\*\*Evidence\*\*:\s*```(?:bash|sh)\n(.*?)\n```
```

**Test result pattern:**
```regex
\*\*Evidence\*\*:\s*pytest\s+([a-zA-Z0-9_/\.\-:]+)\s+-\s+(PASS|FAIL)
```

**URL pattern:**
```regex
\*\*Evidence\*\*:\s*\[([^\]]+)\]\(([^)]+)\)
```

### Context Extraction

For file references, up to 200 characters of surrounding context is captured (100 chars before and after the match).

### Performance

- Regex extraction: <10ms per iteration
- JSON extraction: <5ms per iteration (when present)
- Storage: ~1-5KB per evidence receipt

---

## Future Enhancements

Potential future improvements:
1. More evidence types (e.g., git commits, issues, PRs)
2. Evidence linking (connect related citations)
3. Evidence validation (verify files/lines exist)
4. Evidence search across all receipts
5. Evidence aggregation per task/PRD

---

## Related Documentation

- **Configuration:** `docs/CONFIGURATION.md` - Prompt configuration for JSON extraction
- **Troubleshooting:** `docs/TROUBLESHOOTING.md` - Common issues and solutions
- **Receipts:** `src/ralph_gold/receipts.py` - Receipt storage implementation

---

**Document Owner:** maintainers
**Next Review:** 2026-04-20
**Change Log:**
- 2026-01-20: Initial version (v1.0)
