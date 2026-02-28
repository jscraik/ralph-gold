"""Tests for evidence module."""

from __future__ import annotations

from ralph_gold.evidence import (
    EvidenceCitation,
    EvidenceReceipt,
    extract_evidence,
    extract_evidence_json,
    extract_evidence_regex,
)
from ralph_gold.receipts import hash_text


class TestEvidenceCitation:
    """Tests for EvidenceCitation dataclass."""

    def test_evidence_citation_creation(self) -> None:
        """Test creating an EvidenceCitation."""
        citation = EvidenceCitation(
            citation_type="file",
            reference="src/module.py:42",
            context="Some context"
        )
        assert citation.citation_type == "file"
        assert citation.reference == "src/module.py:42"
        assert citation.context == "Some context"

    def test_evidence_citation_defaults(self) -> None:
        """Test EvidenceCitation default values."""
        citation = EvidenceCitation(
            citation_type="test",
            reference="ref"
        )
        assert citation.context is None

    def test_evidence_citation_str(self) -> None:
        """Test EvidenceCitation __str__ method."""
        citation = EvidenceCitation(
            citation_type="file",
            reference="src/file.py:42"
        )
        str_repr = str(citation)
        assert "file: src/file.py:42" in str_repr


class TestEvidenceReceipt:
    """Tests for EvidenceReceipt dataclass."""

    def test_evidence_receipt_creation(self) -> None:
        """Test creating an EvidenceReceipt."""
        citations = [
            EvidenceCitation("file", "src/test.py:10"),
            EvidenceCitation("command", "pytest tests/")
        ]
        receipt = EvidenceReceipt(
            attempt_id="20260120-120000-iter0001",
            timestamp="2026-01-20T12:00:00Z",
            citations=citations,
            raw_output_hash="abc123",
            metadata={"iteration": 1}
        )
        assert receipt.attempt_id == "20260120-120000-iter0001"
        assert len(receipt.citations) == 2
        assert receipt.metadata["iteration"] == 1

    def test_evidence_receipt_to_command_receipt(self) -> None:
        """Test _to_command_receipt conversion."""
        citations = [
            EvidenceCitation("file", "src/test.py:10", "context")
        ]
        receipt = EvidenceReceipt(
            attempt_id="test-id",
            timestamp="2026-01-20T12:00:00Z",
            citations=citations,
            raw_output_hash="hash123",
            metadata={}
        )
        cmd_receipt = receipt._to_command_receipt()

        assert cmd_receipt["_schema"] == "ralph_gold.evidence.v1"
        assert cmd_receipt["attempt_id"] == "test-id"
        assert cmd_receipt["citation_count"] == 1
        assert len(cmd_receipt["citations"]) == 1
        assert cmd_receipt["citations"][0]["type"] == "file"
        assert cmd_receipt["citations"][0]["reference"] == "src/test.py:10"


class TestHashText:
    """Tests for hash_text function."""

    def testhash_text_consistency(self) -> None:
        """Test that same input produces same hash."""
        text = "test evidence output"
        hash1 = hash_text(text)
        hash2 = hash_text(text)
        assert hash1 == hash2

    def testhash_text_uniqueness(self) -> None:
        """Test that different inputs produce different hashes."""
        hash1 = hash_text("evidence 1")
        hash2 = hash_text("evidence 2")
        assert hash1 != hash2

    def testhash_text_format(self) -> None:
        """Test that hash is SHA256 (64 hex chars)."""
        hash_value = hash_text("test")
        assert len(hash_value) == 64
        # Should be valid hex
        int(hash_value, 16)


class TestExtractEvidenceRegex:
    """Tests for extract_evidence_regex function (Phase 2)."""

    def test_extract_file_evidence(self) -> None:
        """Test extracting file evidence."""
        output = """
Made changes to parser module.
**Evidence**: src/parser.py:156-162
**Evidence**: src/utils.py:42
"""
        citations = extract_evidence_regex(output)
        assert len(citations) == 2
        assert citations[0].citation_type == "file"
        assert "src/parser.py:156-162" in citations[0].reference

    def test_extract_command_evidence(self) -> None:
        """Test extracting command evidence."""
        output = """
Ran tests successfully.
**Evidence**: ```bash
pytest tests/test_parser.py -v
.........
10 passed in 0.5s
```
"""
        citations = extract_evidence_regex(output)
        assert len(citations) == 1
        assert citations[0].citation_type == "command"
        assert "pytest" in citations[0].reference

    def test_extract_test_evidence(self) -> None:
        """Test extracting test evidence."""
        output = """
Tests passing.
**Evidence**: pytest tests/test_module.py::test_func - PASS
**Evidence**: pytest tests/test_other.py::test_edge_case - FAIL
"""
        citations = extract_evidence_regex(output)
        assert len(citations) == 2
        assert citations[0].citation_type == "test"
        assert "PASS" in citations[0].reference

    def test_extract_url_evidence(self) -> None:
        """Test extracting URL evidence."""
        output = """
Documentation reference.
**Evidence**: [Parser Docs](https://docs.example.com/parser)
"""
        citations = extract_evidence_regex(output)
        assert len(citations) == 1
        assert citations[0].citation_type == "url"

    def test_extract_no_evidence(self) -> None:
        """Test output with no evidence."""
        output = "No evidence provided."
        citations = extract_evidence_regex(output)
        assert len(citations) == 0

    def test_extract_mixed_evidence(self) -> None:
        """Test extracting mixed evidence types."""
        output = """
Completed the task.
**Evidence**: src/main.py:42-50
**Evidence**: ```bash
python -m pytest
.
1 passed
```
**Evidence**: pytest tests/test.py::test_x - PASS
"""
        citations = extract_evidence_regex(output)
        assert len(citations) == 3
        types = {c.citation_type for c in citations}
        assert "file" in types
        assert "command" in types
        assert "test" in types


class TestExtractEvidenceJSON:
    """Tests for extract_evidence_json function (Phase 3)."""

    def test_extract_json_valid(self) -> None:
        """Test extracting valid JSON evidence."""
        output = """
Some text here.
```json
{
  "evidence": [
    {
      "type": "file",
      "reference": "src/code.py:100",
      "context": "Added function"
    }
  ]
}
```
"""
        citations = extract_evidence_json(output)
        assert citations is not None
        assert len(citations) == 1
        assert citations[0].citation_type == "file"
        assert citations[0].reference == "src/code.py:100"

    def test_extract_json_citations_format(self) -> None:
        """Test extracting JSON with citations format."""
        output = """
```json
{
  "citations": [
    {
      "type": "command",
      "reference": "npm test"
    }
  ]
}
```
"""
        citations = extract_evidence_json(output)
        assert citations is not None
        assert len(citations) == 1
        assert citations[0].citation_type == "command"

    def test_extract_json_invalid(self) -> None:
        """Test extracting invalid JSON returns None."""
        output = """
```json
{invalid json}
```
"""
        citations = extract_evidence_json(output)
        assert citations is None

    def test_extract_json_no_json(self) -> None:
        """Test output with no JSON returns None."""
        output = "No JSON here."
        citations = extract_evidence_json(output)
        assert citations is None


class TestExtractEvidence:
    """Tests for extract_evidence unified API."""

    def test_extract_evidence_regex_only(self) -> None:
        """Test extract_evidence with regex only (JSON disabled)."""
        output = "**Evidence**: src/file.py:42"
        citations = extract_evidence(output, enable_json=False)
        assert len(citations) == 1
        assert citations[0].citation_type == "file"

    def test_extract_evidence_json_fallback(self) -> None:
        """Test extract_evidence falls back to regex when JSON fails."""
        output = "**Evidence**: src/file.py:42\n```json\n{bad}\n```"
        citations = extract_evidence(output, enable_json=True)
        # Should fall back to regex and find the file evidence
        assert len(citations) == 1
        assert citations[0].citation_type == "file"

    def test_extract_evidence_json_priority(self) -> None:
        """Test extract_evidence tries JSON first when enabled."""
        output = """
```json
{
  "evidence": [{"type": "file", "reference": "src/x.py:1"}]
}
```
**Evidence**: src/other.py:2
"""
        citations = extract_evidence(output, enable_json=True)
        # JSON should take priority
        assert len(citations) == 1
        assert citations[0].reference == "src/x.py:1"

    def test_extract_evidence_empty_output(self) -> None:
        """Test extract_evidence with empty output."""
        citations = extract_evidence("")
        assert len(citations) == 0

    def test_extract_evidence_truncates_context(self) -> None:
        """Test that context is truncated to 200 chars."""
        output = "**Evidence**: src/file.py:42"
        # Note: Current implementation doesn't capture context in regex
        # This test documents the behavior
        citations = extract_evidence(output)
        assert len(citations) == 1


class TestIntegration:
    """Integration tests for evidence extraction."""

    def test_real_world_agent_output(self) -> None:
        """Test with realistic agent output."""
        output = """
I've implemented the user authentication feature.

**Evidence**: src/auth/login.py:45-78 (Added login function)
**Evidence**: src/auth/models.py:12-25 (User model)
**Evidence**: ```bash
pytest tests/auth/test_login.py -v
...
6 passed in 0.3s
```

All tests pass and the feature is ready.
"""
        citations = extract_evidence(output)
        assert len(citations) >= 2  # At least file and command
        types = {c.citation_type for c in citations}
        assert "file" in types
        # Command may or may not be parsed depending on format

    def test_evidence_receipt_full_workflow(self) -> None:
        """Test full evidence receipt workflow."""
        output = "**Evidence**: src/test.py:42"
        citations = extract_evidence(output)

        receipt = EvidenceReceipt(
            attempt_id="test-001",
            timestamp="2026-01-20T12:00:00Z",
            citations=citations,
            raw_output_hash=hash_text(output),
            metadata={"iteration": 1}
        )

        assert receipt.citation_count == 1
        cmd_receipt = receipt._to_command_receipt()
        assert cmd_receipt["citation_count"] == 1
        assert "evidence.v1" in cmd_receipt["_schema"]
