"""Evidence collection and parsing for Ralph Gold.

Extracts and validates evidence from agent outputs for transparency.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Regex patterns for evidence extraction (Phase 2)
# Note: Patterns match **Evidence**: markdown bold syntax
EVIDENCE_FILE_RE = re.compile(
    r'\*\*Evidence\*\*:\s*([a-zA-Z0-9_/\.\-]+:\d+(?::\d+)?(?:-\d+)?)',
    re.MULTILINE
)
EVIDENCE_COMMAND_RE = re.compile(
    r'\*\*Evidence\*\*:\s*```(?:bash|sh)\n(.*?)\n```',
    re.MULTILINE | re.DOTALL
)
EVIDENCE_TEST_RE = re.compile(
    r'\*\*Evidence\*\*:\s*pytest\s+([a-zA-Z0-9_/\.\-:]+)\s+-\s+(PASS|FAIL)',
    re.MULTILINE
)
EVIDENCE_URL_RE = re.compile(
    r'\*\*Evidence\*\*:\s*\[([^\]]+)\]\(([^)]+)\)',
    re.MULTILINE
)


@dataclass(frozen=True)
class EvidenceCitation:
    """A single evidence citation extracted from agent output.

    Args:
        citation_type: Type of evidence ("file", "command", "test", "url")
        reference: The evidence reference (e.g., "src/file.py:42" or command output)
        context: Optional surrounding text (max 200 chars)
    """
    citation_type: str  # "file", "command", "test", "url"
    reference: str
    context: Optional[str] = None

    def __str__(self) -> str:
        if self.context:
            return f"{self.citation_type}: {self.reference} ({self.context[:50]}...)"
        return f"{self.citation_type}: {self.reference}"


@dataclass
class EvidenceReceipt:
    """Aggregated evidence for an iteration.

    Args:
        attempt_id: Unique identifier for this attempt
        timestamp: ISO timestamp of evidence collection
        citations: List of evidence citations
        raw_output_hash: Hash of raw output for verification
        metadata: Additional metadata
    """
    attempt_id: str
    timestamp: str
    citations: List[EvidenceCitation]
    raw_output_hash: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def citation_count(self) -> int:
        """Return the number of citations in this receipt."""
        return len(self.citations)

    def _to_command_receipt(self) -> Dict[str, Any]:
        """Convert to CommandReceipt format for write_receipt() compatibility.

        The receipts.py module expects a specific dict format.
        """
        return {
            "_schema": "ralph_gold.evidence.v1",
            "attempt_id": self.attempt_id,
            "timestamp": self.timestamp,
            "citation_count": len(self.citations),
            "citations": [
                {
                    "type": c.citation_type,
                    "reference": c.reference,
                    "context": c.context,
                }
                for c in self.citations
            ],
            "raw_output_hash": self.raw_output_hash,
            "metadata": self.metadata,
        }


def extract_evidence_regex(output: str) -> List[EvidenceCitation]:
    """Phase 2: Extract evidence via regex patterns.

    Matches:
    - **Evidence**: src/file.py:42
    - **Evidence**: ```bash\n<command>\n<output>\n```
    - **Evidence**: pytest tests/test.py::test_name - PASS
    - **Evidence**: [text](url)

    Args:
        output: Raw agent output text

    Returns:
        List of EvidenceCitation objects (empty if none found)
    """
    citations: List[EvidenceCitation] = []

    # Extract file references (e.g., src/module.py:42-47)
    for match in EVIDENCE_FILE_RE.finditer(output):
        reference = match.group(1)
        # Get surrounding context (up to 200 chars)
        start = max(0, match.start() - 100)
        end = min(len(output), match.end() + 100)
        context = output[start:end].strip()
        citations.append(EvidenceCitation(
            citation_type="file",
            reference=reference,
            context=context[:200] if context else None
        ))

    # Extract command blocks
    for match in EVIDENCE_COMMAND_RE.finditer(output):
        command_output = match.group(1).strip()
        # Truncate to 200 chars
        truncated = command_output[:200]
        citations.append(EvidenceCitation(
            citation_type="command",
            reference=truncated,
            context=None
        ))

    # Extract test results
    for match in EVIDENCE_TEST_RE.finditer(output):
        test_path = match.group(1)
        result = match.group(2)
        citations.append(EvidenceCitation(
            citation_type="test",
            reference=f"{test_path} - {result}",
            context=None
        ))

    # Extract URL references
    for match in EVIDENCE_URL_RE.finditer(output):
        text = match.group(1)
        url = match.group(2)
        citations.append(EvidenceCitation(
            citation_type="url",
            reference=f"{text}: {url}",
            context=None
        ))

    return citations


def extract_evidence_json(output: str) -> Optional[List[EvidenceCitation]]:
    """Phase 3: Extract structured JSON evidence.

    Looks for:
    - ```json ... ``` code blocks with evidence schema
    - Bare JSON objects at end of output

    Args:
        output: Raw agent output text

    Returns:
        List of EvidenceCitation if valid JSON found, None otherwise
    """
    # Try JSON code blocks first
    json_match = re.search(r'```json\s*({[\s\S]*?})\s*```', output, re.DOTALL)
    if not json_match:
        # Try bare JSON at end of output
        json_match = re.search(r'\n({[\s\S]*})\s*$', output)

    if not json_match:
        return None

    try:
        data = json.loads(json_match.group(1))

        # Handle structured evidence schema
        if "evidence" in data and isinstance(data["evidence"], list):
            citations: List[EvidenceCitation] = []
            for item in data["evidence"]:
                if not isinstance(item, dict):
                    continue
                citation_type = str(item.get("type", "unknown"))
                reference = str(item.get("reference", ""))
                context = item.get("context")
                citations.append(EvidenceCitation(
                    citation_type=citation_type,
                    reference=reference,
                    context=str(context)[:200] if context else None
                ))
            return citations

        # Handle simple evidence list
        if "citations" in data and isinstance(data["citations"], list):
            citations: List[EvidenceCitation] = []
            for item in data["citations"]:
                if not isinstance(item, dict):
                    continue
                citation_type = str(item.get("type", "unknown"))
                reference = str(item.get("reference", ""))
                context = item.get("context")
                citations.append(EvidenceCitation(
                    citation_type=citation_type,
                    reference=reference,
                    context=str(context)[:200] if context else None
                ))
            return citations

        return None

    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        logger.debug(f"Failed to parse JSON evidence: {e}")
        return None


def extract_evidence(output: str, enable_json: bool = False) -> List[EvidenceCitation]:
    """Unified extraction API with graceful fallback.

    Tries JSON extraction first if enabled, falls back to regex.

    Args:
        output: Raw agent output text
        enable_json: If True, attempt JSON extraction before regex

    Returns:
        List of EvidenceCitation objects (empty if extraction fails)
    """
    # Try JSON first if enabled (Phase 3)
    if enable_json:
        json_citations = extract_evidence_json(output)
        if json_citations:
            return json_citations
        # Fall through to regex if JSON fails

    # Use regex extraction (Phase 2)
    return extract_evidence_regex(output)
