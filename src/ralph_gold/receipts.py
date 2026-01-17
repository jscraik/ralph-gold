from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


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


def write_receipt(path: Path, receipt: CommandReceipt) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(receipt)
    payload["_schema"] = "ralph_gold.receipt.v1"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
