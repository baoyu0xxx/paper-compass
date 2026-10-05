"""Shared tokenization helpers for sparse keyword/BM25 search."""

from __future__ import annotations

import re

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]+")


def tokenize_for_sparse_search(text: str) -> list[str]:
    """Tokenize text for lightweight sparse search.

    The tokenizer intentionally avoids heavyweight segmentation dependencies.
    It keeps ASCII word/number/underscore tokens lowercased, and converts each
    contiguous CJK run into overlapping bigrams so unsegmented Chinese text can
    match short Chinese queries in keyword search and BM25.
    """
    tokens: list[str] = []
    for match in _TOKEN_RE.finditer(text or ""):
        part = match.group(0)
        if not part:
            continue
        if _is_cjk_run(part):
            if len(part) == 1:
                tokens.append(part)
            else:
                tokens.extend(part[i : i + 2] for i in range(len(part) - 1))
        else:
            tokens.append(part.lower())
    return [token for token in tokens if token]


def _is_cjk_run(text: str) -> bool:
    return all(_is_cjk_char(char) for char in text)


def _is_cjk_char(char: str) -> bool:
    return (
        "\u3400" <= char <= "\u4DBF"
        or "\u4E00" <= char <= "\u9FFF"
        or "\uF900" <= char <= "\uFAFF"
    )
