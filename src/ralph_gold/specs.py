from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple


_ACCEPTANCE_HEADING_RE = re.compile(r"^\s*##\s+acceptance\s+criteria\b", re.IGNORECASE | re.MULTILINE)
_ANY_HEADING_RE = re.compile(r"^\s*#{1,6}\s+\S", re.MULTILINE)
_BULLET_RE = re.compile(r"^\s*[-*]\s+\S", re.MULTILINE)


@dataclass
class SpecsCheckResult:
    ok: bool
    errors: List[str]
    warnings: List[str]
    files: List[str]


def _extract_section(text: str, heading_match: re.Match[str]) -> str:
    """Return the section body after a heading, until the next heading."""

    start = heading_match.end()
    rest = text[start:]
    m_next = _ANY_HEADING_RE.search(rest)
    if not m_next:
        return rest
    return rest[: m_next.start()]


def check_specs(project_root: Path, specs_dir: str = "specs") -> SpecsCheckResult:
    """Basic lint/check for specs/*.md.

    This intentionally stays lightweight and deterministic.

    Rules (opinionated, but "gold"-useful):
    - specs directory must exist
    - each spec (except README.md) should contain a '## Acceptance Criteria' section
    - acceptance section should contain at least one bullet item

    Returns errors + warnings; ok=False iff any errors.
    """

    specs_path = project_root / specs_dir
    errors: List[str] = []
    warnings: List[str] = []

    if not specs_path.exists() or not specs_path.is_dir():
        errors.append(f"Missing specs directory: {specs_path}")
        return SpecsCheckResult(ok=False, errors=errors, warnings=warnings, files=[])

    md_files = sorted([p for p in specs_path.rglob("*.md") if p.is_file()])
    if not md_files:
        warnings.append(f"No markdown specs found under: {specs_path}")
        return SpecsCheckResult(ok=True, errors=errors, warnings=warnings, files=[])

    checked: List[str] = []

    for p in md_files:
        rel = str(p.relative_to(project_root))
        if p.name.lower() == "readme.md":
            checked.append(rel)
            continue

        checked.append(rel)
        try:
            text = p.read_text(encoding="utf-8")
        except Exception as e:
            errors.append(f"{rel}: failed to read ({e})")
            continue

        if len(text.strip()) < 50:
            warnings.append(f"{rel}: very short spec (<50 chars)")

        if not _ANY_HEADING_RE.search(text):
            warnings.append(f"{rel}: no markdown headings found")

        m_acc = _ACCEPTANCE_HEADING_RE.search(text)
        if not m_acc:
            errors.append(f"{rel}: missing '## Acceptance Criteria' section")
            continue

        body = _extract_section(text, m_acc)
        if not _BULLET_RE.search(body):
            warnings.append(f"{rel}: 'Acceptance Criteria' has no bullet items")

    ok = len(errors) == 0
    return SpecsCheckResult(ok=ok, errors=errors, warnings=warnings, files=checked)


def format_specs_check(result: SpecsCheckResult) -> str:
    lines: List[str] = []
    if result.files:
        lines.append(f"Checked {len(result.files)} file(s):")
        for f in result.files:
            lines.append(f"  - {f}")
    else:
        lines.append("Checked 0 spec files")

    if result.errors:
        lines.append("")
        lines.append("Errors:")
        for e in result.errors:
            lines.append(f"  - {e}")

    if result.warnings:
        lines.append("")
        lines.append("Warnings:")
        for w in result.warnings:
            lines.append(f"  - {w}")

    lines.append("")
    lines.append(f"OK: {str(result.ok).lower()}")
    return "\n".join(lines) + "\n"
