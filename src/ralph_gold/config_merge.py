"""Config merging for ralph init --force to preserve user settings.

Provides text-based merge logic to preserve custom configurations when
re-initializing a project, without requiring full TOML parsing/serialization.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MergeConfig:
    """Configuration for config merge behavior.

    Attributes:
        strategy: Merge strategy - "user_wins", "template_wins", or "ask"
        preserve_sections: Sections never overwritten (user values always kept)
        merge_sections: Sections to merge (user values override template)
    """

    strategy: str = "user_wins"
    preserve_sections: list[str] = field(default_factory=lambda: [
        "runners.custom",
        "tracker.github",
        "authorization",  # User's authorization settings
    ])
    merge_sections: list[str] = field(default_factory=lambda: [
        "loop",
        "gates",
        "files",
        "prompt",
        "state",
        "output_control",
    ])


def _extract_section_lines(
    lines: list[str], section_name: str
) -> tuple[int, int, list[str]]:
    """Extract a section's lines from TOML config.

    Args:
        lines: All lines from the TOML file
        section_name: Name of the section to extract (e.g., "loop")

    Returns:
        Tuple of (start_index, end_index, section_lines)
        Returns (-1, -1, []) if section not found
    """
    # Find section start
    section_pattern = re.compile(rf"^\[{re.escape(section_name)}\]")
    start_idx = -1
    for i, line in enumerate(lines):
        if section_pattern.match(line):
            start_idx = i
            break

    if start_idx == -1:
        return -1, -1, []

    # Find section end (next section at same level or end of file)
    # A section at the same level starts with '[' at the beginning of a line
    end_idx = start_idx + 1
    for i in range(start_idx + 1, len(lines)):
        line = lines[i]
        if line.startswith("[") and not line.startswith("[["):
            end_idx = i
            break
        if i == len(lines) - 1:
            end_idx = len(lines)

    return start_idx, end_idx, lines[start_idx:end_idx]


def _extract_nested_section(
    lines: list[str], parent_section: str, nested_key: str
) -> str | None:
    """Extract a nested section value (e.g., runners.custom) from TOML.

    Supports both formats:
    - Inline table: [runners] custom = { cmd = "..." }
    - Dotted section: [runners.custom]

    Args:
        lines: All lines from the TOML file
        parent_section: Parent section name (e.g., "runners")
        nested_key: Nested key name (e.g., "custom")

    Returns:
        The nested section content as a string, or None if not found
    """
    # First try dotted section format [parent_section.nested_key]
    dotted_section_name = f"{parent_section}.{nested_key}"
    dotted_start, dotted_end, dotted_lines = _extract_section_lines(lines, dotted_section_name)
    if dotted_start != -1:
        # Found dotted section format - return the section header and content
        return "\n".join(dotted_lines)

    # Fallback: try inline table format within parent section
    parent_start, parent_end, parent_lines = _extract_section_lines(lines, parent_section)
    if parent_start == -1:
        return None

    # Look for the nested key within the parent section
    nested_pattern = re.compile(rf"^{re.escape(nested_key)}\s*=")
    nested_lines = []
    found = False

    for line in parent_lines:
        if nested_pattern.match(line):
            found = True
        if found:
            nested_lines.append(line)
            # Check if this is a multiline table (indented)
            if line.strip().endswith("{") and "{" not in line[line.index("{") + 1:]:
                # Multiline table - collect until closing brace
                brace_count = line.count("{") - line.count("}")
                i = parent_lines.index(line) + 1
                while i < len(parent_lines) and brace_count > 0:
                    nested_lines.append(parent_lines[i])
                    brace_count += parent_lines[i].count("{") - parent_lines[i].count("}")
                    i += 1
            break

    if not found:
        return None

    return "\n".join(nested_lines)


def merge_configs_text(
    user_config_text: str,
    template_config_text: str,
    merge_cfg: MergeConfig | None = None,
) -> str:
    """Merge user config with new template using text-based approach.

    This approach preserves specific sections from the user config while
    updating everything else from the template.

    Args:
        user_config_text: User's current ralph.toml as text
        template_config_text: New template ralph.toml as text
        merge_cfg: Merge configuration (optional, uses defaults)

    Returns:
        Merged configuration as text
    """
    if merge_cfg is None:
        merge_cfg = MergeConfig()

    user_lines = user_config_text.splitlines()
    template_lines = template_config_text.splitlines()

    # Extract preserved sections from user config
    preserved_sections: dict[str, str] = {}
    for section_path in merge_cfg.preserve_sections:
        parts = section_path.split(".")
        if len(parts) == 1:
            # Top-level section
            start, end, section_lines = _extract_section_lines(user_lines, parts[0])
            if start != -1:
                preserved_sections[section_path] = "\n".join(section_lines)
        elif len(parts) == 2:
            # Nested section (e.g., runners.custom)
            nested_content = _extract_nested_section(user_lines, parts[0], parts[1])
            if nested_content:
                preserved_sections[section_path] = nested_content

    # Extract merge_sections from user config (user values override template)
    merged_sections: dict[str, str] = {}
    for section_path in merge_cfg.merge_sections:
        parts = section_path.split(".")
        if len(parts) == 1:
            # Top-level section
            start, end, section_lines = _extract_section_lines(user_lines, parts[0])
            if start != -1:
                merged_sections[section_path] = "\n".join(section_lines)
        elif len(parts) == 2:
            # Nested section (e.g., runners.custom)
            nested_content = _extract_nested_section(user_lines, parts[0], parts[1])
            if nested_content:
                merged_sections[section_path] = nested_content

    # Start with template and replace/insert both preserved and merged sections
    result_lines = list(template_lines)

    # First, handle merge_sections (user values override template)
    for section_path, content in merged_sections.items():
        parts = section_path.split(".")
        if len(parts) == 1:
            # Replace top-level section
            section_name = parts[0]

            # Find section in template
            template_start, template_end, _ = _extract_section_lines(
                result_lines, section_name
            )

            if template_start != -1:
                # Replace existing section in template with user's version
                content_lines = content.splitlines()
                result_lines = (
                    result_lines[:template_start] + content_lines + result_lines[template_end:]
                )
            # If section not in template, skip it (don't add new sections for merge)
        elif len(parts) == 2:
            # Replace nested section (same logic as preserve_sections)
            parent_section = parts[0]
            nested_key = parts[1]

            # Check if it's a dotted section format
            dotted_section_name = section_path
            dotted_start, dotted_end, _ = _extract_section_lines(result_lines, dotted_section_name)

            if dotted_start != -1:
                # Replace dotted section
                content_lines = content.splitlines()
                result_lines = (
                    result_lines[:dotted_start] + content_lines + result_lines[dotted_end:]
                )
            else:
                # Try inline table format
                parent_start, parent_end, parent_lines = _extract_section_lines(
                    result_lines, parent_section
                )

                if parent_start != -1:
                    nested_pattern = re.compile(rf"^{re.escape(nested_key)}\s*=")
                    new_parent_lines = list(parent_lines)
                    replaced = False

                    for i, line in enumerate(new_parent_lines):
                        if nested_pattern.match(line):
                            content_lines = content.splitlines()
                            new_parent_lines = (
                                new_parent_lines[:i] + content_lines + new_parent_lines[i + 1:]
                            )
                            if line.strip().endswith("{") and "{" not in line[line.index("{") + 1:]:
                                j = i + 1
                                brace_count = line.count("{") - line.count("}")
                                while (
                                    j < len(new_parent_lines)
                                    and brace_count > 0
                                    and not new_parent_lines[j].startswith("[")
                                ):
                                    new_parent_lines.pop(j)
                                    brace_count += new_parent_lines[j].count("{") - new_parent_lines[j].count("}")
                            replaced = True
                            break

                    if replaced:
                        result_lines = (
                            result_lines[:parent_start]
                            + new_parent_lines
                            + result_lines[parent_end:]
                        )

    # Then, handle preserve_sections (user values always kept)
    for section_path, content in preserved_sections.items():
        parts = section_path.split(".")
        if len(parts) == 1:
            # Replace top-level section
            section_name = parts[0]

            # Find section in template
            template_start, template_end, _ = _extract_section_lines(
                result_lines, section_name
            )

            if template_start != -1:
                # Replace existing section in template
                content_lines = content.splitlines()
                # Keep the same indentation
                result_lines = (
                    result_lines[:template_start] + content_lines + result_lines[template_end:]
                )
            else:
                # Section not in template - append it
                result_lines.append("")
                result_lines.append(content.splitlines()[0])  # Add section header
                if len(content.splitlines()) > 1:
                    result_lines.extend(content.splitlines()[1:])
        elif len(parts) == 2:
            # Replace nested section
            parent_section = parts[0]
            nested_key = parts[1]

            parent_start, parent_end, parent_lines = _extract_section_lines(
                result_lines, parent_section
            )

            if parent_start != -1:
                # Find and replace the nested key within parent section
                nested_pattern = re.compile(rf"^{re.escape(nested_key)}\s*=")
                new_parent_lines = list(parent_lines)
                replaced = False

                for i, line in enumerate(new_parent_lines):
                    if nested_pattern.match(line):
                        # Found the line to replace
                        content_lines = content.splitlines()
                        # Replace the nested key content
                        new_parent_lines = (
                            new_parent_lines[:i] + content_lines + new_parent_lines[i + 1:]
                        )
                        # Remove any old content for this key (multiline handling)
                        if line.strip().endswith("{") and "{" not in line[line.index("{") + 1:]:
                            # Remove old multiline content
                            j = i + 1
                            brace_count = line.count("{") - line.count("}")
                            while (
                                j < len(new_parent_lines)
                                and brace_count > 0
                                and not new_parent_lines[j].startswith("[")
                            ):
                                new_parent_lines.pop(j)
                                brace_count += new_parent_lines[j].count("{") - new_parent_lines[j].count("}")
                        replaced = True
                        break

                if replaced:
                    # Replace parent section in result
                    result_lines = (
                        result_lines[:parent_start]
                        + new_parent_lines
                        + result_lines[parent_end:]
                    )
                else:
                    # Nested key not in template parent section
                    # Check if it's dotted section format [parent.nested] or inline table
                    content_lines = content.splitlines()
                    if content_lines and content_lines[0].startswith(f"[{section_path}]"):
                        # Dotted section format - append as new section
                        # Find position after parent section ends
                        result_lines = (
                            result_lines[:parent_end] + [""] + content_lines + result_lines[parent_end:]
                        )
                    else:
                        # Inline table format - insert before parent section ends
                        insert_pos = parent_end - 1
                        result_lines = (
                            result_lines[:insert_pos] + content_lines + result_lines[insert_pos:]
                        )
            else:
                # Parent section doesn't exist in template
                # Check if user content is dotted section format
                content_lines = content.splitlines()
                if content_lines and content_lines[0].startswith(f"[{section_path}]"):
                    # Dotted section format - append to end of file
                    result_lines.extend([""] + content_lines)
                else:
                    # Inline table format - need to create parent section first
                    # This is more complex, so skip for now (inline tables require parent section)
                    pass

    return "\n".join(result_lines)


def merge_existing_config(
    project_root: Path,
    template_path: Path,
    cfg: MergeConfig | None = None,
) -> str:
    """Merge existing project config with new template.

    Args:
        project_root: Path to project root directory
        template_path: Path to the new template file
        cfg: Merge configuration (optional)

    Returns:
        Merged configuration as text

    Raises:
        FileNotFoundError: If template_path doesn't exist
    """
    config_path = project_root / ".ralph" / "ralph.toml"

    # Load user's current config
    if config_path.exists():
        user_config_text = config_path.read_text(encoding="utf-8")
    else:
        user_config_text = ""

    # Load new template
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")
    template_config_text = template_path.read_text(encoding="utf-8")

    # Perform merge
    if user_config_text:
        merged = merge_configs_text(user_config_text, template_config_text, cfg)
        preserved_count = len(cfg.preserve_sections) if cfg else 0
        merged_count = len(cfg.merge_sections) if cfg else 0
        logger.info(f"Preserved {preserved_count} sections and merged {merged_count} sections from existing config")
    else:
        merged = template_config_text

    return merged
