# Security Policy

Doc requirements:
- Audience: users and contributors
- Scope: vulnerability reporting and supported versions
- Owner: maintainers
- Review cadence: quarterly
- Last updated: 2026-01-15

## Supported versions

Only the latest release and the current `main` branch are supported for security fixes.

## Reporting a vulnerability

Please report security issues privately by email:

- jscraik@brainwav.io

Do not open a public issue for security-sensitive reports.

## Security Features

### Path Traversal Protection

Ralph-gold includes robust path traversal protection. All user-provided file paths from CLI arguments are validated using `validate_project_path()` in `src/ralph_gold/path_utils.py`.

**Protected Attack Vectors:**
- Path traversal via `../`
- Symlink attacks
- Absolute path bypass
- Config manipulation

**Technical Details:**
See `.spec/path-validation-security-posture.md` for a complete security audit and threat analysis.

**Compliance:**
- OWASP ASVS V5.3.1: Verified use of intended paths
- OWASP ASVS V5.3.2: Path traversal prevention

### Authorization System

Ralph-gold provides configurable authorization to control file write operations. See `docs/AUTHORIZATION.md` for complete documentation.

**Features:**
- Pattern-based permissions (allow/deny)
- WARN mode (soft enforcement) or BLOCK mode (hard enforcement)
- Opt-in design, disabled by default

## Non-security bugs

Use GitHub Issues for non-security bugs and feature requests.
