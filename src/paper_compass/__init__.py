"""Minimal package for Zotero + PaperQA + wiki + MCP project."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("paper-compass")
except PackageNotFoundError:
    __version__ = "0.0.0"
