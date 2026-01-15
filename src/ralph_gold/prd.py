from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple


PrdKind = Literal["json", "md", "beads"]


TaskId = str


@dataclass
class SelectedTask:
    """A unified pointer to the next unit of work across tracker formats."""

    id: TaskId
    title: str
    kind: PrdKind
    acceptance: List[str]


@dataclass
class MdTask:
    id: int
    title: str
    done: bool
    line_index: int
    indent: int
    acceptance: List[str]


@dataclass
class MdPrd:
    lines: List[str]
    tasks: List[MdTask]


_MD_TASKS_HEADING_RE = re.compile(r"^\s*##\s+tasks\b", re.IGNORECASE)
_MD_HEADING_RE = re.compile(r"^\s*#{1,6}\s+\S")
_MD_FENCE_RE = re.compile(r"^\s*```")
_MD_CHECKBOX_RE = re.compile(r"^(\s*[-*]\s+\[)([ xX])(\]\s+)(.+?)\s*$")
_MD_BULLET_RE = re.compile(r"^\s*[-*]\s+(?:\[[ xX]\]\s+)?(.+?)\s*$")
_MD_BRANCH_RE = re.compile(r"^\s*(branch|branchname)\s*:\s*(.+?)\s*$", re.IGNORECASE)


def is_markdown_prd(path: Path) -> bool:
    return path.suffix.lower() in {".md", ".markdown"}


def _load_json_prd(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing PRD file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json_prd(path: Path, prd: Dict[str, Any]) -> None:
    path.write_text(json.dumps(prd, indent=2) + "\n", encoding="utf-8")


def _story_done(story: Dict[str, Any]) -> bool:
    if "passes" in story:
        return bool(story.get("passes"))
    status = str(story.get("status", "open")).lower()
    return status == "done"


def _story_priority(story: Dict[str, Any]) -> int:
    try:
        return int(story.get("priority", 10_000))
    except Exception:
        return 10_000


def _select_next_story(prd: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    stories = prd.get("stories", [])
    if not isinstance(stories, list):
        return None
    remaining = [s for s in stories if isinstance(s, dict) and not _story_done(s)]
    if not remaining:
        return None
    remaining.sort(key=_story_priority)
    return remaining[0]


def _json_all_done(prd: Dict[str, Any]) -> bool:
    stories = prd.get("stories", [])
    if not isinstance(stories, list):
        return True
    return all((not isinstance(s, dict)) or _story_done(s) for s in stories)


def _json_force_story_open(prd: Dict[str, Any], story_id: int) -> bool:
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
        try:
            sid = int(s.get("id"))
        except Exception:
            continue
        if sid != story_id:
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
            done = m.group(2).lower() == "x"
            title = m.group(4).strip()
            indent = len(line) - len(line.lstrip(" "))
            tasks.append(MdTask(id=len(tasks) + 1, title=title, done=done, line_index=li, indent=indent, acceptance=[]))

    if tasks_start is not None:
        # End of tasks section is the next markdown heading outside fences.
        end = len(lines)
        for j in range(tasks_start, len(lines)):
            line = lines[j]
            if _MD_FENCE_RE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            if _MD_HEADING_RE.match(line):
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
    return all(t.done for t in prd.tasks)


def _md_force_task_open(prd: MdPrd, task_id: int) -> bool:
    for t in prd.tasks:
        if t.id != task_id:
            continue
        if not t.done:
            return False
        line = prd.lines[t.line_index]
        # Replace first checkbox marker only.
        prd.lines[t.line_index] = re.sub(r"\[[ xX]\]", "[ ]", line, count=1)
        t.done = False
        return True
    return False


def select_next_task(prd_path: Path) -> Optional[SelectedTask]:
    """Return the next unfinished task in the configured PRD file."""

    if is_markdown_prd(prd_path):
        prd = _load_md_prd(prd_path)
        for t in prd.tasks:
            if not t.done:
                return SelectedTask(id=str(t.id), title=t.title, kind="md", acceptance=list(t.acceptance))
        return None

    prd = _load_json_prd(prd_path)
    story = _select_next_story(prd)
    if not story:
        return None
    try:
        sid = int(story.get("id"))
    except Exception:
        return None
    title = str(story.get("title", "")).strip() or f"Story {sid}"
    acc = story.get("acceptance", [])
    if not isinstance(acc, list):
        acc = []
    acceptance = [str(x).strip() for x in acc if str(x).strip()]
    return SelectedTask(id=str(sid), title=title, kind="json", acceptance=acceptance)


def task_counts(prd_path: Path) -> Tuple[int, int]:
    """Return (done, total)."""

    if is_markdown_prd(prd_path):
        prd = _load_md_prd(prd_path)
        total = len(prd.tasks)
        done = sum(1 for t in prd.tasks if t.done)
        return done, total

    prd = _load_json_prd(prd_path)
    stories = prd.get("stories", [])
    if not isinstance(stories, list):
        return 0, 0
    total = sum(1 for s in stories if isinstance(s, dict))
    done = sum(1 for s in stories if isinstance(s, dict) and _story_done(s))
    return done, total


def all_done(prd_path: Path) -> bool:
    if is_markdown_prd(prd_path):
        return _md_all_done(_load_md_prd(prd_path))
    return _json_all_done(_load_json_prd(prd_path))


def force_task_open(prd_path: Path, task_id: TaskId) -> bool:
    """Force a task/story back to unfinished (used when gates fail)."""

    try:
        tid_int = int(str(task_id))
    except Exception:
        return False

    if is_markdown_prd(prd_path):
        prd = _load_md_prd(prd_path)
        changed = _md_force_task_open(prd, tid_int)
        if changed:
            _save_md_prd(prd_path, prd)
        return changed

    prd = _load_json_prd(prd_path)
    changed = _json_force_story_open(prd, tid_int)
    if changed:
        _save_json_prd(prd_path, prd)
    return changed


def is_task_done(prd_path: Path, task_id: TaskId) -> bool:
    """Return True if a given task/story is currently marked done."""

    try:
        tid_int = int(str(task_id))
    except Exception:
        return False

    if is_markdown_prd(prd_path):
        prd = _load_md_prd(prd_path)
        for t in prd.tasks:
            if t.id == tid_int:
                return bool(t.done)
        return False

    prd = _load_json_prd(prd_path)
    stories = prd.get("stories", [])
    if not isinstance(stories, list):
        return False
    for s in stories:
        if not isinstance(s, dict):
            continue
        try:
            sid = int(s.get("id"))
        except Exception:
            continue
        if sid != tid_int:
            continue
        return _story_done(s)
    return False


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
        for k in ["branchName", "branch", "gitBranch", "branch_name", "branchNameOverride"]:
            v = prd.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None
    except Exception:
        return None
