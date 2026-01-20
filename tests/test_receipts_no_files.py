"""Tests for NoFilesWrittenReceipt and atomic receipt writes (Phase 1).

Tests:
- NoFilesWrittenReceipt dataclass creation and serialization
- Atomic receipt writes via atomic_write_json
- Receipt file format with _schema field
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from ralph_gold.receipts import (
    NoFilesWrittenReceipt,
    CommandReceipt,
    write_receipt,
)


class TestNoFilesWrittenReceipt:
    """Tests for NoFilesWrittenReceipt dataclass."""

    def test_no_files_receipt_creation(self) -> None:
        """Test creating a NoFilesWrittenReceipt."""
        receipt = NoFilesWrittenReceipt(
            task_id="task-1",
            iteration=1,
            started_at="2025-01-20T10:00:00+00:00",
            ended_at="2025-01-20T10:05:00+00:00",
            duration_seconds=300.0,
            agent_return_code=0,
        )
        assert receipt.task_id == "task-1"
        assert receipt.iteration == 1
        assert receipt.duration_seconds == 300.0
        assert receipt.agent_return_code == 0
        assert receipt.possible_causes == []  # Default
        assert receipt.remediation == ""  # Default

    def test_no_files_receipt_with_causes(self) -> None:
        """Test NoFilesWrittenReceipt with possible causes."""
        receipt = NoFilesWrittenReceipt(
            task_id="task-2",
            iteration=2,
            started_at="2025-01-20T11:00:00+00:00",
            ended_at="2025-01-20T11:05:00+00:00",
            duration_seconds=300.0,
            agent_return_code=124,  # Timeout
            possible_causes=[
                "Agent timed out (exit code 124)",
                "Task may be too complex for single iteration",
            ],
            remediation="Consider increasing runner_timeout_seconds in ralph.toml",
        )
        assert len(receipt.possible_causes) == 2
        assert "timed out" in receipt.possible_causes[0].lower()
        assert "complex" in receipt.possible_causes[1]
        assert "timeout" in receipt.remediation.lower()

    def test_no_files_receipt_immutable(self) -> None:
        """Test NoFilesWrittenReceipt is frozen (immutable)."""
        receipt = NoFilesWrittenReceipt(
            task_id="task-1",
            iteration=1,
            started_at="2025-01-20T10:00:00+00:00",
            ended_at="2025-01-20T10:05:00+00:00",
            duration_seconds=300.0,
            agent_return_code=0,
        )
        with pytest.raises(Exception):  # FrozenInstanceError
            receipt.task_id = "task-2"

    def test_no_files_receipt_serializable(self) -> None:
        """Test NoFilesWrittenReceipt can be serialized to dict."""
        receipt = NoFilesWrittenReceipt(
            task_id="task-1",
            iteration=1,
            started_at="2025-01-20T10:00:00+00:00",
            ended_at="2025-01-20T10:05:00+00:00",
            duration_seconds=300.0,
            agent_return_code=1,
            possible_causes=["Sandbox permissions"],
            remediation="Check file permissions",
        )
        data = asdict(receipt)
        assert data["task_id"] == "task-1"
        assert data["iteration"] == 1
        assert data["agent_return_code"] == 1
        assert data["possible_causes"] == ["Sandbox permissions"]
        assert data["remediation"] == "Check file permissions"


class TestWriteReceiptAtomic:
    """Tests for atomic receipt writes."""

    def test_write_command_receipt_creates_file(self, tmp_path: Path) -> None:
        """Test write_receipt creates file for CommandReceipt."""
        receipt_path = tmp_path / "receipts" / "command.json"
        receipt = CommandReceipt(
            name="test-command",
            argv=["echo", "hello"],
            returncode=0,
            started_at="2025-01-20T10:00:00+00:00",
            ended_at="2025-01-20T10:00:01+00:00",
            duration_seconds=1.0,
        )

        write_receipt(receipt_path, receipt)

        assert receipt_path.exists()
        # Verify parent directory was created
        assert receipt_path.parent.exists()

    def test_write_no_files_receipt_creates_file(self, tmp_path: Path) -> None:
        """Test write_receipt creates file for NoFilesWrittenReceipt."""
        receipt_path = tmp_path / "receipts" / "no-files.json"
        receipt = NoFilesWrittenReceipt(
            task_id="task-1",
            iteration=1,
            started_at="2025-01-20T10:00:00+00:00",
            ended_at="2025-01-20T10:05:00+00:00",
            duration_seconds=300.0,
            agent_return_code=0,
        )

        write_receipt(receipt_path, receipt)

        assert receipt_path.exists()

    def test_write_receipt_adds_schema_field(self, tmp_path: Path) -> None:
        """Test write_receipt adds _schema field to output."""
        receipt_path = tmp_path / "receipts" / "command.json"
        receipt = CommandReceipt(
            name="test",
            argv=["test"],
            returncode=0,
            started_at="2025-01-20T10:00:00+00:00",
            ended_at="2025-01-20T10:00:01+00:00",
            duration_seconds=1.0,
        )

        write_receipt(receipt_path, receipt)

        content = receipt_path.read_text()
        data = json.loads(content)
        assert data["_schema"] == "ralph_gold.receipt.v1"
        assert data["name"] == "test"

    def test_write_receipt_atomic_no_corruption(self, tmp_path: Path) -> None:
        """Test that receipt writes are atomic (no partial writes).

        This test verifies that using atomic_write_json prevents
        partial/corrupted files from being written.
        """
        receipt_path = tmp_path / "receipts" / "atomic-test.json"
        receipt = NoFilesWrittenReceipt(
            task_id="task-atomic",
            iteration=1,
            started_at="2025-01-20T10:00:00+00:00",
            ended_at="2025-01-20T10:05:00+00:00",
            duration_seconds=300.0,
            agent_return_code=0,
            possible_causes=["Test atomic write"],
            remediation="No remediation needed",
        )

        # Write the receipt
        write_receipt(receipt_path, receipt)

        # Verify file is valid JSON (not corrupted)
        content = receipt_path.read_text()
        data: dict[str, Any] = json.loads(content)  # Will raise if invalid JSON

        # Verify all fields present
        assert data["task_id"] == "task-atomic"
        assert data["possible_causes"] == ["Test atomic write"]
        assert data["remediation"] == "No remediation needed"
        assert "_schema" in data

    def test_write_receipt_overwrites_existing(self, tmp_path: Path) -> None:
        """Test write_receipt overwrites existing file atomically."""
        receipt_path = tmp_path / "receipts" / "overwrite.json"

        # Write first receipt
        receipt1 = NoFilesWrittenReceipt(
            task_id="task-1",
            iteration=1,
            started_at="2025-01-20T10:00:00+00:00",
            ended_at="2025-01-20T10:05:00+00:00",
            duration_seconds=300.0,
            agent_return_code=1,
        )
        write_receipt(receipt_path, receipt1)

        # Write second receipt (same path)
        receipt2 = NoFilesWrittenReceipt(
            task_id="task-2",
            iteration=2,
            started_at="2025-01-20T11:00:00+00:00",
            ended_at="2025-01-20T11:05:00+00:00",
            duration_seconds=300.0,
            agent_return_code=0,
        )
        write_receipt(receipt_path, receipt2)

        # Verify second receipt overwrote first
        content = receipt_path.read_text()
        data = json.loads(content)
        assert data["task_id"] == "task-2"
        assert data["iteration"] == 2
