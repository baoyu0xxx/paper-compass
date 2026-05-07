"""
Shared data models for paper-compass.

Defines the UnifiedResponse envelope and typed search result structures
used across the MCP layer, router, and RAG modules.
"""

import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class WikiMatch:
    """A single wiki page match from search_wiki."""

    page_path: str
    title: str
    page_type: str = ""
    summary: str = ""
    snippet: str = ""
    score: float = 0.0


@dataclass
class LibraryMatch:
    """A single library entry match from search_library."""

    doc_id: str
    title: str
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    doi: str = ""
    journal: str = ""
    collections: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    pdf_path: str = ""
    metadata_source: str = ""
    score: float = 0.0


@dataclass
class PaperDetail:
    """Full metadata for a single paper (get_paper_metadata result)."""

    doc_id: str
    title: str
    authors: List[str] = field(default_factory=list)
    year: Optional[int] = None
    journal: str = ""
    doi: str = ""
    collections: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    pdf_path: str = ""
    metadata_source: str = ""


@dataclass
class ModeDecision:
    """Explanation of which retrieval mode was used and why."""

    requested: str = "auto"
    actual: str = "wiki"
    reason: str = ""


@dataclass
class UnifiedResponse:
    """Standard response envelope for all MCP tools."""

    ok: bool = True
    tool: str = ""
    trace_id: str = ""
    mode_used: str = "wiki"
    confidence: str = "medium"
    data: Any = None
    sources: List[Dict[str, str]] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    next_suggested_action: str = ""

    @classmethod
    def success(
        cls,
        tool: str,
        data: Any = None,
        mode_used: str = "wiki",
        confidence: str = "medium",
        sources: Optional[List[Dict[str, str]]] = None,
        warnings: Optional[List[str]] = None,
        next_action: str = "",
    ) -> "UnifiedResponse":
        return cls(
            ok=True,
            tool=tool,
            trace_id=str(uuid.uuid4())[:8],
            mode_used=mode_used,
            confidence=confidence,
            data=data,
            sources=sources or [],
            warnings=warnings or [],
            next_suggested_action=next_action,
        )

    @classmethod
    def error(
        cls,
        tool: str,
        warnings: Optional[List[str]] = None,
        next_action: str = "",
    ) -> "UnifiedResponse":
        return cls(
            ok=False,
            tool=tool,
            trace_id=str(uuid.uuid4())[:8],
            mode_used="none",
            confidence="low",
            data=None,
            sources=[],
            warnings=warnings or [],
            next_suggested_action=next_action,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "tool": self.tool,
            "trace_id": self.trace_id,
            "mode_used": self.mode_used,
            "confidence": self.confidence,
            "data": self.data,
            "sources": self.sources,
            "warnings": self.warnings,
            "next_suggested_action": self.next_suggested_action,
        }
