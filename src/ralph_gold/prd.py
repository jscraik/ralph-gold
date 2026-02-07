from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set, Tuple

PrdKind = Literal["json", "md", "beads", "web_analysis", "yaml", "github_issues"]


TaskId = str


@dataclass
class SelectedTask:
    """A unified pointer to the next unit of work across tracker formats."""

    id: TaskId
    title: str
    kind: PrdKind
    acceptance: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    group: str = "default"


@dataclass
class MdTask:
    id: str
    title: str
    status: str  # open|in_progress|done|blocked
    line_index: int
    indent: int
    acceptance: List[str]
    depends_on: List[str] = field(default_factory=list)

    @property
    def done(self) -> bool:
        return self.status == "done"


@dataclass
class MdPrd:
    lines: List[str]
    tasks: List[MdTask]


_MD_TASKS_HEADING_RE = re.compile(r"^\s*##\s+tasks\b", re.IGNORECASE)
# Match same-level (##) headings when scanning for tasks end - don't stop at ### subheadings
_MD_SECTION_HEADING_RE = re.compile(r"^\s*##\s+\S")
_MD_HEADING_RE = re.compile(r"^\s*#{1,6}\s+\S")
_MD_FENCE_RE = re.compile(r"^\s*```")
_MD_CHECKBOX_RE = re.compile(r"^(\s*[-*]\s+\[)([^\]])(\]\s+)(.+?)\s*$")
_MD_BULLET_RE = re.compile(r"^\s*[-*]\s+(?:\[[ xX]\]\s+)?(.+?)\s*$")
_MD_BRANCH_RE = re.compile(r"^\s*(branch|branchname)\s*:\s*(.+?)\s*$", re.IGNORECASE)
_MD_DEPENDS_RE = re.compile(r"^\s*depends\s+on\s*:\s*(.+?)\s*$", re.IGNORECASE)


def _marker_to_status(marker: str) -> str:
    m = marker.strip().lower()
    if m == "x":
        return "done"
    if m in {"-", "!"}:
        return "blocked"
    if m == "~":
        return "in_progress"
    return "open"


def _status_to_marker(status: str) -> str:
    s = (status or "open").strip().lower()
    if s == "done":
        return "x"
    if s == "blocked":
        return "-"
    if s == "in_progress":
        return "~"
    return " "


def _parse_md_depends(acceptance: List[str]) -> List[str]:
    deps: List[str] = []
    for a in acceptance:
        m = _MD_DEPENDS_RE.match(a)
        if not m:
            continue
        tail = m.group(1)
        nums = re.findall(r"\d+", tail)
        for n in nums:
            if n not in deps:
                deps.append(n)
    return deps


def is_markdown_prd(path: Path) -> bool:
    return path.suffix.lower() in {".md", ".markdown"}


def _load_json_prd(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing PRD file: {path}")
    try:
        prd_data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.debug("Failed to load PRD: %s", e)
        return None
    return prd_data


def _save_json_prd(path: Path, prd: Dict[str, Any]) -> None:
    path.write_text(json.dumps(prd, indent=2) + "\n", encoding="utf-8")


def _story_done(story: Dict[str, Any]) -> bool:
    if "passes" in story:
        return bool(story.get("passes"))
    status = str(story.get("status", "open")).lower()
    return status == "done"


def _story_blocked(story: Dict[str, Any]) -> bool:
    if story.get("blocked") is True:
        return True
    status = str(story.get("status", "open")).lower()
    return status in {"blocked", "stuck"}


def _story_depends(story: Dict[str, Any]) -> List[str]:
    deps = story.get("depends_on")
    if isinstance(deps, list):
        return [str(x) for x in deps if x is not None]
    return []


def _deps_satisfied(deps: List[str], done_ids: Set[str]) -> bool:
    return all(d in done_ids for d in deps)


def _story_priority(story: Dict[str, Any]) -> int:
    try:
        return int(story.get("priority", 10_000))
    except (json.JSONDecodeError, OSError) as e:
        logger.debug("Failed to load JSON PRD: %s", e)
        return None


def _select_next_story(
    prd: Dict[str, Any],
    exclude_ids: Optional[Set[str]] = None,
) -> Optional[Dict[str, Any]]:
    stories = prd.get("stories", [])
    if not isinstance(stories, list):
        return None
    exclude = exclude_ids or set()

    done_ids: Set[str] = set()
    for s in stories:
        if not isinstance(s, dict):
            continue
        sid = s.get("id", s.get("story_id", s.get("key")))
        if sid is None:
            continue
        sid_str = str(sid)
        if _story_done(s) or _story_blocked(s):
            done_ids.add(sid_str)

    remaining: List[Dict[str, Any]] = []
    for s in stories:
        if not isinstance(s, dict):
            continue
        sid = s.get("id", s.get("story_id", s.get("key")))
        if sid is None:
            continue
        sid_str = str(sid)
        if sid_str in exclude:
            continue
        if _story_done(s) or _story_blocked(s):
            continue
        deps = _story_depends(s)
        if deps and not _deps_satisfied(deps, done_ids):
            continue
        remaining.append(s)

    if not remaining:
        return None
    remaining.sort(key=_story_priority)
    return remaining[0]


def _json_all_done(prd: Dict[str, Any]) -> bool:
    stories = prd.get("stories", [])
    if not isinstance(stories, list):
        return False  # Invalid structure is not "done"
    if not stories:
        return False  # Empty PRD is not "done"
    return all((not isinstance(s, dict)) or _story_done(s) for s in stories)


def _json_force_story_open(prd: Dict[str, Any], story_id: str) -> bool:
    """Force a JSON PRD story back to not-done.

    This is used as a post-iteration safety valve when quality gates fail.
    """

    stories = prd.get("stories", [])
    if not isinstance(stories, list):
        return False
    changed = False
    for s in stories:
        if not isinstance(s, dict):
            continue
        sid = s.get("id", s.get("story_id", s.get("key")))
        if sid is None:
            continue
        if str(sid) != str(story_id):
            continue

        if "passes" in s and s.get("passes") is True:
            s["passes"] = False
            changed = True
        if "status" in s and str(s.get("status", "open")).lower() == "done":
            s["status"] = "open"
            changed = True
        if "completedAt" in s:
            s.pop("completedAt", None)
            changed = True
        return changed
    return False


def _parse_md_prd(text: str) -> MdPrd:
    lines = text.splitlines()

    # Try to parse tasks under an explicit "## Tasks" heading first.
    in_fence = False
    tasks_start: Optional[int] = None
    for i, line in enumerate(lines):
        if _MD_FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if _MD_TASKS_HEADING_RE.match(line):
            tasks_start = i + 1
            break

    tasks: List[MdTask] = []
    in_fence = False

    def _scan_range(start: int, end: int) -> None:
        nonlocal in_fence
        for li in range(start, end):
            line = lines[li]
            if _MD_FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            m = _MD_CHECKBOX_RE.match(line)
            if not m:
                continue
            status = _marker_to_status(m.group(2))
            title = m.group(4).strip()
            indent = len(line) - len(line.lstrip(" "))
            tasks.append(
                MdTask(
                    id=str(len(tasks) + 1),
                    title=title,
                    status=status,
                    line_index=li,
                    indent=indent,
                    acceptance=[],
                )
            )

    if tasks_start is not None:
        # End of tasks section is the next ## heading outside fences.
        # Don't stop at ### subheadings - they're allowed within tasks section.
        end = len(lines)
        for j in range(tasks_start, len(lines)):
            line = lines[j]
            if _MD_FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            if _MD_SECTION_HEADING_RE.match(line):
                end = j
                break
        in_fence = False
        _scan_range(tasks_start, end)
    else:
        # Fallback: any checkbox task line (outside fences).
        _scan_range(0, len(lines))

    # Populate acceptance criteria for each task by scanning the block until the next task.
    for idx, t in enumerate(tasks):
        start = t.line_index + 1
        end = tasks[idx + 1].line_index if idx + 1 < len(tasks) else len(lines)

        acc: List[str] = []
        in_fence = False
        for li in range(start, end):
            line = lines[li]
            if _MD_FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            # Stop at the next section heading.
            if _MD_HEADING_RE.match(line):
                break

            # Only consider indented bullets under the task line.
            if len(line) - len(line.lstrip(" ")) <= t.indent:
                continue
            m = _MD_BULLET_RE.match(line)
            if not m:
                continue
            item = m.group(1).strip()
            if item:
                acc.append(item)
        t.acceptance = acc
        t.depends_on = _parse_md_depends(acc)

    return MdPrd(lines=lines, tasks=tasks)


def _load_md_prd(path: Path) -> MdPrd:
    if not path.exists():
        raise FileNotFoundError(f"Missing PRD file: {path}")
    return _parse_md_prd(path.read_text(encoding="utf-8"))


def _save_md_prd(path: Path, prd: MdPrd) -> None:
    # Preserve a trailing newline.
    text = "\n".join(prd.lines)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def _md_all_done(prd: MdPrd) -> bool:
    if not prd.tasks:
        return False  # Empty PRD is not "done"
    return all(t.status == "done" for t in prd.tasks)


def _md_force_task_open(prd: MdPrd, task_id: str) -> bool:
    for t in prd.tasks:
        if t.id != task_id:
            continue
        if t.status != "done":
            return False
        line = prd.lines[t.line_index]
        prd.lines[t.line_index] = re.sub(r"\[[^\]]\]", "[ ]", line, count=1)
        t.status = "open"
        return True
    return False


def select_next_task(
    prd_path: Path, exclude_ids: Optional[Set[str]] = None
) -> Optional[SelectedTask]:
    """Return the next unfinished task in the configured PRD file."""

    if is_markdown_prd(prd_path):
        prd = _load_md_prd(prd_path)
        exclude = exclude_ids or set()
        done_ids: Set[str] = set()
        for t in prd.tasks:
            if t.status in {"done", "blocked"}:
                done_ids.add(t.id)
        for t in prd.tasks:
            if t.id in exclude:
                continue
            if t.status != "open":
                continue
            if t.depends_on and not _deps_satisfied(t.depends_on, done_ids):
                continue
            return SelectedTask(
                id=str(t.id),
                title=t.title,
                kind="md",
                acceptance=list(t.acceptance),
                depends_on=list(t.depends_on),
            )
        return None

    prd = _load_json_prd(prd_path)
    if prd is None:
        return None
    story = _select_next_story(prd, exclude_ids=exclude_ids)
    if not story:
        return None
    sid = story.get("id", story.get("story_id", story.get("key")))
    if sid is None:
        return None
    sid_str = str(sid)
    title = str(story.get("title", "")).strip() or f"Story {sid_str}"
    acc = story.get("acceptance", [])
    if not isinstance(acc, list):
        acc = []
    acceptance = [str(x).strip() for x in acc if str(x).strip()]
    depends = _story_depends(story)
    return SelectedTask(
        id=sid_str,
        title=title,
        kind="json",
        acceptance=acceptance,
        depends_on=depends,
    )


def task_counts(prd_path: Path) -> Tuple[int, int]:
    """Return (done, total)."""

    if is_markdown_prd(prd_path):
        prd = _load_md_prd(prd_path)
        total = len(prd.tasks)
        done = sum(1 for t in prd.tasks if t.status == "done")
        return done, total

    prd = _load_json_prd(prd_path)
    if prd is None:
        return 0, 0
    stories = prd.get("stories", [])
    if not isinstance(stories, list):
        return 0, 0
    total = sum(1 for s in stories if isinstance(s, dict))
    done = sum(1 for s in stories if isinstance(s, dict) and _story_done(s))
    return done, total


def status_counts(prd_path: Path) -> Tuple[int, int, int, int]:
    """Return (done, blocked, open, total) detailed status counts.

    Provides separate counts for done, blocked, and open tasks.
    Blocked tasks are NOT counted as done - they are tracked separately.

    Returns:
        A tuple of (done_count, blocked_count, open_count, total_count)
    """
    if is_markdown_prd(prd_path):
        prd = _load_md_prd(prd_path)
        total = len(prd.tasks)
        done = sum(1 for t in prd.tasks if t.status == "done")
        blocked = sum(1 for t in prd.tasks if t.status == "blocked")
        open_count = sum(1 for t in prd.tasks if t.status == "open")
        return done, blocked, open_count, total

    prd = _load_json_prd(prd_path)
    if prd is None:
        return 0, 0, 0, 0
    stories = prd.get("stories", [])
    if not isinstance(stories, list):
        return 0, 0, 0, 0
    total = sum(1 for s in stories if isinstance(s, dict))
    done = sum(1 for s in stories if isinstance(s, dict) and _story_done(s))
    blocked = sum(1 for s in stories if isinstance(s, dict) and _story_blocked(s))
    # Open = total - done - blocked
    open_count = total - done - blocked
    return done, blocked, open_count, total


def all_done(prd_path: Path) -> bool:
    if is_markdown_prd(prd_path):
        return _md_all_done(_load_md_prd(prd_path))
    prd = _load_json_prd(prd_path)
    if prd is None:
        return False
    return _json_all_done(prd)


def all_blocked(prd_path: Path) -> bool:
    """Check if all remaining tasks are marked as blocked.

    Returns:
        True if all remaining tasks have status "blocked", False otherwise.
        Returns False if there are no remaining tasks (all done).
    """
    if is_markdown_prd(prd_path):
        return _md_all_blocked(_load_md_prd(prd_path))
    prd = _load_json_prd(prd_path)
    if prd is None:
        return False
    return _json_all_blocked(prd)


def _md_all_blocked(prd: MdPrd) -> bool:
    """Check if all remaining MD tasks are blocked.

    Returns:
        True if all remaining tasks have status "blocked", False otherwise.
        Returns False if there are no remaining tasks (all done).
    """
    remaining = [t for t in prd.tasks if t.status != "done"]
    if not remaining:
        return False  # All done, not blocked
    return all(t.status == "blocked" for t in remaining)


def _json_all_blocked(prd: Dict[str, Any]) -> bool:
    """Check if all remaining JSON stories are blocked.

    Returns:
        True if all remaining stories have status "blocked", False otherwise.
        Returns False if there are no remaining stories (all done).
    """
    stories = prd.get("stories", [])
    if not isinstance(stories, list):
        return False
    remaining = [s for s in stories if isinstance(s, dict) and not _story_done(s)]
    if not remaining:
        return False  # All done, not blocked
    return all(s.get("status") == "blocked" for s in remaining if isinstance(s, dict))


def force_task_open(prd_path: Path, task_id: TaskId) -> bool:
    """Force a task/story back to unfinished (used when gates fail)."""

    if is_markdown_prd(prd_path):
        prd = _load_md_prd(prd_path)
        changed = _md_force_task_open(prd, str(task_id))
        if changed:
            _save_md_prd(prd_path, prd)
        return changed

    prd = _load_json_prd(prd_path)
    if prd is None:
        return False
    changed = _json_force_story_open(prd, str(task_id))
    if changed:
        _save_json_prd(prd_path, prd)
    return changed


def is_task_done(prd_path: Path, task_id: TaskId) -> bool:
    """Return True if a given task/story is currently marked done."""

    if is_markdown_prd(prd_path):
        prd = _load_md_prd(prd_path)
        for t in prd.tasks:
            if t.id == str(task_id):
                return bool(t.status == "done")
        return False

    prd = _load_json_prd(prd_path)
    if prd is None:
        return False
    stories = prd.get("stories", [])
    if not isinstance(stories, list):
        return False
    for s in stories:
        if not isinstance(s, dict):
            continue
        sid = s.get("id", s.get("story_id", s.get("key")))
        if sid is None:
            continue
        if str(sid) != str(task_id):
            continue
        return _story_done(s)
    return False


def block_task(prd_path: Path, task_id: TaskId, reason: str) -> bool:
    """Mark a task/story as blocked (best effort)."""

    if is_markdown_prd(prd_path):
        prd = _load_md_prd(prd_path)
        changed = False
        for t in prd.tasks:
            if t.id != str(task_id):
                continue
            if t.status == "blocked":
                return False
            line = prd.lines[t.line_index]
            prd.lines[t.line_index] = re.sub(r"\[[^\]]\]", "[-]", line, count=1)
            t.status = "blocked"
            changed = True
            break
        if changed:
            _save_md_prd(prd_path, prd)
        return changed

    prd = _load_json_prd(prd_path)
    if prd is None:
        return False
    stories = prd.get("stories", [])
    if not isinstance(stories, list):
        return False
    changed = False
    for s in stories:
        if not isinstance(s, dict):
            continue
        sid = s.get("id", s.get("story_id", s.get("key")))
        if sid is None or str(sid) != str(task_id):
            continue
        s["blocked"] = True
        if "status" in s:
            s["status"] = "blocked"
        if reason:
            s.setdefault("blocked_reason", reason)
        changed = True
        break
    if changed:
        _save_json_prd(prd_path, prd)
    return changed


def get_prd_branch_name(prd_path: Path) -> Optional[str]:
    """Extract a branch name from PRD metadata.

    Supported:
    - JSON PRD root keys: branchName / branch / gitBranch / branch_name
    - Markdown PRD header lines: `Branch: ...` or `branchName: ...`
    """

    try:
        if is_markdown_prd(prd_path):
            if not prd_path.exists():
                return None
            # Only scan the header portion to avoid false positives in task titles.
            lines = prd_path.read_text(encoding="utf-8").splitlines()
            for line in lines[:60]:
                m = _MD_BRANCH_RE.match(line)
                if not m:
                    continue
                val = m.group(2).strip()
                return val or None
            return None

        prd = _load_json_prd(prd_path)
        if prd is None:
            return None
        for k in [
            "branchName",
            "branch",
            "gitBranch",
            "branch_name",
            "branchNameOverride",
        ]:
            v = prd.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None
    except (json.JSONDecodeError, OSError) as e:
        logger.debug("Failed to load PRD: %s", e)
        return None


def get_all_tasks(prd_path: Path) -> List[Dict[str, Any]]:
    """Get all tasks from PRD file for dependency graph building.

    Returns:
        List of task dictionaries with 'id', 'title', 'status', and 'depends_on' fields
    """
    tasks: List[Dict[str, Any]] = []

    try:
        if is_markdown_prd(prd_path):
            prd = _load_md_prd(prd_path)
            for t in prd.tasks:
                tasks.append(
                    {
                        "id": t.id,
                        "title": t.title,
                        "status": t.status,
                        "depends_on": list(t.depends_on),
                    }
                )
        else:
            prd = _load_json_prd(prd_path)
            if prd is None:
                return tasks
            stories = prd.get("stories", [])
            if isinstance(stories, list):
                for s in stories:
                    if not isinstance(s, dict):
                        continue
                    sid = s.get("id", s.get("story_id", s.get("key")))
                    if sid is None:
                        continue
                    title = str(s.get("title", "")).strip() or f"Story {sid}"
                    status = (
                        "done"
                        if _story_done(s)
                        else ("blocked" if _story_blocked(s) else "open")
                    )
                    depends = _story_depends(s)
                    tasks.append(
                        {
                            "id": str(sid),
                            "title": title,
                            "status": status,
                            "depends_on": depends,
                        }
                    )
    except (json.JSONDecodeError, OSError) as e:
        logger.debug("Failed to load JSON PRD: %s", e)
        return None
    return tasks
