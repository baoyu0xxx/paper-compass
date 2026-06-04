"""Lightweight handle helpers for MCP readback flows."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ParsedPaperHandle:
    doc_id: str


@dataclass
class ParsedPassageHandle:
    doc_id: str
    page_num: int | None
    search_mode: str
    ordinal: int


@dataclass
class ParsedWikiHandle:
    page_path: str
    section: str | None


def make_paper_handle(doc_id: str) -> str:
    return f"paper:{doc_id}"


def parse_paper_handle(handle: str) -> ParsedPaperHandle:
    if not handle.startswith("paper:"):
        raise ValueError(f"Invalid paper handle: {handle}")
    doc_id = handle.split(":", 1)[1].strip()
    if not doc_id:
        raise ValueError(f"Invalid paper handle: {handle}")
    return ParsedPaperHandle(doc_id=doc_id)


def make_passage_handle(doc_id: str, page_num: int | None, search_mode: str, ordinal: int) -> str:
    page_part = f"p{page_num}" if page_num is not None else "p?"
    return f"passage:{doc_id}:{page_part}:{search_mode}:{ordinal}"


def parse_passage_handle(handle: str) -> ParsedPassageHandle:
    parts = handle.split(":")
    if len(parts) != 5 or parts[0] != "passage":
        raise ValueError(f"Invalid passage handle: {handle}")
    _, doc_id, page_part, search_mode, ordinal_text = parts
    page_num = None
    if page_part != "p?":
        if not page_part.startswith("p"):
            raise ValueError(f"Invalid passage handle: {handle}")
        page_num = int(page_part[1:])
    return ParsedPassageHandle(
        doc_id=doc_id,
        page_num=page_num,
        search_mode=search_mode,
        ordinal=int(ordinal_text),
    )


def make_wiki_handle(page_path: str, section: str | int | None) -> str:
    if section is None or section == "":
        return f"wiki:{page_path}"
    return f"wiki:{page_path}#section={section}"


def parse_wiki_handle(handle: str) -> ParsedWikiHandle:
    if not handle.startswith("wiki:"):
        raise ValueError(f"Invalid wiki handle: {handle}")
    payload = handle[len("wiki:") :]
    if "#section=" in payload:
        page_path, section = payload.split("#section=", 1)
        return ParsedWikiHandle(page_path=page_path, section=section or None)
    return ParsedWikiHandle(page_path=payload, section=None)
