from __future__ import annotations

import hashlib
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .atomic_file import atomic_write_json


def iso_utc(ts: Optional[float] = None) -> str:
    import datetime as _dt

    dt = _dt.datetime.fromtimestamp(ts or time.time(), tz=_dt.timezone.utc)
    return dt.isoformat()


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def truncate_text(text: str, limit: int = 2000) -> str:
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    head = text[: max(0, limit // 4)]
    tail = text[-max(0, limit - len(head) - 64) :]
    omitted = len(text) - len(head) - len(tail)
    return f"{head}\n... [truncated {omitted} chars] ...\n{tail}"


@dataclass(frozen=True)
class CommandReceipt:
    name: str
    argv: List[str]
    returncode: int
    started_at: str
    ended_at: str
    duration_seconds: float

    stdout_path: Optional[str] = None
    stderr_path: Optional[str] = None
    notes: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NoFilesWrittenReceipt:
    """Receipt emitted when agent writes no files.

    This receipt is created when the agent completes execution but
    no user files were written to the project (excluding .ralph internal files).

    Attributes:
        task_id: The task ID that was being executed
        iteration: The iteration number when this occurred
        started_at: ISO timestamp when agent started
        ended_at: ISO timestamp when agent ended
        duration_seconds: How long the agent ran
        agent_return_code: The agent's exit code
        possible_causes: List of possible reasons for no files written
        remediation: Suggested remediation steps
    """
    task_id: str
    iteration: int
    started_at: str
    ended_at: str
    duration_seconds: float
    agent_return_code: int
    possible_causes: List[str] = field(default_factory=list)
    remediation: str = ""


def write_receipt(path: Path, receipt: CommandReceipt | NoFilesWrittenReceipt) -> None:
    """Write receipt to file atomically.

    Atomic writes prevent partial state files from being read and ensure
    that interrupted operations don't corrupt receipt data.

    Args:
        path: Target file path for the receipt
        receipt: Either a CommandReceipt or NoFilesWrittenReceipt to write
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(receipt)
    payload["_schema"] = "ralph_gold.receipt.v1"
    atomic_write_json(path, payload)
